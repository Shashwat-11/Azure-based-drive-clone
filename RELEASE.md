# Release Checklist — v1.0.0

## Pre-Release

- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Coverage at 80%+
- [ ] Ruff lint clean (`ruff check app/ tests/`)
- [ ] Production Dockerfile builds (`docker build -f backend/Dockerfile.prod backend/`)
- [ ] Database migrations up to date (`alembic upgrade head`)
- [ ] No hardcoded secrets in codebase
- [ ] `.env.example` matches all required variables
- [ ] Terraform plan validates (`terraform plan`)

## Deployment Preparation

- [ ] GitHub secrets configured (`AZURE_CREDENTIALS`, `ACR_*`)
- [ ] Azure resources provisioned (Terraform apply)
- [ ] Database migrations run against production
- [ ] Azure Key Vault secrets populated
- [ ] Container App revision is healthy

## Smoke Tests

- [ ] `GET /api/v1/health` returns 200
- [ ] `GET /api/v1/ready` returns ready status
- [ ] `POST /api/v1/auth/register` creates user
- [ ] `POST /api/v1/auth/login` returns tokens
- [ ] `POST /api/v1/files/upload` accepts file
- [ ] `GET /api/v1/files/{id}/download` streams file
- [ ] `POST /api/v1/folders` creates folder
- [ ] `GET /api/v1/search?query=test` returns results
- [ ] `GET /api/v1/versions/file/{id}` returns versions

## Monitoring

- [ ] Application Insights receiving telemetry
- [ ] Log Analytics receiving structured logs
- [ ] Prometheus metrics endpoint accessible
- [ ] Azure Monitor alerts configured
- [ ] Dashboard accessible

## Documentation

- [ ] `DEPLOYMENT.md` up to date
- [ ] `CHANGELOG.md` updated for v1.0.0
- [ ] `README.md` reflects current state
- [ ] Architecture docs current

## Post-Release

- [ ] Git tag `v1.0.0` created
- [ ] Release notes published on GitHub
- [ ] Team notified
- [ ] Monitor error rate for 24 hours
- [ ] Backup verified

## Sign-off

- [ ] Lead Engineer
- [ ] Security Review
- [ ] Operations Review
