from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import os
import json

# נתיב בסיס לפרויקט
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# הגדרת embedding function - אותה כמו בפלאסק
embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# אתחול Chroma - אותו כמו בפלאסק
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
collection = chroma_client.get_or_create_collection(
    "atarize_demo", 
    embedding_function=embedding_function
)

# מחיקת מסמכים קיימים
try:
    # שימוש בשיטה החדשה למחיקה
    all_docs = collection.get()
    if all_docs['ids']:
        collection.delete(ids=all_docs['ids'])
        print(f"✅ נמחקו {len(all_docs['ids'])} מסמכים קיימים.")
    else:
        print("✅ אין מסמכים קיימים למחיקה.")
except Exception as e:
    print(f"שגיאה במחיקת המסמכים: {e}")

# קריאת קובץ JSON
json_path = os.path.join(DATA_DIR, "Atarize_bot_full_knowledge.json")

if not os.path.isfile(json_path):
    print("❌ הקובץ לא נמצא:", json_path)
    exit()

with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

# פונקציה משופרת להוספת מסמך ל-Chroma
def add_doc(text, doc_id, metadata):
    try:
        collection.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[metadata]
        )
        print(f"✅ נוסף: {doc_id}")
        return True
    except Exception as e:
        print(f"❌ שגיאה בהוספת {doc_id}: {e}")
        return False

doc_counter = 1
added_count = 0

# BENEFITS
for benefit in data.get("benefits", []):
    if add_doc(
        text=benefit,
        doc_id=f"benefit_{doc_counter}",
        metadata={
            "type": "benefit",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1
    doc_counter += 1

# FEATURES
for feature in data.get("features", []):
    if add_doc(
        text=feature,
        doc_id=f"feature_{doc_counter}",
        metadata={
            "type": "feature",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1
    doc_counter += 1

# FAQ
for i, faq in enumerate(data.get("faq", []), start=1):
    text = f"שאלה: {faq['q']}\nתשובה: {faq['a']}"
    if add_doc(
        text=text,
        doc_id=f"faq_{i}",
        metadata={
            "type": "faq",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1

# OBJECTIONS
for i, obj in enumerate(data.get("common_objections", []), start=1):
    text = f"התנגדות: {obj['question']}\nתגובה: {obj['response']}"
    if add_doc(
        text=text,
        doc_id=f"objection_{i}",
        metadata={
            "type": "objection",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1

# PROCESS STEPS
for step in data.get("process_steps", []):
    if add_doc(
        text=step,
        doc_id=f"process_step_{doc_counter}",
        metadata={
            "type": "process_step",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1
    doc_counter += 1

# PRICING (סיכום כללי)
pricing = data.get("pricing", {})
if pricing:
    pricing_text = f"""מחיר הקמה: {pricing.get('setup', 'לא צוין')}
הטמעה (אם דרושה): {pricing.get('deployment', 'לא צוין')}
הטמעה בידע: {pricing.get('embedding', 'לא צוין')}
חודש ניסיון: {pricing.get('trial', 'לא צוין')}
אפשרויות תשלום: {', '.join(pricing.get('payment_methods', []))}"""
    
    if add_doc(
        text=pricing_text,
        doc_id="pricing_summary",
        metadata={
            "type": "pricing",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1

# PRICING PLANS
for plan, details in pricing.get("monthly_plans", {}).items():
    text = f"חבילת {plan}:\nהודעות: {details.get('limit', 'לא צוין')}\nמחיר: {details.get('price', 'לא צוין')}"
    if add_doc(
        text=text,
        doc_id=f"pricing_{plan.lower()}",
        metadata={
            "type": "pricing_plan",
            "plan": plan,
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1

# INTENT DETECTION
intent = data.get("intent_detection", {}).get("interested_lead")
if intent:
    text = f"כוונת ליד מתעניין:\n{intent['description']}\nפעולה: {intent['action']}"
    if add_doc(
        text=text,
        doc_id="intent_interested_lead",
        metadata={
            "type": "intent",
            "intent": "interested_lead",
            "language": data.get("language", "he"),
            "source": data.get("business_name", "atarize")
        }
    ):
        added_count += 1

print(f"🎉 הושלם! נוספו {added_count} מסמכים ל-ChromaDB!")

# בדיקה שהמידע נשמר
try:
    total_docs = collection.count()
    print(f"📊 סה\"כ מסמכים ב-collection: {total_docs}")
    
    # בדיקת שאילתה פשוטה
    test_query = collection.query(query_texts=["מחיר"], n_results=3)
    print(f"🔍 בדיקת חיפוש למילה 'מחיר': נמצאו {len(test_query['documents'][0])} תוצאות")
    
except Exception as e:
    print(f"❌ שגיאה בבדיקה: {e}")