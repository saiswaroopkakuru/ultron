import sys
import json
import os

def run_hook():
    """
    Ultron PostToolUse Hook for Claude Code.
    Intercepts Bash, Read, and Grep tool outputs before they enter LLM context.
    Matches Claude Code's exact Zod outputSchema (e.g. {stdout, stderr, interrupted} for Bash)
    so replacements are never rejected by e.outputSchema.safeParse().
    Stashes bulky logs, test runs, and diffs to SQLite breadcrumb store,
    returning a lightweight preview + [ultron:ref:hash:NL:NB] breadcrumb tag.
    Slashes real Claude Code context consumption by up to 95%.
    """
    try:
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            sys.exit(0)

        try:
            payload = json.loads(raw)
        except Exception:
            sys.exit(0)

        tool_name = payload.get("tool_name") or payload.get("toolName") or ""
        # Claude Code specifies either "response" or "tool_response" or "tool_output"
        tool_resp = (
            payload.get("response")
            or payload.get("tool_response")
            or payload.get("tool_output")
            or payload.get("toolResult")
        )

        if not tool_resp:
            sys.exit(0)

        # Extract text content from tool response
        output_text = ""
        is_dict = isinstance(tool_resp, dict)
        if is_dict:
            # Check for Read tool structure: { type: "text", file: { content: "..." } }
            if "file" in tool_resp and isinstance(tool_resp["file"], dict):
                output_text = tool_resp["file"].get("content", "")
            else:
                stdout = tool_resp.get("stdout") or tool_resp.get("output") or tool_resp.get("content") or ""
                stderr = tool_resp.get("stderr") or ""
                if stderr and stdout:
                    output_text = f"{stdout}\n{stderr}"
                elif stdout:
                    output_text = stdout
                elif stderr:
                    output_text = stderr
        elif isinstance(tool_resp, str):
            output_text = tool_resp
        else:
            output_text = str(tool_resp)

        # Skip compression for trivial or short outputs
        if len(output_text) < 350 and output_text.count("\n") < 15:
            sys.exit(0)

        # Don't re-compress if already contains an ultron breadcrumb
        if "[ultron:ref:" in output_text:
            sys.exit(0)

        # Import Ultron core compression engines
        from ultron.core.headroom import headroom
        from ultron.core.omniroute import omniroute

        compressed_text, meta = headroom.compress_tool_output(output_text)
        savings = meta.get("savings_pct", 0.0)

        # If significant savings achieved (> 15%)
        if savings > 15.0:
            raw_tokens = max(1, len(output_text) // 4)
            comp_tokens = max(1, len(compressed_text) // 4)
            omniroute.record_savings(raw_tokens, comp_tokens)

            # Construct schema-compliant replacement matching Claude Code's Zod schemas
            if tool_name == "Bash" or (is_dict and "stdout" in tool_resp):
                # Claude Code Bash outputSchema:
                # { stdout: string, stderr: string, interrupted: boolean, ... }
                updated_tool_resp = {
                    "stdout": compressed_text,
                    "stderr": tool_resp.get("stderr", "") if is_dict else "",
                    "interrupted": bool(tool_resp.get("interrupted", False)) if is_dict else False,
                }
                # Preserve optional background/task fields if present
                if is_dict:
                    for opt_key in ("backgroundTaskId", "rawOutputPath", "isImage"):
                        if opt_key in tool_resp:
                            updated_tool_resp[opt_key] = tool_resp[opt_key]

            elif tool_name == "Read" or (is_dict and "file" in tool_resp):
                # Claude Code Read outputSchema:
                # { type: "text", file: { filePath, content, numLines, startLine, totalLines } }
                if is_dict and isinstance(tool_resp.get("file"), dict):
                    file_obj = dict(tool_resp["file"])
                    file_obj["content"] = compressed_text
                    file_obj["numLines"] = compressed_text.count("\n") + 1
                    updated_tool_resp = {
                        "type": tool_resp.get("type", "text"),
                        "file": file_obj
                    }
                else:
                    updated_tool_resp = compressed_text

            elif is_dict:
                updated_tool_resp = dict(tool_resp)
                if "output" in updated_tool_resp:
                    updated_tool_resp["output"] = compressed_text
                elif "content" in updated_tool_resp:
                    updated_tool_resp["content"] = compressed_text
                elif "stdout" in updated_tool_resp:
                    updated_tool_resp["stdout"] = compressed_text
                else:
                    updated_tool_resp = compressed_text
            else:
                updated_tool_resp = compressed_text

            crumb = meta.get("breadcrumb", "")
            raw_bytes = meta.get("raw_bytes", len(output_text))
            comp_bytes = meta.get("compressed_bytes", len(compressed_text))
            
            notice = (
                f"[Ultron Active: Slashing {round(savings, 1)}% tokens ({raw_bytes:,}B -> {comp_bytes:,}B). "
                f"Full raw output safely stashed in SQLite as {crumb}. "
                f"To expand full uncompressed output, run `/ultron expand <hash>`]"
            )

            result_envelope = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "updatedToolOutput": updated_tool_resp,
                    "additionalContext": notice
                }
            }
            sys.stdout.write(json.dumps(result_envelope, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    except Exception as e:
        # Never break Claude Code on hook exception
        try:
            sys.stderr.write(f"[ultron-hook-warn] {e}\n")
        except Exception:
            pass
    finally:
        sys.exit(0)

if __name__ == "__main__":
    run_hook()
