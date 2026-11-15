from datetime import datetime
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
    password: str | None = None
    role: str = "user"


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionProfileResponse(BaseModel):
    message: str
    user_id: int
    role: str
    tenant_id: str
    created_at: str


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


class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: str
    average_order_value: str


class DashboardStatsResponse(BaseModel):
    source: str
    stats: DashboardStats


class OrderCreate(BaseModel):
    tenant_id: str
    total_amount: float
    status: str = "completed"
    created_at: datetime | None = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    total_amount: float
    status: str
    created_at: datetime
