from flask import Flask, request, render_template, session as session_data, redirect, url_for, jsonify
from openai import OpenAI
from chromadb import HttpClient
from dotenv import load_dotenv
from datetime import timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText

# === טעינת משתני סביבה === #
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TARGET = os.getenv("EMAIL_TARGET")

# === הגדרת Flask === #
app = Flask(__name__, static_folder="static/dist", static_url_path="")
app.secret_key = FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)

# === בסיס הפרויקט === #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === התחברות ל־ChromaDB === #
chroma_client = HttpClient(host="localhost", port=8000)
collection = chroma_client.get_or_create_collection("atarize_knowledge")

# === חיבור ל־OpenAI === #
client = OpenAI(api_key=OPENAI_API_KEY)

# === טעינת system prompt === #
with open(os.path.join(BASE_DIR, "data", "system_prompt_atarize.txt"), encoding="utf-8") as f:
    system_prompt = f.read()

# === טעינת קובץ JSON עם intents === #
with open(os.path.join(BASE_DIR, "data", "Atarize_bot_full_knowledge.json"), encoding="utf-8") as f:
    intents_data = json.load(f)
intents = intents_data.get("intents", [])

# === פונקציה לזיהוי intent === #
def detect_intent(user_input, intents):
    user_input = user_input.lower()
    for intent in intents:
        for trigger in intent.get("triggers", []):
            if trigger.lower() in user_input:
                return intent
    return None

# === שליחת התראה למייל עם דיבאג === #
def send_email_notification(subject, message):
    print("\U0001f4ec מנסה לשלוח מייל...")
    print(f"נושא: {subject}")
    print(f"תוכן:\n{message}")
    print(f"From: {EMAIL_USER} → To: {EMAIL_TARGET}")

    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TARGET

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        print("✅ מייל נשלח בהצלחה!")
        return True
    except Exception as e:
        print(f"❌ שגיאה בשליחת המייל: {e}")
        return False

def handle_question(question, session, collection, system_prompt, client):
    answer = None
    interested_lead_pending_changed = False
    if session.get("interested_lead_pending"):
        print("\U0001f4cc מחכים לפרטי ליד...")
        if any(x in question for x in ["@", ".com", "050", "052", "טלפון", "מייל", "שם"]):
            print("\U0001f4e5 זיהינו ניסיון לשלוח פרטים, שולח התראה במייל")
            send_email_notification(
                subject="\U0001f4ac פרטי ליד חם התקבלו מהבוט",
                message=f"המשתמש השאיר פרטים:\n\n{question}"
            )
            session.pop("interested_lead_pending")
            answer = "תודה רבה! קיבלנו את הפרטים ונחזור אליך בהקדם \U0001f60a"
            interested_lead_pending_changed = True
        else:
            answer = "רק תוודא ששלחת גם שם, טלפון ומייל \U0001f64f"
    else:
        print("\U0001f50d שולחים לשאילת GPT עם חיפוש הקשר")
        results = collection.query(query_texts=[question], n_results=3)
        relevant_context = "\n---\n".join(doc[0] for doc in results["documents"] if doc)
        print("\U0001f50d הקשר שהוחזר מה־Chroma:\n", relevant_context)
        full_system_prompt = f"""{system_prompt}\n\nהקשר רלוונטי מתוך המסמכים:\n{relevant_context}\n"""
        history = [{"role": "system", "content": full_system_prompt}]
        for entry in session["history"]:
            history.append({"role": "user", "content": entry["question"]})
            history.append({"role": "assistant", "content": entry["answer"]})
        history.append({"role": "user", "content": question})
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=history
        )
        answer = completion.choices[0].message.content.strip()
    return answer, session, interested_lead_pending_changed

# === Serve React Frontend === #
@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if "history" not in session_data:
        session_data["history"] = []
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    print(f"\n🟢 שאלה מהמשתמש (API): {question}")
    answer, session_data_, _ = handle_question(question, session_data, collection, system_prompt, client)
    session_data["history"].append({"question": question, "answer": answer})
    session_data.modified = True
    return jsonify({
        "answer": answer,
        "success": True
    })

@app.route("/api/clear", methods=["POST"])
def api_clear():
    session_data.pop("history", None)
    session_data.pop("interested_lead_pending", None)
    return jsonify({"success": True})

@app.route("/clear", methods=["POST"])
def clear_chat():
    session_data.pop("history", None)
    session_data.pop("interested_lead_pending", None)
    return redirect(url_for("chat"))

@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json()
    full_name = data.get("full_name")
    phone = data.get("phone")
    email = data.get("email")
    if not (full_name and phone and email):
        return jsonify({"success": False, "message": "Missing required fields."}), 400
    subject = "📝 ליד חדש מהאתר (טופס צור קשר)"
    body = f"שם מלא: {full_name}\nטלפון: {phone}\nאימייל: {email}"
    success = send_email_notification(subject, body)
    if success:
        return jsonify({"success": True, "message": "Contact details sent successfully!"}), 200
    else:
        return jsonify({"success": False, "message": "Failed to send contact details."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
