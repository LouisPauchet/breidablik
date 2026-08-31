import base64
import json
import secrets
from io import BytesIO

import pyotp
import qrcode
from fastapi_users.password import PasswordHelper

_password_helper = PasswordHelper()


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_qr_data_uri(secret: str, email: str, issuer: str = "Breidablik") -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)
    img = qrcode.make(uri)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([_password_helper.hash(code) for code in codes])


def verify_and_consume_recovery_code(code: str, hashed_codes_json: str | None) -> tuple[bool, str]:
    """Returns (matched, updated_hashed_codes_json). On a match, the used code is removed
    from the stored list so it can't be reused.
    """
    if not hashed_codes_json:
        return False, hashed_codes_json or "[]"

    hashed_codes: list[str] = json.loads(hashed_codes_json)
    for i, hashed in enumerate(hashed_codes):
        verified, _ = _password_helper.verify_and_update(code, hashed)
        if verified:
            remaining = hashed_codes[:i] + hashed_codes[i + 1 :]
            return True, json.dumps(remaining)
    return False, hashed_codes_json
