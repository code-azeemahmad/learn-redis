from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    full_name = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="user")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(50), nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), nullable=False)


