from sqlalchemy import Column, String, Text
from app.models.base import BaseModel

class Company(BaseModel):
    """企業情報モデル"""
    __tablename__ = "companies"

    name = Column(String(255), nullable=False, index=True)
    ticker_code = Column(String(10), nullable=False, unique=True, index=True)
    sector = Column(String(100))
    industry = Column(String(100))
    description = Column(Text)
    website_url = Column(String(255))
    
    def __repr__(self):
        return f"<Company(name={self.name}, ticker_code={self.ticker_code})>" 