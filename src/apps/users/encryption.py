# -*- coding: UTF-8 -*-
from django.conf import settings
from django.db import connection


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string using PostgreSQL pgcrypto.

    Uses pgp_sym_encrypt with AES-256 cipher.
    Returns base64-encoded encrypted data for storage in TextField.
    """
    if not plaintext:
        return ""

    key = settings.FIELD_ENCRYPTION_KEY
    with connection.cursor() as cursor:
        # Using AES-256 cipher for strong encryption
        cursor.execute(
            "SELECT encode(pgp_sym_encrypt(%s, %s, 'cipher-algo=aes256'), 'base64')",
            [plaintext, key],
        )
        return cursor.fetchone()[0]


def decrypt_value(encrypted: str) -> str:
    """
    Decrypt a string using PostgreSQL pgcrypto.

    Uses pgp_sym_decrypt to decrypt base64-encoded data.
    Returns plaintext string.
    """
    if not encrypted:
        return ""

    key = settings.FIELD_ENCRYPTION_KEY
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgp_sym_decrypt(decode(%s, 'base64'), %s)",
            [encrypted, key],
        )
        return cursor.fetchone()[0]
