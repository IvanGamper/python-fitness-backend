from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # später einschränken
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path("exercises.json")


@app.get("/")
def root():
    return {"status": "Python Fitness Backend läufttttt"}

@app.get("/exercises")
def get_exercises():
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))
