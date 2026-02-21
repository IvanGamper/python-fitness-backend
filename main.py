from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import resend
import base64
import requests
import os
from resend import Attachment
import json
from pathlib import Path
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta

resend.api_key = os.getenv("RESEND_API_KEY")
if not resend.api_key:
    raise RuntimeError("RESEND_API_KEY nicht gesetzt")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pythonfitness.de",
                   "https://www.pythonfitness.de"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path("exercises.json")
LEADS_FILE = Path("leads.json")
PDF_PATH = Path("files/handstand.pdf")


@app.get("/")
def root():
    return {"status": "Python Fitness Backend läufttttt"}

class Exercise(BaseModel):
    title: str
    category: str

@app.get("/exercises")
def get_exercises():
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))

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

    leads.append({
        "email": data.email,
        "created": datetime.utcnow().isoformat(),
    })

    LEADS_FILE.write_text(
        json.dumps(leads, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    try:
        send_pdf_via_email(data.email)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=str(e))


    return {
        "message": "Danke für deine E-Mail.",
    }

def send_pdf_via_email(to_email: str):

    attachment = Attachment(
        filename="handstand.pdf",
        path=str(PDF_PATH)   # 🔥 Das ist wichtig
    )

    response = resend.Emails.send(
        {
            "from": "onboarding@pythonfitness.de",
            "to": to_email,
            "subject": "Dein Handstand Guide von Python Fitness",
            "html": """
                <p>Hallo,</p>
                <p>Hier ist dein Handstand Guide.</p>
                <p>Viel Spaß beim Training!</p>
            """,
            "attachments": [attachment],
        }
    )

    print("Resend Response:", response)