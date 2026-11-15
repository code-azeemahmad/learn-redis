import hashlib
import json


def generate_llm_cache_key(
    prompt: str,
    model: str,
    system_prompt: str,
    temperature: float
) -> str:
    """
    Generates a deterministic, canonical SHA-256 cache key for LLM queries.
    Sorting keys and specifying compact separators ensures equivalent inputs
    always produce identical hashes regardless of dict key ordering.
    """
    request_data = {
        "prompt": prompt.strip(),
        "model": model.strip(),
        "system_prompt": system_prompt.strip(),
        "temperature": round(temperature, 4)
    }
    canonical_data = json.dumps(
        request_data,
        sort_keys=True,
        separators=(",", ":")
    )
    request_hash = hashlib.sha256(
        canonical_data.encode("utf-8")
    ).hexdigest()
    return f"v1:llm:{request_hash}"
