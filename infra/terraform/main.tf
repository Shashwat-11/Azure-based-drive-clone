terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
  required_version = ">= 1.5"
}

provider "azurerm" {
  features {}
}

data "azurerm_client_config" "current" {}

variable "environment" { default = "production" }
variable "location" { default = "centralindia" }
variable "app_name" { default = "drive" }
variable "postgres_sku" { default = "B_Standard_B1ms" }
variable "postgres_storage_mb" { default = 32768 }
variable "redis_sku" { default = "Balanced_B0" }
variable "container_cpu" { default = 0.5 }
variable "container_memory" { default = "1.0Gi" }
variable "container_min_replicas" { default = 1 }
variable "container_max_replicas" { default = 3 }

# Bootstrap image used for initial provisioning.
# GitHub Actions replaces this with the real application image on first CD run.
variable "container_image" {
  default     = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
  description = "Container image to deploy. Overridden by GitHub Actions CD pipeline at runtime."
}

# ── Foundation ──────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.app_name}-${var.environment}"
  location = var.location
}

# ── Logging & Monitoring ───────────────────────────────

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "main" {
  depends_on          = [azurerm_log_analytics_workspace.main]
  name                = "appi-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}

# ── Key Vault ───────────────────────────────────────────

resource "azurerm_key_vault" "main" {
  name                = "kv-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  soft_delete_retention_days = 90
  purge_protection_enabled   = true
}

resource "azurerm_key_vault_access_policy" "current_user" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get", "List", "Set", "Delete", "Recover", "Backup", "Restore",
  ]
}

# ── ACR ─────────────────────────────────────────────────

resource "azurerm_container_registry" "main" {
  name                = replace("cr${var.app_name}${var.environment}", "-", "")
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = true
}

# ── PostgreSQL ──────────────────────────────────────────

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  version             = "16"
  sku_name            = var.postgres_sku
  storage_mb          = var.postgres_storage_mb

  zone = "1"

  administrator_login    = "drive_admin"
  administrator_password = random_password.db_password.result

  backup_retention_days = 7
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = var.app_name
  server_id = azurerm_postgresql_flexible_server.main.id
}

# ── Key Vault Secrets ───────────────────────────────────

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

resource "azurerm_key_vault_secret" "db_password" {
  depends_on   = [azurerm_key_vault_access_policy.current_user]
  name         = "database-password"
  value        = random_password.db_password.result
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "storage_account_key" {
  depends_on   = [azurerm_key_vault_access_policy.current_user, azurerm_storage_account.main]
  name         = "storage-account-key"
  value        = azurerm_storage_account.main.primary_access_key
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "jwt_secret" {
  depends_on   = [azurerm_key_vault_access_policy.current_user]
  name         = "jwt-secret-key"
  value        = random_password.jwt_secret.result
  key_vault_id = azurerm_key_vault.main.id
}

# ── Managed Redis ──────────────────────────────────────

resource "azurerm_managed_redis" "main" {
  name                = "redis-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Balanced_B0"

  default_database {}
}

# ── Storage ─────────────────────────────────────────────

resource "azurerm_storage_account" "main" {
  name                     = "st${var.app_name}${var.environment}"
  location                 = azurerm_resource_group.main.location
  resource_group_name      = azurerm_resource_group.main.name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
    container_delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "files" {
  depends_on            = [azurerm_storage_account.main]
  name                  = "${var.app_name}-files"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# ── Container Apps ──────────────────────────────────────

resource "azurerm_container_app_environment" "main" {
  depends_on                 = [azurerm_log_analytics_workspace.main]
  name                       = "cae-${var.app_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

resource "azurerm_container_app" "backend" {
  depends_on = [
    azurerm_container_app_environment.main,
    azurerm_postgresql_flexible_server_database.main,
    azurerm_managed_redis.main,
    azurerm_storage_container.files,
  ]

  name                         = "ca-${var.app_name}-backend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    container {
      name   = "backend"
      image  = var.container_image
      cpu    = var.container_cpu
      memory = var.container_memory
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "DB_HOST"
        value = azurerm_postgresql_flexible_server.main.fqdn
      }
      env {
        name  = "DB_USER"
        value = "drive_admin"
      }
      env {
        name  = "DB_NAME"
        value = var.app_name
      }
      env {
        name        = "DB_PASSWORD"
        secret_name = "db-password"
      }
      env {
        name  = "REDIS_HOST"
        value = azurerm_managed_redis.main.hostname
      }
      env {
        name  = "REDIS_PORT"
        value = "6380"
      }
      env {
        name  = "REDIS_SSL"
        value = "true"
      }
      env {
        name        = "REDIS_PASSWORD"
        secret_name = "redis-password"
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
      env {
        name        = "AZURE_STORAGE_ACCOUNT_KEY"
        secret_name = "storage-key"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER_NAME"
        value = azurerm_storage_container.files.name
      }
      env {
        name        = "JWT_SECRET_KEY"
        secret_name = "jwt-secret"
      }
      env {
        name  = "AZURE_APPINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
      env {
        name  = "OTEL_ENABLED"
        value = "true"
      }
      env {
        name  = "WORKERS"
        value = "1"
      }
    }
    min_replicas = var.container_min_replicas
    max_replicas = var.container_max_replicas
  }

  secret {
    name  = "db-password"
    value = random_password.db_password.result
  }
  secret {
    name  = "storage-key"
    value = azurerm_storage_account.main.primary_access_key
  }
  secret {
    name  = "jwt-secret"
    value = random_password.jwt_secret.result
  }
  secret {
    name  = "redis-password"
    value = azurerm_managed_redis.main.primary_access_key
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# ── Alerts ──────────────────────────────────────────────

resource "azurerm_monitor_action_group" "oncall" {
  name                = "ag-${var.app_name}-oncall"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "oncall"
}

resource "azurerm_monitor_metric_alert" "high_error_rate" {
  depends_on          = [azurerm_application_insights.main, azurerm_monitor_action_group.oncall]
  name                = "alert-${var.app_name}-error-rate"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Alert when server error rate exceeds threshold"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.Insights/components"
    metric_name      = "exceptions/count"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 10
  }

  action {
    action_group_id = azurerm_monitor_action_group.oncall.id
  }
}

resource "azurerm_monitor_metric_alert" "availability" {
  depends_on          = [azurerm_container_app.backend, azurerm_monitor_action_group.oncall]
  name                = "alert-${var.app_name}-availability"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.backend.id]
  description         = "Alert when application is unavailable"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "Replicas"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 1
  }

  action {
    action_group_id = azurerm_monitor_action_group.oncall.id
  }
}

# ── Outputs ─────────────────────────────────────────────

output "app_url" {
  value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "acr_admin_username" {
  value     = azurerm_container_registry.main.admin_username
  sensitive = true
}

output "acr_admin_password" {
  value     = azurerm_container_registry.main.admin_password
  sensitive = true
}

output "container_app_fqdn" {
  value = azurerm_container_app.backend.ingress[0].fqdn
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "db_host" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "redis_host" {
  value = azurerm_managed_redis.main.hostname
}

output "storage_account" {
  value = azurerm_storage_account.main.name
}

output "storage_account_key" {
  value     = azurerm_storage_account.main.primary_access_key
  sensitive = true
}
