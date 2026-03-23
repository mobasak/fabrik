"""Scenario 06: Database schema change."""

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    status = Column(String(50), default="pending")
