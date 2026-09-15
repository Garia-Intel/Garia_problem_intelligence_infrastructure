# GARIA Backend

GARIA is a provenance-first Problem Intelligence Platform. This modular monolith uses FastAPI, PostgreSQL, SQLAlchemy, and Alembic.

## Architecture and flow

```text
Source (content hash)
  -> idempotent ingestion/extraction run
  -> candidate claims, evidence, and statistics (all source-linked)
  -> deterministic quality assessment
  -> human review + audit log
  -> guarded publication
```

AI-produced material is never published automatically. A published problem requires an approved review and at least one claim linked to a source.

## Quick start

1. Copy `.env.example` to `.env` and adjust values as needed.
2. Start services: `docker compose up --build`.
3. Apply schema migrations: `docker compose exec backend alembic upgrade head`.
4. Visit `http://localhost:8000/docs`.

## Phase 2 endpoints

- `POST /api/v1/sources/{source_id}/process` records an idempotent extraction run.
- `GET /api/v1/extraction-runs/{run_id}` retrieves run provenance.
- `POST|GET /api/v1/problems/{id}/claims` manages source-linked claims.
- `POST /api/v1/claims/{id}/evidence` attaches short, traceable evidence.
- `POST|GET /api/v1/problems/{id}/statistics` manages validated statistics.
- `POST /api/v1/problems/{id}/review` records an immutable review decision and audit event.
- `POST /api/v1/problems/{id}/publish?reviewer_id=...` enforces review and provenance requirements.
- `GET /api/v1/problems/{id}/quality` returns versioned deterministic readiness dimensions.

## Processing a source

Create a source with `content` to enable SHA-256 duplicate detection, then process it:

```bash
curl -X POST http://localhost:8000/api/v1/sources/SOURCE_ID/process -H "Content-Type: application/json" -d '{}'
```

Processing creates an `IngestionJob`, an `ExtractionRun`, and an audit entry. Repeating the request for unchanged source content returns the existing run rather than duplicating work.

## Local development

Create a Python 3.12 virtual environment, install `pip install -r requirements.txt`, set `DATABASE_URL`, then run `alembic upgrade head` and `uvicorn app.main:app --reload`.

Run checks with `pytest`, `ruff check .`, and `black --check .`.

## Scope

## Environment

`DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are read from `.env`. OpenAI credentials are optional. Phase 2 intentionally records extraction provenance without making an implicit OpenAI request; provider calls and asynchronous Celery dispatch are the next safe increment.

## Current limitations

- No authentication/authorization provider exists yet; reviewer IDs are explicit request values for development only.
- Extraction run creation is synchronous and records an empty candidate result when no explicit extractor is configured.
- PDF/web/video acquisition and full OpenAI structured extraction remain future work.
