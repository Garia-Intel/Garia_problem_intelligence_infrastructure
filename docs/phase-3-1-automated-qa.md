# Phase 3.1: Automated QA

Automated QA checks structural integrity, consistency and provenance. It does not establish factual truth. Factual verification is handled in Phase 3.3.

## Lifecycle

`ai_extracted` (or another candidate state) → `POST /api/v1/problems/{id}/qa` → `human_review` on no blocking errors, or `qa_failed` when an error is found. Each run persists a new immutable `QAResult`; the GET endpoint returns the latest one. Repaired `qa_failed` candidates can pass on a later run. `verified` and `published` records are never automatically moved backward.

## Checks

The deterministic v1 validator checks required title/source linkage; claim source/document/extraction-run provenance; evidence document and claim-document consistency; and statistic indicator/value/source/document/claim/evidence/unit/year/percentage/geography structure. Duplicate statistic fingerprints and missing evidence excerpts are warnings. Warnings identify reviewer attention items; errors block the review transition.

## API

- `POST /api/v1/problems/{id}/qa` runs QA and records a result.
- `GET /api/v1/problems/{id}/qa` returns the latest result.
- `GET /api/v1/problems/{id}/qa/history` returns immutable results newest first.

A result contains `passed`, `score`, `checks`, `errors`, `warnings`, `checkedAt` (`created_at`), and `validatorVersion` (`validator_version`). Checks contain stable codes, category, severity, pass state, field, message, and optional metadata.

## Adding a rule

Add a small deterministic check in `app/services/qa.py`, include a stable machine-readable code, and add an isolated test. Do not use an LLM or set verification status inside QA.

## Deferred work

Authentication/authorization, reviewer decisions, factual claim verification, full quality scoring, source versioning, and audit/version history expansion are Phase 3.2–3.6 work.
