---
name: security-guardrails
description: Shields credentials, detects leaked tokens, and validates sensitive production namespaces.
license: MIT
---

# Ultron Security Guardrails

1. **Never read or echo credential files**: `.env`, `.credentials.json`, `NTUSER.DAT`, `.gitconfig`.
2. **Never log sensitive tokens**: Intercept and mask `sk-`, `ghp_`, `Bearer`, and private keys.
3. **Prompt for destructive commands**: Require explicit user confirmation for `rm -rf`, `git push --force`, or dropping database tables.
