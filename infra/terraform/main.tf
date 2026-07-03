terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
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

variable "environment" { default = "production" }
variable "location" { default = "eastus" }
variable "app_name" { default = "drive" }
variable "postgres_sku" { default = "GP_Standard_D2s_v3" }
variable "postgres_storage_mb" { default = 32768 }
variable "redis_sku" { default = "Standard" }
variable "redis_capacity" { default = 1 }
variable "container_cpu" { default = 1.0 }
variable "container_memory" { default = "2.0Gi" }
variable "container_min_replicas" { default = 1 }
variable "container_max_replicas" { default = 5 }

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.app_name}-${var.environment}"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}

resource "azurerm_key_vault" "main" {
  name                = "kv-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  soft_delete_retention_days = 90
  purge_protection_enabled   = true
}

data "azurerm_client_config" "current" {}

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  version             = "16"
  sku_name            = var.postgres_sku
  storage_mb          = var.postgres_storage_mb

  administrator_login    = "drive_admin"
  administrator_password = random_password.db_password.result

  backup_retention_days = 7
  geo_redundant_backup  = false

  high_availability {
    mode = "Disabled"
  }
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = var.app_name
  server_id = azurerm_postgresql_flexible_server.main.id
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "database-password"
  value        = random_password.db_password.result
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_redis_cache" "main" {
  name                = "redis-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  capacity            = var.redis_capacity
  family              = "C"
  sku_name            = var.redis_sku
  minimum_tls_version = "1.2"
  redis_version       = "7.4"

  redis_configuration {
    maxmemory_policy = "volatile-lru"
  }
}

resource "azurerm_storage_account" "main" {
  name                = "st${var.app_name}${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  account_tier        = "Standard"
  account_replication_type = "LRS"
  min_tls_version     = "TLS1_2"

  blob_properties {
    versioning_enabled = true
    container_delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "files" {
  name                  = "${var.app_name}-files"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_container_app_environment" "main" {
  name                = "cae-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

resource "azurerm_container_app" "backend" {
  name                         = "ca-${var.app_name}-backend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    container {
      name   = "backend"
      image  = "${var.container_registry}/drive-backend:latest"
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
        name  = "DB_NAME"
        value = var.app_name
      }
      env {
        name = "DB_PASSWORD"
        secret_ref = "db-password"
      }
      env {
        name  = "REDIS_HOST"
        value = azurerm_redis_cache.main.hostname
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
      env {
        name  = "AZURE_APPINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
      env {
        name  = "OTEL_ENABLED"
        value = "true"
      }
    }
    min_replicas = var.container_min_replicas
    max_replicas = var.container_max_replicas
  }

  secret {
    name  = "db-password"
    value = random_password.db_password.result
  }

  ingress {
    external_enabled = true
    target_port      = 8000
  }
}

resource "azurerm_monitor_action_group" "oncall" {
  name                = "ag-${var.app_name}-oncall"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "oncall"
}

resource "azurerm_monitor_metric_alert" "high_error_rate" {
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
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 10
  }

  action {
    action_group_id = azurerm_monitor_action_group.oncall.id
  }
}

resource "azurerm_monitor_metric_alert" "availability" {
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

output "app_url" { value = azurerm_container_app.backend.ingress[0].fqdn }
output "key_vault_uri" { value = azurerm_key_vault.main.vault_uri }
output "db_host" { value = azurerm_postgresql_flexible_server.main.fqdn }
output "redis_host" { value = azurerm_redis_cache.main.hostname }
output "storage_account" { value = azurerm_storage_account.main.name }
