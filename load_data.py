from chromadb import HttpClient
import os
import json

# נתיב בסיס לפרויקט
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# אתחול Chroma
chroma_client = HttpClient(host="localhost", port=8000)
collection = chroma_client.get_or_create_collection("atarize_knowledge")

# מחיקת מסמכים קיימים
try:
    existing = collection.get()
    ids = existing["ids"]
    if ids:
        collection.delete(ids=ids)
        print("✅ כל המסמכים הקיימים נמחקו מה-collection.")
    else:
        print("ℹ️ לא נמצאו מסמכים קיימים למחיקה.")
except Exception as e:
    print(f"שגיאה במחיקת המסמכים: {e}")

# קריאת קובץ JSON
json_path = os.path.join(DATA_DIR, "Atarize_bot_full_knowledge.json")

if not os.path.isfile(json_path):
    print("❌ הקובץ לא נמצא:", json_path)
    exit()

with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

# פונקציה להוספת מסמך ל-Chroma
def add_doc(text, doc_id, metadata):
    collection.add(
        documents=[text],
        ids=[doc_id],
        metadatas=[metadata]
    )
    print(f"✅ נוסף: {doc_id}")

# טעינת הידע מהחלק knowledge
for item in data.get("data", []):
    text = f"שאלה: {item.get('question_he', '')}\nתשובה: {item.get('answer_he', '')}"
    language = item.get("language", [])
    if isinstance(language, list):
        language = ",".join(language)
    add_doc(
        text=text,
        doc_id=item.get("id", ""),
        metadata={
            "intent": item.get("intent", ""),
            "language": language,
            "source": "Atarize"
        }
    )

# טעינת ה-intents כקטגוריית מסמכים נוספת
for intent in data.get("intents", []):
    text = intent.get("response", "")
    add_doc(
        text=text,
        doc_id=f"intent_{intent.get('name', '')}",
        metadata={
            "type": "intent",
            "intent": intent.get("name", ""),
            "language": "he",
            "source": "Atarize"
        }
    )

print("🎉 כל הידע וה-intents הועלו בהצלחה ל־Chroma!")
print("📦 מספר פריטים:", collection.count())
