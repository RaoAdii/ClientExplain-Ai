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

## Follow-up: concurrent terminal replay

A deterministic two-session PostgreSQL test confirmed a remaining race in the first fix. A new submission holds the project row lock while its queued job is uncommitted. An old failed-job replay starts its project update and waits on that lock; `pg_blocking_pids` confirms the wait before the new submission commits. PostgreSQL retains the old statement snapshot for the newer-job existence check, allowing the waiting update to overwrite the committed queued status. The regression failed with actual status `failed` and expected status `queued` before the follow-up fix.

The terminal update now compares the project's observed `updated_at` and processing status. PostgreSQL rechecks these row predicates after a lock wait, preventing stale updates. On a conflict, terminal persistence checks for a newer analysis with a fresh snapshot. Unrelated concurrent edits are retried up to three times; continued contention rolls back the terminal transaction for existing durable recovery to retry.

Follow-up verification:

- Focused analysis, retrieval and worker tests: **115 passed**, including the two-session regression.
- Full backend suite: **347 passed, 1 failed**. The sole failure was Task 9's `test_expired_fixed_window_admits_again`: expected HTTP 429 for a second request, received HTTP 202. This result was sent to the Task 9 owner; no Task 9 files were changed for this fix.
- An immediate isolated rerun of `test_expired_fixed_window_admits_again`: **1 passed**. The full-suite failure remains recorded above.
- Full backend Ruff lint and formatting: **passed** (71 Python files formatted).
