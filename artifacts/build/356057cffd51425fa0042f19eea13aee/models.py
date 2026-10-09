from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func

from database import Base

class HighScore(Base):
    __tablename__ = "high_scores"

    id = Column(Integer, primary_key=True, index=True)
    player_name = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.utcnow(), nullable=False)

    __table_args__ = (
        Index("idx_score", "score"),
    )
