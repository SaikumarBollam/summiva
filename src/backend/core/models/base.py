from tokenize import String
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class BaseModel(Base):
    """Abstract base model with common fields."""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())