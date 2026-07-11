#!/usr/bin/env bash
# Usage: bash scripts/health-check.sh <url> <container-app-name>
set -euo pipefail

TARGET_URL="${1:?missing target URL}"
CONTAINER_APP="${2:-ca-drive-backend}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-drive-production}"

echo "── DNS resolution ──"
FQDN=$(echo "$TARGET_URL" | sed 's|https\?://||' | cut -d/ -f1)
dig +short "${FQDN}" 2>/dev/null || nslookup "${FQDN}" 2>/dev/null || echo "(DNS lookup unavailable)"

echo ""
echo "── Container App Status (pre-flight) ──"
az containerapp show \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "{name:name, provisioningState:properties.provisioningState, fqdn:properties.configuration.ingress.fqdn, targetPort:properties.configuration.ingress.targetPort, latestRevisionName:properties.latestRevisionName}" -o json

echo ""
echo "── Revision Status (pre-flight) ──"
az containerapp revision list \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{name:name, active:properties.active, replicas:properties.replicas, healthState:properties.healthState}" -o table

echo ""
echo "── Recent Container Logs (pre-flight, last 50 lines) ──"
az containerapp logs show \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 50 2>/dev/null || echo "(unable to fetch logs)"

echo ""
echo "── Beginning health check loop ──"
for i in $(seq 1 12); do
  echo ""
  echo "Attempt ${i}/12..."

  CURL_EXIT=0
  RESPONSE=$(curl -s -w '\n%{http_code}' \
    --connect-timeout 10 \
    --max-time 20 \
    "${TARGET_URL}" 2>&1) || CURL_EXIT=$?

  HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
  BODY=$(echo "${RESPONSE}" | sed '$d')

  echo "  curl exit code: ${CURL_EXIT}"
  if [ "${CURL_EXIT}" != "0" ]; then
    echo "  curl error (exit ${CURL_EXIT})"
  fi
  echo "  HTTP status: ${HTTP_CODE}"
  echo "  Response body: ${BODY}"

  if [ "${CURL_EXIT}" = "0" ] && [ "${HTTP_CODE}" = "200" ]; then
    echo ""
    echo "Health check passed."
    exit 0
  fi

  sleep 10
done

set +e
echo ""
echo "::error::Health check failed after 12 attempts"
echo ""
echo "── Container App Status (post-mortem) ──"
az containerapp show \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "{name:name, provisioningState:properties.provisioningState, fqdn:properties.configuration.ingress.fqdn, targetPort:properties.configuration.ingress.targetPort, latestRevisionName:properties.latestRevisionName}" -o json || true

echo ""
echo "── Revision Status (post-mortem) ──"
az containerapp revision list \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{name:name, active:properties.active, provisioningState:properties.provisioningState, replicas:properties.replicas, healthState:properties.healthState}" -o table || true

echo ""
echo "── Ingress URL ──"
echo "${TARGET_URL}"

echo ""
echo "── Container Logs (post-mortem, last 100 lines) ──"
az containerapp logs show \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 100 2>/dev/null || echo "(unable to fetch logs)"

exit 1
