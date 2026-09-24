"""
Newsletter Digest Agent
------------------------
Cada vez que corre:
  1. Se conecta a Gmail por IMAP y revisa los correos de los ultimos 2 dias.
  2. Filtra cuales parecen newsletters (heuristica: List-Unsubscribe, Precedence, remitente).
  3. Descarta los que ya proceso antes (memoria/estado en state.json).
  4. Le pide a Gemini que sintetice todo en un solo resumen.
  5. Envia el resumen como un correo nuevo.
  6. Actualiza el estado para no repetir los mismos newsletters manana.
"""

import imaplib
import email
from email.header import decode_header
import smtplib
from email.mime.text import MIMEText
import os
import json
import re
import html
import requests
from datetime import datetime, timedelta

STATE_FILE = "state.json"

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DIGEST_TO = os.environ.get("DIGEST_TO_EMAIL", GMAIL_ADDRESS)


# ---------- Estado / memoria ----------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed_ids": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------- Utilidades de parseo de correo ----------

def clean_html(raw_html):
    text = re.sub("<[^<]+?>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(errors="ignore")
                except Exception:
                    continue
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    raw = part.get_payload(decode=True).decode(errors="ignore")
                    return clean_html(raw)
                except Exception:
                    continue
        return ""
    try:
        raw = msg.get_payload(decode=True).decode(errors="ignore")
    except Exception:
        return ""
    if msg.get_content_type() == "text/html":
        return clean_html(raw)
    return raw


def is_newsletter(msg):
    if msg.get("List-Unsubscribe"):
        return True
    if (msg.get("Precedence") or "").lower() == "bulk":
        return True
    from_addr = (msg.get("From") or "").lower()
    keywords = ["newsletter", "noreply", "no-reply", "digest", "updates@", "news@"]
    return any(k in from_addr for k in keywords)


# ---------- Paso 1: leer correos (herramienta: IMAP) ----------

def fetch_newsletters(state):
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    imap.select("INBOX")

    since_date = (datetime.utcnow() - timedelta(days=2)).strftime("%d-%b-%Y")
    _, data = imap.search(None, f"(SINCE {since_date})")
    ids = data[0].split()

    newsletters = []
    for msg_id in ids:
        _, msg_data = imap.fetch(msg_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        message_id = msg.get("Message-ID", str(msg_id))

        if message_id in state["processed_ids"]:
            continue
        if not is_newsletter(msg):
            continue

        subject, encoding = decode_header(msg.get("Subject", ""))[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8", errors="ignore")

        body = get_body(msg)[:3000]  # limitar tamano por correo

        newsletters.append(
            {
                "id": message_id,
                "from": msg.get("From", ""),
                "subject": subject,
                "body": body,
            }
        )

    imap.logout()
    return newsletters


# ---------- Paso 2: sintetizar (herramienta: modelo Gemini) ----------

def summarize_with_gemini(newsletters):
    combined = "\n\n---\n\n".join(
        f"De: {n['from']}\nAsunto: {n['subject']}\nContenido:\n{n['body']}"
        for n in newsletters
    )

    prompt = (
        "Eres un asistente que resume newsletters de correo para una persona ocupada. "
        "A continuacion tienes varios correos de newsletter. Escribe un resumen "
        "consolidado en espanol, organizado por newsletter, en texto plano con "
        "vinetas (-), destacando lo mas relevante de cada uno en 2-3 lineas. "
        "Se breve, concreto y ameno.\n\n" + combined
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ---------- Paso 3: entregar el resultado (herramienta: SMTP) ----------

def send_digest_email(summary_text, count):
    today = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEText(summary_text, "plain", "utf-8")
    msg["Subject"] = f"Tu resumen de newsletters - {today} ({count} correos)"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = DIGEST_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [DIGEST_TO], msg.as_string())


# ---------- Loop principal del agente ----------

def main():
    state = load_state()
    newsletters = fetch_newsletters(state)
    print(f"Encontrados {len(newsletters)} newsletters nuevos.")

    if not newsletters:
        print("No hay newsletters nuevos. No se envia nada.")
        return

    summary = summarize_with_gemini(newsletters)
    send_digest_email(summary, len(newsletters))

    state["processed_ids"].extend(n["id"] for n in newsletters)
    save_state(state)
    print("Resumen enviado y estado actualizado.")


if __name__ == "__main__":
    main()
