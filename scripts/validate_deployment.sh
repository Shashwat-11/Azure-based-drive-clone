#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ──────────────────────────────────────────
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-drive-production}"
CONTAINER_APP="${CONTAINER_APP:-ca-drive-backend}"
RESULTS_DIR="validation-results"
PASSWORD="Val1d@te-$(date +%s)"
EMAIL_PREFIX="validate"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

PASS_COUNT=0
FAIL_COUNT=0
FAIL_REQUESTS=()

# ── Setup ──────────────────────────────────────────────────
rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass()  { echo -e "${GREEN}[PASS]${NC} $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
log_fail()  { echo -e "${RED}[FAIL]${NC} $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); FAIL_REQUESTS+=("$1"); }
log_info()  { echo -e "${YELLOW}[INFO]${NC} $1"; }

die() {
    log_info "Fetching last 100 Container App logs..."
    az containerapp logs show \
        -g "$RESOURCE_GROUP" \
        -n "$CONTAINER_APP" \
        --tail 100 > "$RESULTS_DIR/crash-logs.json" 2>&1 || true
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo " DEPLOYMENT VALIDATION FAILED"
    echo "═══════════════════════════════════════════════════════════"
    echo "  Failing step: $1"
    echo "  Response:     $RESULTS_DIR/$2"
    echo "  Logs:         $RESULTS_DIR/crash-logs.json"
    echo "═══════════════════════════════════════════════════════════"
    exit 1
}

# ── Discover FQDN ──────────────────────────────────────────
log_info "Discovering Container App FQDN..."
APP_FQDN=$(az containerapp show \
    -g "$RESOURCE_GROUP" \
    -n "$CONTAINER_APP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

if [[ -z "$APP_FQDN" ]]; then
    echo "ERROR: Could not resolve Container App FQDN"
    exit 1
fi

APP_URL="https://${APP_FQDN}"
EMAIL="${EMAIL_PREFIX}-$(date +%s | shasum -a 256 | cut -c1-8)@example.com"

log_info "Target:  $APP_URL"
log_info "User:    $EMAIL"
echo ""

# ── Helper ─────────────────────────────────────────────────
do_curl() {
    local label="$1"
    local file="$2"
    shift 2
    curl -s -w "\n%{http_code}" "$@" > "$RESULTS_DIR/$file" 2>&1 || true
}

check_http() {
    local label="$1"
    local file="$2"
    local expected="${3:-200}"
    local body
    local code

    body=$(sed '$d' "$RESULTS_DIR/$file" 2>/dev/null || echo "")
    code=$(tail -n1 "$RESULTS_DIR/$file" 2>/dev/null || echo "000")

    if [[ "$code" == "$expected" ]]; then
        log_pass "$label"
    else
        log_fail "$label"
        echo "       Expected HTTP $expected, got HTTP $code"
        echo "       Body: $body"
        die "$label" "$file"
    fi
}

# ── Test 1: Health ─────────────────────────────────────────
log_info "1. Health check"
do_curl "Health" "01-health.json" \
    "$APP_URL/api/v1/health"
check_http "GET /api/v1/health" "01-health.json" 200

# ── Test 2: Live ───────────────────────────────────────────
log_info "2. Liveness check"
do_curl "Live" "02-live.json" \
    "$APP_URL/api/v1/live"
check_http "GET /api/v1/live" "02-live.json" 200

# ── Test 3: Startup ────────────────────────────────────────
log_info "3. Startup check"
do_curl "Startup" "03-startup.json" \
    "$APP_URL/api/v1/startup"
check_http "GET /api/v1/startup" "03-startup.json" 200

# ── Test 4: Register ───────────────────────────────────────
log_info "4. Register user"
do_curl "Register" "04-register.json" \
    -X POST "$APP_URL/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"Validator\"}"
check_http "POST /api/v1/auth/register" "04-register.json" 201

# ── Test 5: Login ──────────────────────────────────────────
log_info "5. Login"
do_curl "Login" "05-login.json" \
    -X POST "$APP_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
check_http "POST /api/v1/auth/login" "05-login.json" 200

ACCESS_TOKEN=$(sed '$d' "$RESULTS_DIR/05-login.json" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
REFRESH_TOKEN=$(sed '$d' "$RESULTS_DIR/05-login.json" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])" 2>/dev/null || echo "")

if [[ -z "$ACCESS_TOKEN" ]]; then
    log_fail "Token extraction"
    die "Token extraction" "05-login.json"
fi

# ── Test 6: GET /auth/me ───────────────────────────────────
log_info "6. Authenticated /auth/me"
do_curl "GET /me" "06-me.json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$APP_URL/api/v1/auth/me"
check_http "GET /api/v1/auth/me" "06-me.json" 200

# ── Test 7: Create folder ──────────────────────────────────
log_info "7. Create folder"
do_curl "Create folder" "07-create-folder.json" \
    -X POST "$APP_URL/api/v1/folders" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"Validation Folder"}'
check_http "POST /api/v1/folders" "07-create-folder.json" 201

FOLDER_ID=$(sed '$d' "$RESULTS_DIR/07-create-folder.json" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
if [[ -z "$FOLDER_ID" ]]; then
    log_fail "Folder ID extraction"
    die "Folder ID extraction" "07-create-folder.json"
fi

# ── Test 8: List folders ───────────────────────────────────
log_info "8. List folders"
do_curl "List folders" "08-list-folders.json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$APP_URL/api/v1/folders"
check_http "GET /api/v1/folders" "08-list-folders.json" 200

# ── Test 9: Upload file ────────────────────────────────────
log_info "9. Upload file"
echo "Drive validation content - $TIMESTAMP" > "$RESULTS_DIR/test-file.txt"
do_curl "Upload file" "09-upload.json" \
    -X POST "$APP_URL/api/v1/files/upload" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -F "file=@$RESULTS_DIR/test-file.txt" \
    -F "folder_id=$FOLDER_ID"
check_http "POST /api/v1/files/upload" "09-upload.json" 201

FILE_ID=$(sed '$d' "$RESULTS_DIR/09-upload.json" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
if [[ -z "$FILE_ID" ]]; then
    log_fail "File ID extraction"
    die "File ID extraction" "09-upload.json"
fi

# ── Test 10: Download file ─────────────────────────────────
log_info "10. Download file"
do_curl "Download file" "10-download.txt" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$APP_URL/api/v1/files/$FILE_ID/download"
check_http "GET /api/v1/files/:id/download" "10-download.txt" 200

DOWNLOADED=$(sed '$d' "$RESULTS_DIR/10-download.txt" 2>/dev/null || echo "")
EXPECTED="Drive validation content - $TIMESTAMP"
if [[ "$DOWNLOADED" == "$EXPECTED" ]]; then
    log_pass "Download content matches"
else
    log_fail "Download content mismatch"
    echo "       Expected: $EXPECTED"
    echo "       Got:      $DOWNLOADED"
fi

# ── Test 11: Delete file ───────────────────────────────────
log_info "11. Delete file"
do_curl "Delete file" "11-delete.json" \
    -X DELETE "$APP_URL/api/v1/files/$FILE_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN"
check_http "DELETE /api/v1/files/:id" "11-delete.json" 200

# ── Test 12: Logout ────────────────────────────────────────
log_info "12. Logout"
do_curl "Logout" "12-logout.json" \
    -X POST "$APP_URL/api/v1/auth/logout" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
check_http "POST /api/v1/auth/logout" "12-logout.json" 200

# ── Summary ────────────────────────────────────────────────
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo ""
echo "═══════════════════════════════════════════════════════════"
echo " DEPLOYMENT VALIDATION COMPLETE"
echo "═══════════════════════════════════════════════════════════"
printf "  %-45s %s\n" "Target" "$APP_URL"
printf "  %-45s %s\n" "User" "$EMAIL"
echo ""
printf "  %-45s %s\n" "Tests passed" "$PASS_COUNT / $TOTAL"
printf "  %-45s %s\n" "Tests failed" "$FAIL_COUNT / $TOTAL"
echo ""
printf "  %-45s %s\n" "Results directory" "$RESULTS_DIR/"
echo "═══════════════════════════════════════════════════════════"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
    echo ""
    echo "Failures:"
    for f in "${FAIL_REQUESTS[@]}"; do
        echo "  - $f"
    done
    exit 1
fi

exit 0
