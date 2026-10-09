import os
import uuid
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import HighScore
from schemas import (
    GameStartResponse,
    ScoreSubmitRequest,
    HighScoreOut,
)

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI()

API_KEY = os.getenv("API_KEY", "secret")

@app.post("/games/start", response_model=GameStartResponse)
def start_game():
    game_id = str(uuid.uuid4())
    return GameStartResponse(gameId=game_id)

@app.post("/games/{game_id}/score", response_model=HighScoreOut)
def submit_score(
    game_id: str,
    payload: ScoreSubmitRequest,
    db: Session = Depends(get_db),
):
    # game_id is only used for client tracking; no validation needed
    high_score = HighScore(
        player_name=payload.player_name,
        score=payload.score,
        created_at=datetime.utcnow(),
    )
    db.add(high_score)
    db.commit()
    db.refresh(high_score)
    return high_score

@app.get("/highscores", response_model=list[HighScoreOut])
def list_highscores(db: Session = Depends(get_db)):
    scores = (
        db.query(HighScore)
        .order_by(HighScore.score.desc(), HighScore.created_at.asc())
        .limit(10)
        .all()
    )
    return scores

@app.delete("/highscores/{score_id}")
def delete_highscore(
    score_id: int,
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    score = db.query(HighScore).filter(HighScore.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")
    db.delete(score)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)
