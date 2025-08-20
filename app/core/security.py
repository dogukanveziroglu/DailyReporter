from __future__ import annotations
import os, hmac, hashlib

# Şema: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
_ALG = "pbkdf2_sha256"
_ITER = 390_000  # Python önerisi (3.12+) civarı

def hash_password(plain: str) -> str:
    if not isinstance(plain, str) or not plain:
        raise ValueError("Password must be non-empty string")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, _ITER)
    return f"{_ALG}${_ITER}${salt.hex()}${dk.hex()}"

def verify_password(plain: str, hashed: str) -> bool:
    try:
        alg, iter_s, salt_hex, hash_hex = hashed.split("$", 3)
        if alg != _ALG:
            return False
        iters = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iters)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False
