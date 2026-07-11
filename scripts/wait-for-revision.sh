#!/usr/bin/env bash
# Usage: bash scripts/wait-for-revision.sh <container-app-name> <revision-name>
set -euo pipefail

CONTAINER_APP="${1:?missing container app name}"
REVISION_NAME="${2:?missing revision name}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-drive-production}"

echo "Waiting for Container App provisioning to succeed..."
for i in $(seq 1 30); do
  PROVISIONING=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.provisioningState -o tsv)
  echo "  [$i/30] provisioningState=${PROVISIONING}"
  if [ "${PROVISIONING}" = "Succeeded" ]; then
    break
  fi
  sleep 10
done

if [ "${PROVISIONING}" != "Succeeded" ]; then
  echo "::error::Container App provisioning did not succeed after 5 minutes"
  az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "{name:name, provisioningState:properties.provisioningState, latestRevisionName:properties.latestRevisionName}" -o json
  exit 1
fi

echo "Waiting for revision ${REVISION_NAME} to become active..."
for i in $(seq 1 30); do
  ACTIVE=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='${REVISION_NAME}'].properties.active" -o tsv)
  ACTIVE_TRIMMED=$(echo "${ACTIVE}" | tr -d '[:space:]')
  echo "  [$i/30] revision=${REVISION_NAME} active='${ACTIVE}' (trimmed='${ACTIVE_TRIMMED}')"
  if [ "${ACTIVE_TRIMMED}" = "true" ]; then
    break
  fi
  sleep 10
done

if [ "${ACTIVE_TRIMMED}" != "true" ]; then
  echo "::error::Revision ${REVISION_NAME} did not become active after 5 minutes"
  az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[].{name:name, active:properties.active, provisioningState:properties.provisioningState, replicas:properties.replicas}" -o table
  exit 1
fi

echo "Revision ${REVISION_NAME} is active."
