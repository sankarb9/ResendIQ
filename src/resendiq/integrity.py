import hashlib

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def verify_text(original: str, reconstructed: str) -> bool:
    return sha256_text(original) == sha256_text(reconstructed)
