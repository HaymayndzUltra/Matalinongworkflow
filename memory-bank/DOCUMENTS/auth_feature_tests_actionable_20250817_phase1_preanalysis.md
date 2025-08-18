# Pre-Analysis — Phase 1 (Task: auth_feature_tests_actionable_20250817)

Restating Phase 1 IMPORTANT NOTE and setup risks:
- Use pytest discovery; explicit fixtures and scopes.
- No real network/DB/file I/O in unit tests (mock).
- Keep skeletons minimal but runnable.

Prereqs:
- Confirm test file paths and discovery.
- Define shared fixtures (tmp_path, monkeypatch usage).
- Decide on mocking boundaries.
