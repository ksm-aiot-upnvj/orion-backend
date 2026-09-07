import uuid

from pydantic import BaseModel, ConfigDict


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
    full_name: str | None = None
    email: str | None = None
    avatar: str | None = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
