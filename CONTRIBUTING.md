# Contributing to Drive

## Setup

```bash
git clone <repo-url>
cd Drive
cp .env.example .env
docker compose up -d postgres redis
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

## Development

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v --cov=app --cov-report=term
ruff check app/ tests/
```

## Commit Convention

```
feat(scope): description
fix(scope): description
refactor(scope): description
test(scope): description
docs(scope): description
```

## Pull Request Process

1. Create a feature branch from `main`
2. Write code with tests
3. Run `ruff check` and `pytest` locally
4. Open a PR against `main`
5. CI must pass (lint, tests, security scan, Docker build)
6. At least one review required
7. Squash-merge to `main`

## Architecture Rules

- Follow Clean Architecture: API → Service → Repository → Model
- Never put business logic in API routes
- Always use Pydantic schemas for request/response DTOs
- Use the Repository Pattern for database access
- Argon2 for passwords, SHA-256 for token storage
- Never log secrets, JWTs, or file contents

## Coding Standards

- Python 3.13+, type hints everywhere
- Line length: 120 characters
- Use `ruff` for linting and formatting
- Add docstrings for public APIs
- Follow SOLID principles
