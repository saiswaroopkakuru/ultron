import re
from typing import Tuple, Dict, Any

FLUFF_PATTERNS = [
    r"\b(Sure|Certainly|Absolutely),?\s+(I would be happy to|I can help with that|here is the|here are the)\b.*?:",
    r"\bAs an AI language model,?\b",
    r"\bPlease let me know if (you need anything else|you have any other questions|this helps)\.?\b",
    r"\bI hope this (helps|solution works for you)\.?\b",
    r"\bIn order to (solve|fix|implement|address) this,?\b",
    r"\bLet's (take a look at|break down|examine|dive into) (the|how)\b.*?:",
    r"\bFeel free to (ask|reach out) if\b.*?:?",
    r"\bDon't hesitate to ask if you have any questions\.?\b",
    r"\bWithout further ado,?\b",
    r"\bTo summarize,?\b",
    r"\bIn conclusion,?\b",
    r"\bHere is the updated (code|file|implementation):?\b",
]

COMPILED_FLUFF = [re.compile(p, re.IGNORECASE) for p in FLUFF_PATTERNS]

CAVEMAN_SYSTEM_DIRECTIVE = """[ULTRON CAVEMAN PROTOCOL ACTIVE]
Rules for zero-waste high-precision communication:
1. Speak telegraphic, direct, information-dense. Eliminate conversational filler, pleasantries, apologies, and framing remarks.
2. CODE IS SACRED: All code blocks, patches, variable names, file paths, line numbers, and API schemas MUST REMAIN 100% BYTE-EXACT and complete. Never abbreviate code logic or identifiers.
3. Use bullet points and concise technical directives instead of narrative paragraphs."""

class CavemanCompressor:
    def __init__(self, mode: str = "adaptive"):
        self.mode = mode

    def get_system_prompt_directive(self) -> str:
        if self.mode == "off":
            return ""
        return CAVEMAN_SYSTEM_DIRECTIVE.strip()

    def compress_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        if self.mode == "off" or not text:
            return text, {"savings_pct": 0.0, "raw_len": len(text), "comp_len": len(text)}

        raw_len = len(text)

        code_blocks = []
        def _save_block(m):
            code_blocks.append(m.group(0))
            return f"__ULTRON_CODE_BLOCK_{len(code_blocks)-1}__"

        protected_text = re.sub(r"```[\s\S]*?```", _save_block, text)

        inline_blocks = []
        def _save_inline(m):
            inline_blocks.append(m.group(0))
            return f"__ULTRON_INLINE_{len(inline_blocks)-1}__"
        protected_text = re.sub(r"`[^`\r\n]+`", _save_inline, protected_text)

        compressed_prose = protected_text
        for pattern in COMPILED_FLUFF:
            compressed_prose = pattern.sub("", compressed_prose)

        compressed_prose = re.sub(r"\n{3,}", "\n\n", compressed_prose).strip()

        if self.mode == "ultra":
            ultra_subs = [
                (r"\bYou should\b", "Must"),
                (r"\bYou can\b", "Can"),
                (r"\bIn order to\b", "To"),
                (r"\bIt is recommended that you\b", "Recommend:"),
                (r"\bNote that\b", "Note:"),
                (r"\bMake sure that you\b", "Ensure"),
            ]
            for pat, repl in ultra_subs:
                compressed_prose = re.sub(pat, repl, compressed_prose, flags=re.IGNORECASE)

        for i, code in enumerate(inline_blocks):
            compressed_prose = compressed_prose.replace(f"__ULTRON_INLINE_{i}__", code)

        for i, code in enumerate(code_blocks):
            compressed_prose = compressed_prose.replace(f"__ULTRON_CODE_BLOCK_{i}__", code)

        comp_len = len(compressed_prose)
        savings = max(0.0, (raw_len - comp_len) / raw_len * 100) if raw_len > 0 else 0.0

        return compressed_prose, {
            "mode": self.mode,
            "raw_len": raw_len,
            "comp_len": comp_len,
            "savings_pct": savings
        }

caveman = CavemanCompressor()
