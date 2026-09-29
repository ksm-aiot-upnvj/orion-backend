import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from utils.security import validate_new_password

NewPassword = Annotated[str, AfterValidator(validate_new_password)]


class LoginRequest(BaseModel):
    student_id: str  # NIM or Email
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_id: uuid.UUID | None = None
    student_id: str
    full_name: str
    email: str
    role: str
    division: str | None = None
    avatar: str | None = None
    is_superadmin: bool = False
    is_active: bool

class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = Field(default=None, max_length=150)
    avatar: str | None = Field(default=None, max_length=255)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: NewPassword

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserOut


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserOut | None = None
