You are a Senior Staff Software Engineer, Cloud Architect, and DevOps Engineer.

Your task is to build a production-grade cloud storage platform similar to Google Drive.

This is NOT a prototype.
This is NOT a CRUD project.
This should resemble software built by Microsoft, Google, Dropbox, or AWS engineers.

====================================================
PROJECT GOAL
====================================================

Build a cloud storage platform that supports:

• Authentication
• Folder hierarchy
• File uploads
• Azure Blob Storage integration
• File sharing
• File versioning
• Trash
• Search
• Monitoring
• Logging
• Security
• Production deployment

Every decision should prioritize:

- scalability
- maintainability
- observability
- security
- extensibility

====================================================
TECH STACK
====================================================

Backend
--------
FastAPI
Python 3.13+

SQLAlchemy 2.x

Alembic

Pydantic v2

PostgreSQL

Redis

Azure Blob Storage SDK

JWT Authentication

Background Tasks

Pytest

Frontend
---------
Next.js

TypeScript

TailwindCSS

React Query

Axios

Docker

Deployment
----------
Docker Compose for development

Azure App Service or Azure Container Apps

GitHub Actions

====================================================
ARCHITECTURE
====================================================

Use Clean Architecture.

Separate

presentation

application

domain

infrastructure

Never mix business logic with API routes.

Use

Repository Pattern

Service Layer

Dependency Injection

Configuration Layer

Separate

DTOs

Entities

ORM Models

Validation Models

====================================================
FOLDER STRUCTURE
====================================================

Backend should resemble

backend/

app/

api/

core/

config/

dependencies/

domain/

services/

repositories/

schemas/

models/

middleware/

storage/

auth/

workers/

tests/

migrations/

logs/

Frontend should have

app/

components/

hooks/

services/

types/

utils/

====================================================
DATABASE DESIGN
====================================================

Use PostgreSQL.

Tables

users

folders

files

file_versions

shared_links

permissions

activity_logs

audit_logs

sessions

refresh_tokens

Every table must

have UUID primary keys

timestamps

soft delete support

indexes

foreign keys

constraints

====================================================
FILE STORAGE
====================================================

Store files ONLY inside Azure Blob Storage.

Database stores only metadata.

Blob name should be UUID based.

Support

upload

download

delete

move

copy

rename

folder upload

streaming download

large files

Do not load entire files into memory.

====================================================
AUTHENTICATION
====================================================

Support

JWT

Refresh Tokens

Email Verification

Password Reset

Google OAuth (optional)

Microsoft OAuth (optional)

Passwords must use Argon2.

Implement

RBAC

Role-based authorization

====================================================
FOLDER SYSTEM
====================================================

Unlimited nesting

Recursive delete

Recursive move

Recursive copy

Breadcrumbs

Folder size calculation

====================================================
FILE FEATURES
====================================================

Upload

Download

Rename

Move

Copy

Delete

Restore

Trash

Permanent delete

Favorites

Recent files

Starred files

Preview metadata

Version history

====================================================
SEARCH
====================================================

Search by

filename

extension

owner

date

size

tags

folder

Use PostgreSQL Full Text Search initially.

====================================================
SHARING
====================================================

Support

Owner

Editor

Viewer

Commenter

Public links

Private links

Expiry

Password protected links

Download restrictions

====================================================
API
====================================================

RESTful

Versioned APIs

/api/v1/

Swagger

OpenAPI

Proper status codes

Validation

Pagination

Filtering

Sorting

====================================================
ERROR HANDLING
====================================================

Never expose stack traces.

Create standardized error responses.

Example

{
  "success": false,
  "message": "...",
  "code": "...",
  "traceId": "..."
}

====================================================
LOGGING
====================================================

Use structured JSON logging.

Every request must contain

requestId

traceId

userId

IP

duration

status code

Log

Uploads

Downloads

Deletes

Login attempts

Permission changes

Errors

Security events

Logs should integrate with Azure Monitor.

====================================================
MONITORING
====================================================

Integrate

Azure Monitor

Application Insights

Log Analytics

Metrics

Distributed tracing

Collect

Latency

Request counts

Exceptions

Blob upload failures

Database timings

Dependency timings

Memory

CPU

====================================================
HEALTH CHECKS
====================================================

Create

/health

/ready

/live

Include

database

blob storage

redis

====================================================
SECURITY
====================================================

Validate MIME type

Validate file size

Virus scan interface

Rate limiting

HTTPS

Security headers

CORS

Input validation

SQL Injection protection

XSS protection

CSRF (if cookies)

Signed URLs

Secrets stored only in Azure Key Vault or environment variables.

Never hardcode secrets.

====================================================
TESTING
====================================================

Write tests for

Services

Repositories

Authentication

Permissions

Storage

API

Target

90%+ coverage.

====================================================
CI/CD
====================================================

GitHub Actions should

Run lint

Run tests

Run type checks

Build Docker

Run migrations

Deploy

====================================================
DOCUMENTATION
====================================================

Generate

README

Architecture diagram

ER Diagram

API documentation

Deployment guide

Developer guide

Contribution guide

====================================================
CODE QUALITY
====================================================

Use

type hints

docstrings

SOLID principles

DRY

KISS

Meaningful variable names

No duplicated logic.

No magic numbers.

No global mutable state.

====================================================
OBSERVABILITY
====================================================

Every request should be traceable.

Support correlation IDs.

Every exception should be logged.

Every external dependency should be traced.

====================================================
PERFORMANCE
====================================================

Use

Streaming uploads

Streaming downloads

Pagination

Indexes

Caching

Connection pooling

Async endpoints where beneficial.

====================================================
DOCKER
====================================================

Provide

Dockerfile

docker-compose.yml

development

production

====================================================
DELIVERABLES
====================================================

Implement incrementally.

Never dump thousands of lines at once.

For each feature:

1. Explain architecture.
2. Explain design decisions.
3. Write code.
4. Write tests.
5. Update documentation.
6. Explain production considerations.
7. Explain Azure integration.

Always ask yourself

"Would this survive production traffic?"

If the answer is no,
improve the implementation before continuing.

Whenever possible, choose maintainability over cleverness.

Assume this project will be reviewed by senior backend engineers during a software engineering interview.

The final codebase should be something worthy of being open-sourced as a portfolio project demonstrating backend engineering, cloud engineering, DevOps, and production readiness.



At any point, if a proposed implementation would not scale or would be considered poor practice in a production environment, explain the issue and implement a more robust alternative, even if it requires slightly more code. Favor maintainability, security, observability, and correctness over speed of implementation.
