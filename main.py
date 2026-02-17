from fastapi import HTTPException

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
import smtplib
from email.message import EmailMessage
import json
from pathlib import Path
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta


EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pythonfitness.de",
                   "https://www.pythonfitness.de"],  # später einschränken
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

    if not EMAIL_USER or not EMAIL_PASS:
        raise RuntimeError("EMAIL_USER und EMAIL_PASS müssen gesetzt sein.")

    msg = EmailMessage()
    msg["Subject"] = "Dein PDF"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content("Hier ist dein PDF. Viel Spaß damit!")

    with open(PDF_PATH, "rb") as f:
        pdf_data = f.read()

    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename="handstand.pdf")


    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:

        smtp.login(EMAIL_USER, EMAIL_PASS)

        smtp.send_message(msg)