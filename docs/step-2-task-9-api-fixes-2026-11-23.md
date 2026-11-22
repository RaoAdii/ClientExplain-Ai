# Task 9 API contract fix — 23 November 2026

The workflow routes returned the application's custom HTTP 422 validation envelope, but OpenAPI advertised FastAPI's default `HTTPValidationError` on eight routes. Upload advertised the generic error envelope, omitting the validation `fields` array. Nine regression cases reproduced the mismatch before implementation.

The Documents and Analysis routers now declare `ValidationErrorRead`, including required `error.message` and `error.fields` with each field's location and message. Upload declares both the validation envelope and the existing generic error envelope used for rejected files and unknown multipart fields. The generated `packages/contracts/openapi.json` reflects these response schemas. Request validators and the runtime exception handler retain their existing behavior.

Regression coverage checks OpenAPI and actual malformed UUID responses for all nine workflow route/method combinations. Existing rejection coverage now also checks body, header and query validation fields and the generic multipart rejection envelope.

Verification:

- Before the fix: all **9** new contract regression cases failed on the expected missing/custom response schema assertion.
- `python -m pytest services/api/tests/test_step2_api.py -q --tb=short`: **42 passed**.
- `python -m pytest -q --tb=short`: **357 passed**.
- `python -m ruff check services/api services/worker scripts`: **passed**.
- `python -m ruff format --check services/api services/worker scripts`: **71 files already formatted**.
- `git diff --check`: **passed**.

No live provider request or credential changes were needed. Existing web work and Task 8 files were preserved.
