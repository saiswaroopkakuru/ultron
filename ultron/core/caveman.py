import re
from typing import Tuple, Dict, Any

FLUFF_PATTERNS = [
    # Conversational pleasantries & throat-clearing sentences
    r"\b(Sure|Certainly|Absolutely|Of course)[!,]?\s+(I would be happy to|I can help with that|here is the|here are the|let me help|let's look at)[^.!?\n]*[.!?]?",
    r"\bAs an AI (language model|assistant)[^.!?\n]*[.!?]?",
    r"\bPlease let me know if (you need anything else|you have any other questions|this helps|there is anything else)[^.!?\n]*[.!?]?",
    r"\bI hope this (helps|solution works for you|information is useful)[^.!?\n]*[.!?]?",
    r"\bFeel free to (ask|reach out|let me know) if[^.!?\n]*[.!?]?",
    r"\bDon't hesitate to (ask|reach out) if you have any questions[^.!?\n]*[.!?]?",
    r"\bWithout further ado,?\b",
    r"\bTo summarize,?\b",
    r"\bIn conclusion,?\b",
    r"\bHere is (a breakdown|a summary|an explanation|the updated code|the implementation):?\b",
    r"\bIn order to (understand|solve|fix|implement|address|achieve) this,?\b",
    r"\bIt is (important|crucial|worth noting|essential) to (remember|note|keep in mind|understand) that\b",
    r"\bFurthermore,?\s+(it should be noted that|it is worth mentioning that)\b",
    r"\bAs (mentioned|stated|discussed) (previously|earlier|above),?\b",
    r"\bAt the end of the day,?\b",
    r"\bAll things considered,?\b",
]

COMPILED_FLUFF = [re.compile(p, re.IGNORECASE) for p in FLUFF_PATTERNS]

WORDY_PHRASES = [
    (r"\bdue to the fact that\b", "because"),
    (r"\bfor the purpose of\b", "for"),
    (r"\bin the event that\b", "if"),
    (r"\bwith reference to\b", "regarding"),
    (r"\bwith regard to\b", "regarding"),
    (r"\bin close proximity to\b", "near"),
    (r"\bat this point in time\b", "currently"),
    (r"\bat the present time\b", "currently"),
    (r"\ba large number of\b", "many"),
    (r"\ba majority of\b", "most"),
    (r"\bin spite of the fact that\b", "although"),
    (r"\btake into consideration\b", "consider"),
    (r"\bhas the ability to\b", "can"),
    (r"\bis capable of\b", "can"),
    (r"\bconduct an investigation into\b", "investigate"),
    (r"\bmake an assumption that\b", "assume"),
    (r"\bprovide an explanation of\b", "explain"),
    (r"\bgive an indication of\b", "indicate"),
    (r"\bdraw your attention to\b", "note"),
    (r"\bit is recommended that you\b", "recommend:"),
    (r"\bmake sure that you\b", "ensure"),
]

COMPILED_WORDY = [(re.compile(p, re.IGNORECASE), r) for p, r in WORDY_PHRASES]

CAVEMAN_SYSTEM_DIRECTIVE = """[ULTRON UNIVERSAL HIGH-DENSITY PROTOCOL ACTIVE]
Universal rules for zero-waste, high-precision communication across ALL queries:
1. TELEGRAPHIC & DIRECT: Eliminate conversational filler ("Certainly!", "I'd be glad to help", "Hope this helps"), preambles, apologies, and framing remarks. Start directly with the substance.
2. DENSE PROSE: Convey maximal technical/factual information in minimal words. Use bullet points and structured summaries. Cut verbose passive phrasing into active directives.
3. 100% PRESERVATION: Never drop, truncate, or alter facts, numbers, dates, links, entity names, formulas, code blocks, filepaths, line numbers, or APIs. Precision is sacred.
4. BREADCRUMBS: When referencing stashed context, preserve the [ultron:ref:hash:NL:NB] reference tag intact."""

class CavemanCompressor:
    """
    Universal High-Density Text & Prose Optimizer.
    Compresses conversational text, technical explanations, articles, and prose
    by removing fluff, passive boilerplate, and padding while preserving 100%
    of facts, code, and entities.
    """
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

        # 1. Protect code blocks from any modification
        code_blocks = []
        def _save_block(m):
            code_blocks.append(m.group(0))
            return f"__ULTRON_CODE_BLOCK_{len(code_blocks)-1}__"

        protected_text = re.sub(r"```[\s\S]*?```", _save_block, text)

        # 2. Protect inline code
        inline_blocks = []
        def _save_inline(m):
            inline_blocks.append(m.group(0))
            return f"__ULTRON_INLINE_{len(inline_blocks)-1}__"
        protected_text = re.sub(r"`[^`\r\n]+`", _save_inline, protected_text)

        # 3. Protect URLs and links
        urls = []
        def _save_url(m):
            urls.append(m.group(0))
            return f"__ULTRON_URL_{len(urls)-1}__"
        protected_text = re.sub(r"https?://[^\s)\]]+", _save_url, protected_text)

        compressed_prose = protected_text

        # 4. Remove fluff and conversational throat-clearing
        for pattern in COMPILED_FLUFF:
            compressed_prose = pattern.sub("", compressed_prose)

        # 5. Compact wordy phrases into crisp equivalents
        for pattern, replacement in COMPILED_WORDY:
            compressed_prose = pattern.sub(replacement, compressed_prose)

        # 6. Normalize whitespace and paragraph spacing
        compressed_prose = re.sub(r"[ \t]+", " ", compressed_prose)
        compressed_prose = re.sub(r"\n[ \t]+", "\n", compressed_prose)
        compressed_prose = re.sub(r"\n{3,}", "\n\n", compressed_prose).strip()

        # 7. Restore protected artifacts exactly
        for i, url in enumerate(urls):
            compressed_prose = compressed_prose.replace(f"__ULTRON_URL_{i}__", url)

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
