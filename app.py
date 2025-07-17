# === קובץ app.py (משודרג עם סטטוס, זרימה חכמה ותמיכה בהקשר) ===

from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from openai import OpenAI
from chromadb import PersistentClient
from dotenv import load_dotenv
from datetime import timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
from flask_cors import CORS

# === טעינת משתני סביבה === #
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TARGET = os.getenv("EMAIL_TARGET")

# === הגדרת Flask === #
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = False


CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}}, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
collection = chroma_client.get_or_create_collection("atarize_demo")
client = OpenAI(api_key=OPENAI_API_KEY)

with open(os.path.join(BASE_DIR, "data", "system_prompt_atarize.txt"), encoding="utf-8") as f:
    system_prompt = f.read()

with open(os.path.join(BASE_DIR, "data", "Atarize_bot_full_knowledge.json"), encoding="utf-8") as f:
    intents_data = json.load(f)
intents = intents_data.get("intents", [])

# === פונקציות עזר === #
def detect_intent(user_input, intents):
    user_input = user_input.lower()
    for intent in intents:
        for trigger in intent.get("triggers", []):
            if trigger.lower() in user_input:
                return intent
    return None

def send_email_notification(subject, message):
    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TARGET
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("✅ מייל נשלח בהצלחה!")
    except Exception as e:
        print(f"❌ שגיאה בשליחת המייל: {e}")

def detect_user_status(question):
    lowered = question.lower()
    if any(kw in lowered for kw in ["אני", "רוצה", "בוט", "מתחיל", "מעוניין"]):
        return "interested"
    if any(kw in lowered for kw in ["מה", "איך", "למה", "מי", "כמה"]):
        return "curious"
    return session.get("status", "new")

# === דיאלוג עם GPT או INTENT === #
def generate_answer(question):
    if (
        any(x in question for x in ["@", ".com", "email", "מייל"]) or
        any(code in question for code in ["050", "051", "052", "053", "054", "055", "058", "059"]) or
        "טלפון" in question or
        "שם" in question
    ):
        send_email_notification(
            subject="📬 ליד מהצ'אט – פרטי התקשרות התקבלו",
            message=f"המשתמש כתב:\n\n{question}"
        )

    intent = detect_intent(question, intents)
    if intent:
        session["status"] = "interested"
        return intent.get("response", "אני כאן לעזור 😊")

    results = collection.query(query_texts=[question], n_results=1)
    relevant_context = results["documents"][0][0] if results["documents"] else ""

    full_system_prompt = f"""{system_prompt}

סטטוס שיחה: {session.get('status', 'new')}

הקשר רלוונטי מתוך המסמכים:
{relevant_context}
"""
    history = [{"role": "system", "content": full_system_prompt}]
    for entry in session["history"][-2:]:
        history.append({"role": "user", "content": entry["question"]})
        history.append({"role": "assistant", "content": entry["answer"]})
    history.append({"role": "user", "content": question})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=history
    )
    return completion.choices[0].message.content.strip()

# === ראוט HTML רגיל === #
@app.route("/", methods=["GET", "POST"])
def chat():
    if "history" not in session:
        session["history"] = []
        session["status"] = "new"

    answer = ""
    if request.method == "POST":
        question = request.form.get("question")
        session["status"] = detect_user_status(question)
        answer = generate_answer(question)
        session["history"].append({"question": question, "answer": answer})
        session.modified = True

    return render_template("chat.html", answer=answer, history=session["history"])

# === Landing Page Route === #
@app.route("/landing")
def landing():
    return app.send_static_file("index.html")

# === API JSON === #
@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    if request.method == "OPTIONS":
        return '', 200
    if "history" not in session:
        session["history"] = []
        session["status"] = "new"

    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400

    session["status"] = detect_user_status(question)
    answer = generate_answer(question)
    session["history"].append({"question": question, "answer": answer})
    session.modified = True

    return jsonify({"answer": answer, "success": True})

@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json()
    full_name = data.get("full_name", "")
    phone = data.get("phone", "")
    email = data.get("email", "")
    if not (full_name and phone and email):
        return jsonify({"success": False, "error": "Missing fields"}), 400
    subject = "ליד חדש מהאתר"
    message = f"שם מלא: {full_name}\nטלפון: {phone}\nאימייל: {email}"
    try:
        send_email_notification(subject, message)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/clear", methods=["POST"])
def api_clear():
    session.pop("history", None)
    session.pop("status", None)
    return jsonify({"success": True})

@app.route("/clear", methods=["POST"])
def clear_chat():
    session.pop("history", None)
    session.pop("status", None)
    return redirect(url_for("chat"))

if __name__ == "__main__":
    app.run(debug=True)