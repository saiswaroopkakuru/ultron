import os

BASE = os.path.dirname(__file__)

# 1. Heavy Terminal Build Log (Webpack/TypeScript/PyTest with noise)
build_log_lines = [
    "webpack 5.88.2 compiled with 12 warnings in 4120 ms",
    "chunk (runtime: main) 420.js (vendor) 2.4 MiB [rendered]",
    "chunk (runtime: main) main.js (main) 140 KiB [rendered]",
]
for i in range(150):
    build_log_lines.append(f"[info] [webpack-dev-server] Processing module {i}/150... [100%] unchanged")
    build_log_lines.append(f"DEBUG 2026-09-03 20:00:{i%60:02d} [telemetry] Heartbeat ping {i*10}ms ok")

build_log_lines.extend([
    "=================================== FAILURES ===================================",
    "_________________________ test_payment_webhook_auth __________________________",
    "def test_payment_webhook_auth(client):",
    ">       resp = client.post('/api/webhook/stripe', headers={'X-Signature': 'invalid'})",
    "E       AssertionError: assert 200 == 401",
    "E        +  where 200 = <Response [200 OK]>.status_code",
    "tests/test_webhook.py:48: AssertionError",
    "----------------------------- Captured stderr call -----------------------------",
    "ERROR:stripe_listener: Signature verification failed: Bad HMAC",
    "=========================== short test summary info ============================",
    "FAILED tests/test_webhook.py::test_payment_webhook_auth - AssertionError: assert 200 == 401",
    "======================== 1 failed, 149 passed in 4.21s ========================"
])

with open(os.path.join(BASE, "terminal_build_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(build_log_lines))

# 2. Large Git Diff with unchanged chunks
diff_lines = [
    "diff --git a/src/auth/jwt.py b/src/auth/jwt.py",
    "index a4b3c2d..e5f6a7b 100644",
    "--- a/src/auth/jwt.py",
    "+++ b/src/auth/jwt.py",
    "@@ -10,25 +10,25 @@ import jwt",
    " from datetime import datetime, timedelta",
    " from src.config import settings",
]
for j in range(40):
    diff_lines.append(f" def helper_check_salt_{j}(): return True")

diff_lines.extend([
    "-def verify_token(token: str) -> dict:",
    "-    return jwt.decode(token, 'old_insecure_key', algorithms=['HS256'])",
    "+def verify_token(token: str) -> dict:",
    "+    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])",
])

for j in range(60):
    diff_lines.append(f" def unused_validator_{j}(): pass")

with open(os.path.join(BASE, "large_git_diff.patch"), "w", encoding="utf-8") as f:
    f.write("\n".join(diff_lines))

print("Benchmark dataset generated.")
