from chromadb import PersistentClient
import os
import json

# נתיב בסיס לפרויקט
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# אתחול Chroma
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
collection = chroma_client.get_or_create_collection("atarize_demo")

# מחיקת מסמכים קיימים (תואם לגרסאות החדשות)
try:
    collection.delete(where={"source": {"$ne": None}})
    print("✅ כל המסמכים הקיימים נמחקו מה-collection.")
except Exception as e:
    print(f"שגיאה במחיקת המסמכים: {e}")

# קריאת קובץ JSON
json_path = os.path.join(DATA_DIR, "Atarize_bot_full_knowledge.json")

if not os.path.isfile(json_path):
    print("❌ הקובץ לא נמצא:", json_path)
    exit()

with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

# פונקציה להוספת מסמך ל-Chromaß
def add_doc(text, doc_id, metadata):
    collection.add(
        documents=[text],
        ids=[doc_id],
        metadatas=[metadata]
    )
    print(f"✅ נוסף: {doc_id}")

doc_counter = 1

# BENEFITS
for benefit in data.get("benefits", []):
    add_doc(
        text=benefit,
        doc_id=f"benefit_{doc_counter}",
        metadata={
            "type": "benefit",
            "language": data["language"],
            "source": data["business_name"]
        }
    )
    doc_counter += 1

# FEATURES
for feature in data.get("features", []):
    add_doc(
        text=feature,
        doc_id=f"feature_{doc_counter}",
        metadata={
            "type": "feature",
            "language": data["language"],
            "source": data["business_name"]
        }
    )
    doc_counter += 1

# FAQ
for i, faq in enumerate(data.get("faq", []), start=1):
    text = f"שאלה: {faq['q']}\nתשובה: {faq['a']}"
    add_doc(
        text=text,
        doc_id=f"faq_{i}",
        metadata={
            "type": "faq",
            "language": data["language"],
            "source": data["business_name"]
        }
    )

# OBJECTIONS
for i, obj in enumerate(data.get("common_objections", []), start=1):
    text = f"התנגדות: {obj['question']}\nתגובה: {obj['response']}"
    add_doc(
        text=text,
        doc_id=f"objection_{i}",
        metadata={
            "type": "objection",
            "language": data["language"],
            "source": data["business_name"]
        }
    )

# PROCESS STEPS
for step in data.get("process_steps", []):
    add_doc(
        text=step,
        doc_id=f"process_step_{doc_counter}",
        metadata={
            "type": "process_step",
            "language": data["language"],
            "source": data["business_name"]
        }
    )
    doc_counter += 1

# PRICING (סיכום כללי)
pricing = data.get("pricing", {})
pricing_text = f"""מחיר הקמה: {pricing.get('setup')}
הטמעה (אם דרושה): {pricing.get('deployment')}
הטמעה בידע: {pricing.get('embedding')}
חודש ניסיון: {pricing.get('trial')}
אפשרויות תשלום: {', '.join(pricing.get('payment_methods', []))}"""
add_doc(
    text=pricing_text,
    doc_id="pricing_summary",
    metadata={
        "type": "pricing",
        "language": data["language"],
        "source": data["business_name"]
    }
)

# PRICING PLANS
for plan, details in pricing.get("monthly_plans", {}).items():
    text = f"חבילת {plan}:\nהודעות: {details['limit']}\nמחיר: {details['price']}"
    add_doc(
        text=text,
        doc_id=f"pricing_{plan.lower()}",
        metadata={
            "type": "pricing_plan",
            "plan": plan,
            "language": data["language"],
            "source": data["business_name"]
        }
    )

# INTENT DETECTION
intent = data.get("intent_detection", {}).get("interested_lead")
if intent:
    text = f"כוונת ליד מתעניין:\n{intent['description']}\nפעולה: {intent['action']}"
    add_doc(
        text=text,
        doc_id="intent_interested_lead",
        metadata={
            "type": "intent",
            "intent": "interested_lead",
            "language": data["language"],
            "source": data["business_name"]
        }
    )

print("🎉 כל הידע הועלה בהצלחה ל־Chroma!")