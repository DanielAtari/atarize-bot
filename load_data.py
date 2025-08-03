from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import os
import json
import re
from dotenv import load_dotenv
import logging

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/load_data.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# נתיב בסיס לפרויקט
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# אתחול Chroma
embedding_func = OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-large"
)
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))

# מחיקת הקולקשן הקיים (אם יש) כדי למנוע חוסר התאמה בווקטורים
try:
    chroma_client.delete_collection("atarize_knowledge")
    print("🗑️ נמחקה הקולקשן הישנה: atarize_knowledge")
except Exception as e:
    print(f"לא נמצאה קולקשן למחיקה או שגיאה: {e}")
collection = chroma_client.get_or_create_collection("atarize_knowledge", embedding_function=embedding_func)

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

def detect_language(text):
    # אם יש לפחות אות אחת באנגלית – נניח שזו שאלה באנגלית
    return "en" if re.search(r'[a-zA-Z]', text) else "he"

# טעינת הידע מהחלק knowledge (paragraph-based, multilingual)
for item in data.get("data", []):
    base_id = item.get("id", "")
    title = item.get("title", {})
    content = item.get("content", {})
    metadata = item.get("metadata", {})
    intent = metadata.get("intent", "")
    category = metadata.get("category", "")
    langs = metadata.get("language", [])

    for lang in ["he", "en"]:
        if lang in title and lang in content:
            text = f"{title[lang]}\n\n{content[lang]}"
            doc_id = f"{base_id}_{lang}"
            meta = {
                "id": doc_id,
                "language": lang,
                "category": category,
                "source": "Atarize"
            }
            if intent:
                meta["intent"] = intent
            print(f"📄 Loading → {doc_id} | lang: {lang}")
            add_doc(
                text=text,
                doc_id=doc_id,
                metadata=meta
            )


print("🎉 כל הידע וה-intents הועלו בהצלחה ל־Chroma!")
print("📦 מספר פריטים:", collection.count())
print(f"[Chroma] Total documents in collection after load: {collection.count()}")
print("[Chroma] Knowledge base ingestion complete.")

# Verify Chroma loading
results = collection.get()
print(f"\n🔍 Loaded {len(results['documents'])} documents from Chroma.")
for i, meta in enumerate(results["metadatas"][:5]):
    print(f"{i+1}. ID: {meta.get('id')} | Intent: {meta.get('intent')} | Langs: {meta.get('language')}")
