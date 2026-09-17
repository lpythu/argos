import secrets
import string

SID_LEN = 12
_ALPHABET = string.ascii_lowercase + string.digits


def new_sid() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(SID_LEN))
