"""A tiny software WebAuthn authenticator for tests: produces the same JSON a browser would
send back from navigator.credentials.create()/get(), so py_webauthn's real verification runs
instead of being mocked out. ES256 keys, "none" attestation, user presence + verification set.
"""

import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url

FLAG_UP = 0x01
FLAG_UV = 0x04
FLAG_AT = 0x40


class SoftAuthenticator:
    def __init__(self, rp_id: str = "localhost", origin: str = "http://localhost"):
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.sign_count = 0
        self.user_handle: bytes | None = None

    @property
    def credential_id_b64(self) -> str:
        return bytes_to_base64url(self.credential_id)

    def _cose_public_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # crv: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def _rp_hash(self) -> bytes:
        return hashlib.sha256(self.rp_id.encode()).digest()

    def register(self, creation_options: dict, *, origin: str | None = None, user_verified: bool = True) -> dict:
        self.user_handle = _b64url_decode(creation_options["user"]["id"])
        client_data = json.dumps(
            {
                "type": "webauthn.create",
                "challenge": creation_options["challenge"],
                "origin": origin or self.origin,
            }
        ).encode()
        flags = FLAG_UP | FLAG_AT | (FLAG_UV if user_verified else 0)
        auth_data = (
            self._rp_hash()
            + bytes([flags])
            + struct.pack(">I", 0)
            + bytes(16)  # AAGUID
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_public_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": self.credential_id_b64,
            "rawId": self.credential_id_b64,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def assert_(
        self,
        request_options: dict,
        *,
        origin: str | None = None,
        user_verified: bool = True,
        sign_count: int | None = None,
    ) -> dict:
        self.sign_count = self.sign_count + 1 if sign_count is None else sign_count
        client_data = json.dumps(
            {
                "type": "webauthn.get",
                "challenge": request_options["challenge"],
                "origin": origin or self.origin,
            }
        ).encode()
        flags = FLAG_UP | (FLAG_UV if user_verified else 0)
        auth_data = self._rp_hash() + bytes([flags]) + struct.pack(">I", self.sign_count)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": self.credential_id_b64,
            "rawId": self.credential_id_b64,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(self.user_handle) if self.user_handle else None,
            },
            "clientExtensionResults": {},
        }


def _b64url_decode(value: str) -> bytes:
    import base64

    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
