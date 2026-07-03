# Deployment Guide

## Prerequisites

- Azure subscription with Contributor access
- [Terraform](https://www.terraform.io/) >= 1.5
- [Azure CLI](https://docs.microsoft.com/cli/azure/) >= 2.50
- [Docker](https://www.docker.com/) >= 24
- GitHub repository with Actions enabled

## Azure Resources

| Resource | SKU | Purpose |
|---|---|---|
| Container Apps | Consumption | Application hosting |
| PostgreSQL Flexible Server | GP_Standard_D2s_v3 | Primary database |
| Redis Cache | Standard C1 | Caching and rate limiting |
| Storage Account (Blob) | Standard LRS | File storage |
| Key Vault | Standard | Secrets management |
| Log Analytics Workspace | PerGB2018 | Centralized logging |
| Application Insights | — | APM and distributed tracing |

## Terraform Deployment

```bash
cd infra/terraform

# Login to Azure
az login

# Initialize
terraform init

# Plan
terraform plan -var="environment=production" -out=tfplan

# Apply
terraform apply tfplan

# Output connection details
terraform output
```

## Environment Variables

Required for production:

| Variable | Source |
|---|---|
| `DB_HOST` | `terraform output db_host` |
| `DB_PASSWORD` | Key Vault: `database-password` |
| `REDIS_HOST` | `terraform output redis_host` |
| `JWT_SECRET_KEY` | Generate: `openssl rand -hex 64` |
| `AZURE_STORAGE_ACCOUNT_NAME` | `terraform output storage_account` |
| `AZURE_STORAGE_ACCOUNT_KEY` | Azure Portal → Storage Account → Access Keys |

## GitHub Secrets

Set in repository Settings → Secrets and variables → Actions:

| Secret | Description |
|---|---|
| `AZURE_CREDENTIALS` | JSON output from `az ad sp create-for-rbac --sdk-auth` |
| `ACR_LOGIN_SERVER` | Azure Container Registry login server URL |
| `ACR_USERNAME` | ACR admin username |
| `ACR_PASSWORD` | ACR admin password |

## Deployment Commands

```bash
# Build production image
docker build -f backend/Dockerfile.prod -t drive-backend:latest backend/

# Push to container registry
az acr login --name <registry-name>
docker tag drive-backend:latest <registry>.azurecr.io/drive-backend:latest
docker push <registry>.azurecr.io/drive-backend:latest

# Deploy via CI/CD (automatic)
git push origin main
```

## Database Migrations

```bash
# Run migrations before starting the app
cd backend
alembic upgrade head
```

## Rollback Procedure

1. Identify the previous healthy image: `az acr repository show-tags`
2. Update Container App:
   ```bash
   az containerapp update --name ca-drive-backend --resource-group rg-drive-production --image <registry>/drive-backend:<previous-sha>
   ```
3. Verify: `curl <app-url>/api/v1/health`

## Scaling

Horizontal scaling via Azure Container Apps:

```bash
az containerapp update --name ca-drive-backend --min-replicas 2 --max-replicas 10
```

Database scaling:

```bash
az postgres flexible-server update --sku-name GP_Standard_D4s_v3 --storage-size 65536
```

## Troubleshooting

| Issue | Command |
|---|---|
| Container logs | `az containerapp logs show -n ca-drive-backend -g rg-drive-production` |
| DB connectivity | `az postgres flexible-server show-connection-string -n psql-drive-production` |
| Health check | `curl <app-url>/api/v1/health` |
| Ready check | `curl <app-url>/api/v1/ready` |
