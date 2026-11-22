# Task 8 audit fixes — 23 November 2026

The audit regressions were reproduced before implementation. The initial focused run had 14 failures and 31 passes: requests above 12,000 characters failed embedding input validation, filenames above 200 characters failed evidence validation, empty document selections used curated sources, and terminal provider failures left the project idle or running. Additional tests reproduced whitespace-only query segments and watchdog failure-state drift.

## Changes

- Keep the analysis request limit at 20,000 characters. Split its retrieval query into inputs of at most 12,000 characters, discard whitespace-only segments, and pool the embeddings by segment length. The analysis provider receives the complete original request. Tests cover 12,000, 12,001 and 20,000 characters, whitespace-only segments, and retrieval influenced by both ends of a long request.
- Permit evidence source filenames through 255 characters, matching stored document filenames. Real pgvector retrieval tests cover 201- and 255-character filenames.
- Keep an empty document selection general and unverified even when curated sources exist. Both initial retrieval and publication revalidation use empty evidence in that case.
- Persist project processing failure in the same transaction as analysis job failure, including disabled providers, exhausted transient failures, permanent failures and watchdog recovery. A replayed old failure cannot overwrite a newer running or completed analysis.

## Verification

- `python -m pytest services/api/tests/test_analysis_pipeline.py services/api/tests/test_rag.py services/api/tests/test_jobs.py -q --tb=short`: **114 passed**.
- Ruff lint and formatting checks over all five changed Python files: **passed**.
- `python -m pytest -q --tb=short` against the shared working tree while Task 9 was being implemented: **325 passed, 11 failed, 1 teardown error**. The failures concern upload rate-limit integration in concurrent Task 9 changes; those files were preserved for that task's owner.
- Full-tree Ruff: two import-order findings in `services/api/app/services/documents.py` and `services/api/app/services/workflow.py`; formatting findings in seven concurrent Task 9 files. Scoped Task 8 checks remain clean.

Full-suite failure names:

- `test_invalid_upload_creates_no_row_or_private_object[huge.txt-text/plain-body7-413]`
- `test_exact_25_mib_boundary_is_accepted`
- `test_duplicate_is_conflict_without_new_object_or_job`
- `test_failure_rolls_back_rows_jobs_and_exact_object[storage]`
- `test_failure_rolls_back_rows_jobs_and_exact_object[commit]` (also teardown error after the early response assertion)
- `test_failure_rolls_back_rows_jobs_and_exact_object[dispatch]`
- `test_dispatch_compensation_recovers_database_cleanup_failure[execute]`
- `test_dispatch_compensation_recovers_database_cleanup_failure[commit]`
- `test_dispatch_compensation_recovers_database_cleanup_failure[rollback]`
- `test_dispatch_compensation_always_removes_object_during_database_outage`
- `test_redis_rate_limits_have_headers_and_are_scoped_to_user[upload]`

The older upload tests received HTTP 429 instead of their expected validation or failure responses. The new rate-limit upload test received HTTP 503 instead of HTTP 202. No real provider request or new credential was used; provider integration tests used controlled SDK HTTP transports and the existing local database.
