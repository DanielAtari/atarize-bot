from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from openai import OpenAI
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
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
app = Flask(__name__, static_folder="static/dist", static_url_path="")
app.secret_key = FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = False

CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://atarize-frontend.onrender.com"
]}}, supports_credentials=True)

# === הגדרות Chroma - תואמות לסקריפט הטעינה === #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# שימוש ב-PersistentClient כמו בסקריפט הטעינה
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
collection = chroma_client.get_or_create_collection(
    "atarize_demo", 
    embedding_function=embedding_function
)

# === לקוח GPT === #
client = OpenAI(api_key=OPENAI_API_KEY)

# === טעינת קבצים === #
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

def search_chromadb(question, n_results=3):
    """חיפוש משופר ב-ChromaDB"""
    try:
        print(f"🔍 מחפש ב-ChromaDB: {question}")
        
        # ביצוע חיפוש
        results = collection.query(
            query_texts=[question], 
            n_results=n_results
        )
        
        # בדיקה שיש תוצאות
        if not results or not results.get("documents") or not results["documents"][0]:
            print("⚠️ לא נמצאו תוצאות ב-ChromaDB")
            return ""
        
        # איחוד התוצאות
        relevant_docs = results["documents"][0]
        metadatas = results.get("metadatas", [[]])[0]
        
        # בניית הקשר רלוונטי
        context_parts = []
        for i, doc in enumerate(relevant_docs):
            metadata = metadatas[i] if i < len(metadatas) else {}
            doc_type = metadata.get("type", "מידע כללי")
            context_parts.append(f"[{doc_type}] {doc}")
        
        context = "\n\n".join(context_parts)
        print(f"✅ נמצאו {len(relevant_docs)} תוצאות ב-ChromaDB")
        print(f"📄 הקשר: {context[:200]}...")
        
        return context
        
    except Exception as e:
        print(f"❌ שגיאה בחיפוש ChromaDB: {e}")
        return ""

def generate_answer(question):
    try:
        # בדיקת פרטי התקשרות
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

        # בדיקת intents
        intent = detect_intent(question, intents)
        if intent:
            session["status"] = "interested"
            return intent.get("response", "אני כאן לעזור 😊")

        # חיפוש ב-ChromaDB
        relevant_context = search_chromadb(question)
        
        # בניית prompt מלא
        full_system_prompt = f"""{system_prompt}

סטטוס שיחה: {session.get('status', 'new')}

הקשר רלוונטי מתוך בסיס הנתונים:
{relevant_context}

הוראות נוספות:
- אם יש מידע רלוונטי בהקשר, השתמש בו כדי לענות בצורה מדויקת
- אם אין מידע רלוונטי, ענה בהתבסס על הידע הכללי שלך על עסק הצ'אטבוטים
- תמיד ענה בעברית ובצורה ידידותית
"""

        # בניית היסטוריית השיחה
        history = [{"role": "system", "content": full_system_prompt}]
        
        # הוספת היסטוריה (רק 2 החלפות אחרונות)
        for entry in session.get("history", [])[-2:]:
            history.append({"role": "user", "content": entry["question"]})
            history.append({"role": "assistant", "content": entry["answer"]})
        
        # הוספת השאלה הנוכחית
        history.append({"role": "user", "content": question})

        print(f"📤 שולח ל-GPT עם קונטקסט: {len(relevant_context)} תווים")
        
        # קבלת תשובה מ-GPT
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=history,
            temperature=0.7,
            max_tokens=1000,
            timeout=15
        )
        
        answer = completion.choices[0].message.content.strip()
        print(f"✅ תשובה מ-GPT: {answer[:100]}...")
        
        return answer
        
    except Exception as e:
        print(f"❌ שגיאה ביצירת תשובת GPT: {e}")
        return "הייתה בעיה בעיבוד השאלה. נסה שוב מאוחר יותר."

# === בדיקת חיבור ל-ChromaDB בעת הפעלה === #
def test_chromadb_connection():
    try:
        count = collection.count()
        print(f"🔌 חיבור ל-ChromaDB הצליח! מספר מסמכים: {count}")
        
        # בדיקת חיפוש פשוטה
        test_results = collection.query(query_texts=["מחיר"], n_results=1)
        if test_results and test_results.get("documents") and test_results["documents"][0]:
            print("✅ בדיקת חיפוש הצליחה!")
        else:
            print("⚠️ בדיקת חיפוש נכשלה - אין מסמכים או בעיה בחיפוש")
            
    except Exception as e:
        print(f"❌ בעיה בחיבור ל-ChromaDB: {e}")

# === Routes === #
@app.route("/chat", methods=["GET", "POST"])
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

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    if request.method == "OPTIONS":
        return '', 200
    
    if "history" not in session:
        session["history"] = []
        session["status"] = "new"
    
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "No question provided"}), 400
    
    question = data.get("question", "")
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

# נתיב לבדיקת מצב ChromaDB
@app.route("/api/db-status")
def db_status():
    try:
        count = collection.count()
        return jsonify({
            "success": True,
            "documents_count": count,
            "collection_name": "atarize_demo"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    # בדיקת חיבור ל-ChromaDB בעת הפעלה
    test_chromadb_connection()
    
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", debug=True, port=port)