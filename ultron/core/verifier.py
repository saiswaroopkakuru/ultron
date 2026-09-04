import re
import ast
from typing import Dict, Any, List
from rapidfuzz import fuzz

class PrecisionVerifier:
    def extract_symbols(self, text: str) -> List[str]:
        identifiers = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", text))
        paths = set(re.findall(r"[\w\.-]+/[\w\.-]+|[\w\.-]+\\+[\w\.-]+", text))
        lines = set(re.findall(r":\d+", text))
        return list(identifiers.union(paths).union(lines))

    def extract_code_blocks(self, text: str) -> List[str]:
        return re.findall(r"```(?:[a-zA-Z0-9_]*\n)?([\s\S]*?)```", text)

    def verify_python_syntax(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def verify(self, baseline_text: str, compressed_text: str) -> Dict[str, Any]:
        base_len = len(baseline_text)
        comp_len = len(compressed_text)
        savings_pct = max(0.0, (base_len - comp_len) / base_len * 100) if base_len > 0 else 0.0

        base_symbols = set(self.extract_symbols(baseline_text))
        comp_symbols = set(self.extract_symbols(compressed_text))

        base_code_blocks = self.extract_code_blocks(baseline_text)
        comp_code_blocks = self.extract_code_blocks(compressed_text)

        code_symbol_total = 0
        code_symbol_preserved = 0

        for block in base_code_blocks:
            symbols = set(self.extract_symbols(block))
            code_symbol_total += len(symbols)
            for s in symbols:
                if s in comp_symbols:
                    code_symbol_preserved += 1

        code_precision = (code_symbol_preserved / code_symbol_total * 100) if code_symbol_total > 0 else 100.0
        fuzzy_sim = fuzz.token_set_ratio(baseline_text, compressed_text)

        syntax_valid = True
        for block in comp_code_blocks:
            if any(k in block for k in ["def ", "import ", "class ", "return "]):
                if not self.verify_python_syntax(block):
                    syntax_valid = False
                    break

        return {
            "baseline_bytes": base_len,
            "compressed_bytes": comp_len,
            "token_reduction_pct": round(savings_pct, 2),
            "code_precision_pct": round(code_precision, 2),
            "fuzzy_similarity_pct": round(fuzzy_sim, 2),
            "syntax_valid": syntax_valid,
            "is_precision_passed": code_precision >= 98.0 and syntax_valid
        }

verifier = PrecisionVerifier()
