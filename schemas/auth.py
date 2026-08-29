import uuid

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    student_id: str  # NIM or Email
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: str
    full_name: str
    email: str
    role: str
    division: str
    avatar: str | None = None
    is_active: bool

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
