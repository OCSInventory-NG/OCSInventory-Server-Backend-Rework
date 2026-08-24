import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

# A Fernet token is urlsafe base64 data whose first byte is the 0x80 version
# marker, which always produces this prefix.
FERNET_PREFIX = "gAAAAA"


def _get_fernet():
    """
    Build a Fernet instance from FIELD_ENCRYPTION_KEY.

    Return None and log the reason when the key is missing or unusable, so that
    the application keeps running instead of failing at import time.
    """
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        logger.error(
            "FIELD_ENCRYPTION_KEY is not set: sensitive configuration values "
            "are left unencrypted"
        )
        return None
    try:
        return Fernet(key)
    except (TypeError, ValueError):
        logger.error(
            "FIELD_ENCRYPTION_KEY is not a valid Fernet key: sensitive "
            "configuration values can neither be encrypted nor decrypted"
        )
        return None


def is_encrypted(value):
    """Tell whether a value has already been encrypted by this module."""
    return isinstance(value, str) and value.startswith(FERNET_PREFIX)


def encrypt(value):
    """
    Encrypt a string value.

    Empty values, non string values and already encrypted values are returned
    unchanged, which makes the function safe to apply twice.
    """
    if not isinstance(value, str) or not value or is_encrypted(value):
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    return fernet.encrypt(value.encode()).decode()


def decrypt(value):
    """
    Decrypt a value encrypted by this module.

    Values that were never encrypted are returned unchanged, so a database
    holding both encrypted and clear text values stays readable.
    """
    if not is_encrypted(value):
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        logger.error(
            "A sensitive configuration value cannot be decrypted with the "
            "current FIELD_ENCRYPTION_KEY"
        )
        return value
