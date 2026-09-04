import sys
import os
import shlex
import subprocess
from ultron.core.pruner import pruner
from ultron.core.breadcrumb import breadcrumb_store

def run():
    """
    Ultron Command Runner.
    Executes a shell command cross-platform (PowerShell/cmd/bash),
    captures its stdout and stderr, prunes repetitive noise, stashes
    the byte-exact original into SQLite breadcrumbs, and prints the
    compacted output to stdout with the original return code.
    """
    if len(sys.argv) < 2:
        sys.exit(0)

    # Reconstruct command preserving quoted arguments
    args = sys.argv[2:] if sys.argv[1] == "--" else sys.argv[1:]
    raw_cmd = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)

    if not raw_cmd.strip():
        sys.exit(0)

    try:
        proc = subprocess.run(
            raw_cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        sys.stderr.write(f"[ultron-runner-err] {e}\n")
        sys.exit(1)

    combined_output = proc.stdout or ""
    if proc.stderr:
        if combined_output and not combined_output.endswith("\n"):
            combined_output += "\n"
        combined_output += proc.stderr

    # If output is trivial or very short (< 120 bytes), print verbatim
    if len(combined_output) < 120:
        sys.stdout.write(combined_output)
        sys.stdout.flush()
        sys.exit(proc.returncode)

    pruned, meta = pruner.prune_tool_output(combined_output)
    sys.stdout.write(pruned)
    sys.stdout.flush()
    sys.exit(proc.returncode)

if __name__ == "__main__":
    run()
