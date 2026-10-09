import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app, get_db
from database import Base

# Override the database URL for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in the in‑memory database
Base.metadata.create_all(bind=engine)

# Dependency override

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Set a known API key for tests
os.environ["API_KEY"] = "testkey"

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

# Helper to create a score

def create_score(client, score, player_name="Tester"):
    response = client.post(
        f"/games/{uuid.uuid4()}/score",
        json={"score": score, "player_name": player_name},
    )
    assert response.status_code == 200
    return response.json()


def test_start_game(client):
    response = client.post("/games/start")
    assert response.status_code == 200
    data = response.json()
    assert "gameId" in data
    uuid_obj = uuid.UUID(data["gameId"])
    assert str(uuid_obj) == data["gameId"]


def test_submit_score(client):
    score_data = create_score(client, 1500, "Alice")
    assert score_data["player_name"] == "Alice"
    assert score_data["score"] == 1500
    assert "id" in score_data
    assert "created_at" in score_data


def test_get_highscores(client):
    # Create 12 scores
    for i in range(12):
        create_score(client, 1000 + i * 10, f"Player{i}")
    response = client.get("/highscores")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    # Verify ordering by score descending
    scores = [item["score"] for item in data]
    assert scores == sorted(scores, reverse=True)


def test_delete_score(client):
    # Create a score to delete
    score = create_score(client, 2000, "ToDelete")
    score_id = score["id"]
    # Attempt delete without API key
    r = client.delete(f"/highscores/{score_id}")
    assert r.status_code == 422  # missing header
    # Delete with wrong key
    r = client.delete(
        f"/highscores/{