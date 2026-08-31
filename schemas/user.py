import uuid

from pydantic import BaseModel, ConfigDict

from models.enums import Division


class UserBase(BaseModel):
    student_id: str
    full_name: str
    email: str
    role: str = "PENGURUS"
    division: Division | None = None
    avatar: str | None = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    password: str | None = None
    role: str | None = None
    division: Division | None = None
    avatar: str | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

