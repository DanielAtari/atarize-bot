import os
from chromadb import PersistentClient

# נתיב לתיקיית Chroma
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

# התחברות ל־Chroma
client = PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("atarize_knowledge")

# בדיקת כמות מסמכים
count = collection.count()
print(f"📦 מספר המסמכים ב־'atarize_knowledge': {count}")

# שליפת כל המסמכים (עד 1000)
results = collection.get(include=["documents", "metadatas"], limit=1000)

print("\n📝 תוכן המסמכים:")
for i, doc in enumerate(results["documents"]):
    print(f"\n📄 [{i+1}]")
    print(doc)
    print("📌 Metadata:", results["metadatas"][i])
