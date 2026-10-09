from datetime import datetime
from pydantic import BaseModel, Field

class GameStartResponse(BaseModel):
    gameId: str

class ScoreSubmitRequest(BaseModel):
    score: int = Field(..., ge=0)
    player_name: str = Field(..., min_length=1, max_length=50)

class HighScoreOut(BaseModel):
    id: int
    player_name: str
    score: int
    created_at: datetime

    class Config:
        orm_mode = True
