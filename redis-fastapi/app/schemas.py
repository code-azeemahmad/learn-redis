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


class ProductListResponse(BaseModel):
    source: str
    page: int
    limit: int
    total: int
    pages: int
    products: list[ProductResponse]


class UserCreate(BaseModel):
    tenant_id: str
    username: str
    email: str
    full_name: str


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    full_name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    username: str
    email: str
    full_name: str
