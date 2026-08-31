from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordConfirmRequest(BaseModel):
    password: str


class TwoFactorVerifyRequest(BaseModel):
    code: str


class PinLoginRequest(BaseModel):
    pin: str


class DeviceTrustEnrollRequest(BaseModel):
    pin: str
    device_label: str | None = None


class TotpEnrollConfirmRequest(BaseModel):
    code: str
