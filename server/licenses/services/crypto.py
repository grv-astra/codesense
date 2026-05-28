# licenses/services/crypto.py
import os
import base64
import secrets
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# -------------------------
# 🔑 Key Management
# -------------------------

def generate_keypair():
    """Generate a new Ed25519 keypair."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def save_private_key(private_key, path: str, password: str | None = None):
    """Save private key to file."""
    enc = serialization.NoEncryption()
    if password:
        enc = serialization.BestAvailableEncryption(password.encode())
    with open(path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=enc,
            )
        )


def save_public_key(public_key, path: str):
    """Save public key to file."""
    with open(path, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )


def load_private_key(path: str, password: str | None = None):
    """Load private key from PEM file."""
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=password)


def load_public_key(path: str):
    """Load public key from PEM file."""
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


# -------------------------
# 🔒 Signing & Verification
# -------------------------

def sign_message(private_key, message: bytes) -> str:
    """Sign a message with private key → return base64 signature."""
    signature = private_key.sign(message)
    return base64.b64encode(signature).decode()


def verify_signature(public_key, message: bytes, signature: str) -> bool:
    """Verify base64 signature against public key."""
    try:
        public_key.verify(base64.b64decode(signature), message)
        return True
    except InvalidSignature:
        return False


# -------------------------
# 🔑 Nonce Helpers
# -------------------------

def random_nonce(length: int = 32) -> str:
    """Generate random nonce (base64)."""
    return base64.b64encode(secrets.token_bytes(length)).decode()


# -------------------------
# 🛠️ Local Convenience
# -------------------------

def sign_nonce(private_key, nonce: str) -> str:
    """Sign nonce string using Local private key."""
    return sign_message(private_key, nonce.encode())


def verify_nonce(public_key, nonce: str, signed_nonce: str) -> bool:
    """Verify signed nonce using Local public key."""
    return verify_signature(public_key, nonce.encode(), signed_nonce)
