from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
print(json)
print(Path)
from pydantic import BaseModel



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

class Exercise(BaseModel):
    title: str
    category: str


@app.post("/exercises")
def add_exercise(exercise: Exercise):
    # Bestehende Daten laden
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        data = []

    # Neue ID vergeben
    next_id = max([e["id"] for e in data], default=0) + 1

    new_exercise = {
        "id": next_id,
        "title": exercise.title,
        "category": exercise.category,
    }

    data.append(new_exercise)

    # Zurück in JSON-Datei schreiben
    DATA_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return new_exercise