from pydantic import BaseModel, EmailStr, Field


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
    # This PIN is a real auth factor — it bypasses password+2FA on a trusted device — so a
    # 1-2 digit PIN would meaningfully weaken security even with the attempt lockout.
    pin: str = Field(min_length=4, max_length=16)
    device_label: str | None = None


class TotpEnrollConfirmRequest(BaseModel):
    code: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
