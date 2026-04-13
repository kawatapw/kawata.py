"""
Encryption Module - AES Encryption for Score Data Security

This module provides AES encryption and decryption functionality for securing
score data transmission between the osu! client and server. It implements
Rijndael CBC encryption with PKCS7 padding to protect sensitive gameplay
data from interception.

The module handles the encryption and decryption of score submission data
using a combination of osu! version-specific keys and initialization vectors.
This ensures that score data remains confidential during transmission
between the client and server. Note that CBC mode provides confidentiality
only, NOT integrity or authentication — it does not prevent tampering
(e.g., bit-flipping attacks). If tamper-protection is required, HMAC
verification should be added on top of the encrypted payload.

Key Features:
    - AES encryption using Rijndael CBC mode
    - PKCS7 padding for block cipher compatibility
    - Base64 encoding for safe data transmission
    - Version-specific encryption keys
    - Score data and client hash encryption
    - Secure data serialization and deserialization

Integration Points:
    - Score submission in app/api/domains/osu.py
    - Client authentication in app/api/domains/cho.py
    - Anti-cheat validation in app/constants/clientflags.py
    - Score processing in app/objects/score.py

Encryption Process:
    1. Score data is joined with colons as delimiters
    2. Data is encrypted using Rijndael CBC with version-specific key
    3. Encrypted data is base64 encoded for transmission
    4. Client hash is encrypted separately for validation
    5. Both encrypted values are returned for client submission

Decryption Process:
    1. Base64 encoded data is decoded
    2. Data is decrypted using Rijndael CBC with version-specific key
    3. Decrypted data is split by colons to reconstruct score data
    4. Client hash is decrypted for validation
    5. Both values are returned for processing

Security Considerations:
    - CBC mode provides confidentiality only, NOT integrity or authentication.
      It is vulnerable to bit-flipping attacks. HMAC verification should be
      added if tamper-protection is required.
    - Version-specific keys prevent cross-version data reuse
    - Initialization vectors ensure unique ciphertext for each submission
    - PKCS7 padding provides proper block alignment
    - Base64 encoding ensures safe transmission over HTTP

Usage Pattern:
    # Encrypt score data for client submission
    score_data_b64, client_hash_b64 = encrypt_score_aes_data(
        score_data=["12345", "95.5", "1000000"],
        client_hash="abc123...",
        iv_b64=b"base64_encoded_iv",
        osu_version="20231215"
    )

    # Decrypt score data from client submission
    score_data, client_hash = decrypt_score_aes_data(
        score_data_b64=b"base64_encoded_score",
        client_hash_b64=b"base64_encoded_hash",
        iv_b64=b"base64_encoded_iv",
        osu_version="20231215"
    )

Related Files:
    - app/api/domains/osu.py: Score submission handling
    - app/objects/score.py: Score data processing
    - app/constants/clientflags.py: Anti-cheat validation
    - app/settings.py: Encryption configuration
"""

from __future__ import annotations

from base64 import b64decode, b64encode

from py3rijndael import Pkcs7Padding, RijndaelCbc


def encrypt_score_aes_data(
    # to encode
    score_data: list[str],
    client_hash: str,
    # used for encoding
    iv_b64: bytes,
    osu_version: str,
) -> tuple[bytes, bytes]:
    """Encrypt the score data to base64.

    This function encrypts score submission data and client hash using
    AES encryption with Rijndael CBC mode. The encryption uses a version-
    specific key derived from the osu! version string.

    Args:
        score_data: List of score data strings to encrypt
        client_hash: Client hash string to encrypt
        iv_b64: Base64 encoded initialization vector
        osu_version: osu! version string for key derivation

    Returns:
        Tuple of (encrypted_score_data, encrypted_client_hash) as base64 bytes
    """
    # TODO: perhaps this should return TypedDict?

    # attempt to encrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_version}".encode(),
        iv=b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    score_data_joined = ":".join(score_data)
    score_data_b64 = b64encode(aes.encrypt(score_data_joined.encode()))
    client_hash_b64 = b64encode(aes.encrypt(client_hash.encode()))

    return score_data_b64, client_hash_b64


def decrypt_score_aes_data(
    # to decode
    score_data_b64: bytes,
    client_hash_b64: bytes,
    # used for decoding
    iv_b64: bytes,
    osu_version: str,
) -> tuple[list[str], str]:
    """Decrypt the base64'ed score data.

    This function decrypts score submission data and client hash from
    base64 encoded encrypted data. The decryption uses a version-specific
    key derived from the osu! version string.

    Args:
        score_data_b64: Base64 encoded encrypted score data
        client_hash_b64: Base64 encoded encrypted client hash
        iv_b64: Base64 encoded initialization vector
        osu_version: osu! version string for key derivation

    Returns:
        Tuple of (score_data_list, client_hash_string)
    """
    # TODO: perhaps this should return TypedDict?

    # attempt to decrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_version}".encode(),
        iv=b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    score_data = aes.decrypt(b64decode(score_data_b64)).decode().split(":")
    client_hash_decoded = aes.decrypt(b64decode(client_hash_b64)).decode()

    # score data is delimited by colons (:).
    return score_data, client_hash_decoded
