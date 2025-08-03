import os
import json
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
import logging

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/load_intents.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

embedding_func = OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-large"
)
chroma_client = PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))

# Delete existing intents collection if exists
try:
    chroma_client.delete_collection("atarize_intents")
    print("🗑️ נמחקה הקולקשן הישנה: atarize_intents")
except Exception as e:
    print(f"לא נמצאה קולקשן למחיקה או שגיאה: {e}")
collection = chroma_client.get_or_create_collection("atarize_intents", embedding_function=embedding_func)

# Load intents config
json_path = os.path.join(DATA_DIR, "intents_config.json")
if not os.path.isfile(json_path):
    print("❌ הקובץ לא נמצא:", json_path)
    exit()
with open(json_path, encoding="utf-8") as f:
    intents = json.load(f)

total = 0
def add_intent_doc(intent):
    doc_id = intent["intent"]
    description = intent.get("description", "")
    triggers = intent.get("triggers", [])
    category = intent.get("category", "")
    content = description if description else " | ".join(triggers)
    metadata = {
        "intent": doc_id,
        "category": category,
        "triggers": ", ".join(triggers)
    }
    collection.add(
        documents=[content],
        ids=[doc_id],
        metadatas=[metadata]
    )
    print(f"✅ Intent inserted: {doc_id} | Content: {content[:60]}{'...' if len(content) > 60 else ''}")

for intent in intents:
    add_intent_doc(intent)
    total += 1

print(f"🎉 All intents loaded into Chroma! Total: {total}")
print(f"[Chroma] Total documents in atarize_intents: {collection.count()}")

def semantic_detect_intent(user_question: str, threshold: float = 0.8):
    """
    Perform a semantic similarity search in the atarize_intents Chroma collection.
    Returns (intent_name, metadata) if the top match is above the threshold, else None.
    """
    # Reconnect to the intents collection (in case called independently)
    intents_collection = chroma_client.get_or_create_collection("atarize_intents", embedding_function=embedding_func)
    results = intents_collection.query(query_texts=[user_question], n_results=1, include=["metadatas", "distances", "ids"])
    ids = results.get("ids", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    if not ids:
        print("[DEBUG] No intent match found.")
        return None
    top_id = ids[0]
    top_meta = metadatas[0]
    top_distance = distances[0]
    print(f"[DEBUG] Top semantic intent match: {top_id} | Distance: {top_distance}")
    if top_distance <= (1 - threshold):  # Chroma: lower distance = more similar
        return top_id, top_meta
    else:
        print(f"[DEBUG] No intent above threshold ({threshold}). Best distance: {top_distance}")
        return None

# Example test (uncomment to run standalone)
# result = semantic_detect_intent("how much does it cost?")
# print("Semantic intent result:", result)