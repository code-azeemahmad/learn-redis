from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    price: float
    category: str
    is_featured: bool = False


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    category: str
    is_featured: bool = False


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    created_at: datetime
