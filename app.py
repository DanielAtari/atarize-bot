from flask import Flask, request, render_template, session, redirect, url_for
from openai import OpenAI
from chromadb import PersistentClient
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
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)

# === בסיס הפרויקט === #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === התחברות ל־ChromaDB === #
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
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
    print("📬 מנסה לשלוח מייל...")
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
    except Exception as e:
        print(f"❌ שגיאה בשליחת המייל: {e}")

def handle_question(question, session, intents, collection, system_prompt, client):
    """
    Handles a user question: detects intent, retrieves context from Chroma, and gets a GPT response if needed.
    Returns: answer, updated session (dict), and a flag if interested_lead_pending was set/cleared.
    """
    answer = None
    interested_lead_pending_changed = False
    # 1. If waiting for lead details
    if session.get("interested_lead_pending"):
        print("📌 מחכים לפרטי ליד...")
        if any(x in question for x in ["@", ".com", "050", "052", "טלפון", "מייל", "שם"]):
            print("📥 זיהינו ניסיון לשלוח פרטים, שולח התראה במייל")
            send_email_notification(
                subject="💬 פרטי ליד חם התקבלו מהבוט",
                message=f"המשתמש השאיר פרטים:\n\n{question}"
            )
            session.pop("interested_lead_pending")
            answer = "תודה רבה! קיבלנו את הפרטים ונחזור אליך בהקדם 😊"
            interested_lead_pending_changed = True
        else:
            answer = "רק תוודא ששלחת גם שם, טלפון ומייל 🙏"
    else:
        # 2. Intent detection
        intent = detect_intent(question, intents)
        if intent:
            print(f"✅ Intent מזוהה: {intent.get('name')}")
            answer = intent.get("response", "אני כאן לעזור 😊")
            if intent.get("name") == "interested_lead":
                print("🟡 ממתינים לפרטים מהמשתמש...")
                session["interested_lead_pending"] = True
                interested_lead_pending_changed = True
        else:
            print("🔍 אין Intent — שולחים לשאילת GPT עם חיפוש הקשר")
            # 3. Retrieve context from Chroma
            results = collection.query(query_texts=[question], n_results=3)
            relevant_context = "\n---\n".join(doc[0] for doc in results["documents"] if doc)
            print("🔍 הקשר שהוחזר מה־Chroma:\n", relevant_context)
            # 4. Build system prompt with context
            full_system_prompt = f"""{system_prompt}\n\nהקשר רלוונטי מתוך המסמכים:\n{relevant_context}\n"""
            # 5. Build chat history
            history = [{"role": "system", "content": full_system_prompt}]
            for entry in session["history"]:
                history.append({"role": "user", "content": entry["question"]})
                history.append({"role": "assistant", "content": entry["answer"]})
            history.append({"role": "user", "content": question})
            # 6. Call GPT
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=history
            )
            answer = completion.choices[0].message.content.strip()
    return answer, session, interested_lead_pending_changed

# === ראוט ראשי לצ׳אט === #
@app.route("/", methods=["GET", "POST"])
def chat():
    answer = ""
    if "history" not in session:
        session["history"] = []
    if request.method == "POST":
        question = request.form.get("question")
        print(f"\n🟢 שאלה מהמשתמש: {question}")
        answer, session, _ = handle_question(question, session, intents, collection, system_prompt, client)
        session["history"].append({"question": question, "answer": answer})
        session.modified = True
    return render_template("chat.html", answer=answer, history=session.get("history", []))

# === JSON endpoint for AJAX requests === #
@app.route("/api/chat", methods=["POST"])
def api_chat():
    from flask import jsonify
    if "history" not in session:
        session["history"] = []
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    print(f"\n🟢 שאלה מהמשתמש (API): {question}")
    answer, session, _ = handle_question(question, session, intents, collection, system_prompt, client)
    session["history"].append({"question": question, "answer": answer})
    session.modified = True
    return jsonify({
        "answer": answer,
        "success": True
    })

# === JSON endpoint for clearing chat === #
@app.route("/api/clear", methods=["POST"])
def api_clear():
    from flask import jsonify
    
    session.pop("history", None)
    session.pop("interested_lead_pending", None)
    
    return jsonify({"success": True})

# === ניקוי שיחה === #
@app.route("/clear", methods=["POST"])
def clear_chat():
    session.pop("history", None)
    session.pop("interested_lead_pending", None)
    return redirect(url_for("chat"))

# === הרצת השרת === #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
