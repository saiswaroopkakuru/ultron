---
name: verification-loop
description: Multi-phase verification system checking build, types, linter, tests, and security secrets before declaring completion.
license: MIT
---

# Verification Loop Protocol

Comprehensive quality gates to verify code before marking tasks complete or creating pull requests.

## 6 Verification Phases

### Phase 1: Build Verification
```bash
npm run build || python -m compileall . || cargo check
```
If build fails, STOP and fix immediately.

### Phase 2: Type Check
```bash
npx tsc --noEmit || pyright . || mypy .
```
Fix all introduced type violations.

### Phase 3: Lint Check
```bash
npm run lint || ruff check . || flake8 .
```

### Phase 4: Test Suite & Coverage
```bash
pytest --cov || npm test -- --coverage
```
Verify tests pass and 80%+ coverage is maintained.

### Phase 5: Security & Secret Scan
Ensure no API keys (`sk-...`), private keys, or `.env` secrets are staged or printed.

### Phase 6: Surgical Diff Review
```bash
git diff --stat
```
Verify zero unintended side-effects or adjacent code churn.
