from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import json
from pathlib import Path
print(json)
print(Path)
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import uuid




app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # später einschränken
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path("exercises.json")
LEADS_FILE = Path("leads.json")
PDF_PATH = Path("files/handstand.pdf")

TOKEN_LIFETIME_HOURS = 24


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

class SignupRequest(BaseModel):
    email: EmailStr


@app.post("/signup")
def signup(data: SignupRequest):
    if LEADS_FILE.exists():
        leads = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
    else:
        leads = []

    token = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(hours=TOKEN_LIFETIME_HOURS)).isoformat()

    leads.append({
        "email": data.email,
        "token": token,
        "used": False,
        "expires": expires_at,
    })

    LEADS_FILE.write_text(
        json.dumps(leads, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    download_link = f"http://localhost:8000/download/{token}"

    # DEV: später echte E-Mail
    print("DOWNLOAD-LINK:", download_link)

    return {
        "message": "Danke! Prüfe deine E-Mails für den Download-Link."
    }



@app.get("/download/{token}")
def download_pdf(token: str):
    if not LEADS_FILE.exists():
        raise HTTPException(status_code=404, detail="Ungültiger Link")

    leads = json.loads(LEADS_FILE.read_text(encoding="utf-8"))

    for lead in leads:
        if lead["token"] == token:

            if lead["used"]:
                raise HTTPException(status_code=410, detail="Link bereits benutzt")

            if datetime.utcnow() > datetime.fromisoformat(lead["expires"]):
                raise HTTPException(status_code=410, detail="Link abgelaufen")

            lead["used"] = True

            LEADS_FILE.write_text(
                json.dumps(leads, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            return FileResponse(
                path=PDF_PATH,
                filename="Handstand_Trainingsplan.pdf",
                media_type="application/pdf"
            )

    raise HTTPException(status_code=404, detail="Ungültiger Link")