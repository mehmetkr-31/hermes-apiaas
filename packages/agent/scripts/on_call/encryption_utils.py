import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hashlib

def _get_key():
    secret = os.getenv("DB_ENCRYPTION_KEY")
    if not secret:
        raise ValueError("DB_ENCRYPTION_KEY is not set in environment variables.")
    
    # Ensure 32 bytes via SHA256 (same as Node fallback or requirement)
    if len(secret.encode()) != 32:
        return hashlib.sha256(secret.encode()).digest()
    return secret.encode()

def encrypt(text: str) -> str:
    """
    Encrypts text using AES-256-GCM.
    Returns: base64(iv + tag + ciphertext)
    Note: cryptography's AESGCM.encrypt returns ciphertext + tag.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    # cryptography returns ciphertext + tag
    ct_with_tag = aesgcm.encrypt(iv, text.encode(), None)
    
    # We need to rearrange to match Node's iv + tag + ciphertext or keep it simple
    # Node: iv(12) + tag(16) + ct
    # Python: iv + (ct + tag)
    # Let's rearrange Python's output to match Node: iv + tag + ct
    tag = ct_with_tag[-16:]
    ct = ct_with_tag[:-16]
    
    combined = iv + tag + ct
    return base64.b64encode(combined).decode('utf-8')

def decrypt(hash_str: str) -> str:
    """
    Decrypts base64(iv + tag + ciphertext) hash using AES-256-GCM.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    data = base64.b64decode(hash_str)
    
    iv = data[:12]
    tag = data[12:28]
    ct = data[28:]
    
    # Reassemble for cryptography (ct + tag)
    ct_with_tag = ct + tag
    
    decrypted = aesgcm.decrypt(iv, ct_with_tag, None)
    return decrypted.decode('utf-8')
