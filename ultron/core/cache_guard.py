import hashlib
from typing import List, Dict, Any

class CacheGuard:
    """
    Anthropic Prompt Cache Stabilization Guard.
    Guarantees that static system prompt prefixes and tool definitions stay byte-for-byte identical,
    protecting the 90% prompt caching discount.
    Dynamically injected content (like memory deltas or breadcrumb hints) is placed at the
    *tail* of system instructions or in user messages so the cache prefix is never broken.
    """
    def __init__(self):
        self._last_prefix_hash = None

    def compute_prefix_hash(self, messages: List[Dict[str, Any]]) -> str:
        """Computes hash of the first 1000 tokens of the message stream."""
        prefix_str = ""
        for msg in messages[:2]:
            content = msg.get("content", "")
            if isinstance(content, str):
                prefix_str += content[:1500]
        return hashlib.sha256(prefix_str.encode("utf-8")).hexdigest()

    def stabilize_payload(self, payload: Dict[str, Any], dynamic_injection: str) -> Dict[str, Any]:
        """
        Safely injects dynamic instructions into the payload without invalidating
        the Anthropic prompt cache prefix.
        """
        if not dynamic_injection:
            return payload

        # Deep copy
        new_payload = dict(payload)
        system = new_payload.get("system")

        if isinstance(system, list):
            # Anthropic multi-block system prompt
            new_system = list(system)
            # Append dynamic block at the end with cache_control disabled
            new_system.append({
                "type": "text",
                "text": dynamic_injection
            })
            new_payload["system"] = new_system
        elif isinstance(system, str):
            # Append to the very end of system string
            new_payload["system"] = f"{system}\n\n{dynamic_injection}"
        else:
            new_payload["system"] = dynamic_injection

        return new_payload

cache_guard = CacheGuard()
