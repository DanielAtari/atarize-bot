#!/usr/bin/env python3
"""
Debug script to analyze ChromaDB collections and intent-knowledge matching.
This script helps identify mismatches between intent detection and knowledge retrieval.
"""

import os
import json
from collections import defaultdict
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup ChromaDB connection
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")

embedding_func = OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-large"
)

print("🔍 DEBUGGING CHROMADB COLLECTIONS AND INTENT MATCHING")
print("=" * 60)

try:
    chroma_client = PersistentClient(path=CHROMA_DB_PATH)
    print(f"✅ Connected to ChromaDB at: {CHROMA_DB_PATH}")
except Exception as e:
    print(f"❌ Failed to connect to ChromaDB: {e}")
    exit(1)

# === ANALYZE INTENTS COLLECTION === #
print("\n=== INTENTS COLLECTION ===")
try:
    intents_collection = chroma_client.get_or_create_collection("atarize_intents", embedding_function=embedding_func)
    intents_data = intents_collection.get(include=["metadatas", "documents"])
    
    intents_count = len(intents_data["ids"])
    print(f"Total intents: {intents_count}")
    
    if intents_count > 0:
        for i, (intent_id, metadata, doc) in enumerate(zip(intents_data["ids"], intents_data["metadatas"], intents_data["documents"])):
            category = metadata.get("category", "N/A")
            triggers = metadata.get("triggers", "N/A")
            print(f"{i+1:2d}. {intent_id} | category: {category}")
            print(f"     triggers: {triggers[:100]}{'...' if len(str(triggers)) > 100 else ''}")
    else:
        print("⚠️  No intents found in collection!")
        
except Exception as e:
    print(f"❌ Failed to access intents collection: {e}")
    intents_collection = None

# === ANALYZE KNOWLEDGE COLLECTION === #
print("\n=== KNOWLEDGE COLLECTION ===")
try:
    knowledge_collection = chroma_client.get_or_create_collection("atarize_knowledge", embedding_function=embedding_func)
    knowledge_data = knowledge_collection.get(include=["metadatas"])
    
    knowledge_count = len(knowledge_data["ids"])
    print(f"Total documents: {knowledge_count}")
    
    # Count documents by intent
    intent_counts = defaultdict(int)
    intent_samples = defaultdict(list)
    
    for doc_id, metadata in zip(knowledge_data["ids"], knowledge_data["metadatas"]):
        intent = metadata.get("intent", "NO_INTENT")
        intent_counts[intent] += 1
        if len(intent_samples[intent]) < 3:  # Keep max 3 samples per intent
            intent_samples[intent].append(doc_id)
    
    print("\nDocuments by intent:")
    for intent, count in sorted(intent_counts.items()):
        samples = ", ".join(intent_samples[intent])
        print(f"  - {intent}: {count} docs (samples: {samples})")
        
except Exception as e:
    print(f"❌ Failed to access knowledge collection: {e}")
    knowledge_collection = None

# === INTENT-KNOWLEDGE MISMATCH ANALYSIS === #
print("\n=== INTENT-KNOWLEDGE MISMATCH ANALYSIS ===")
if intents_collection and knowledge_collection:
    # Get all intent names from both collections
    intent_names = set(intents_data["ids"]) if intents_data["ids"] else set()
    knowledge_intents = set(intent_counts.keys()) if intent_counts else set()
    
    print(f"Intent names in intents collection: {sorted(intent_names)}")
    print(f"Intent names in knowledge collection: {sorted(knowledge_intents)}")
    
    # Find mismatches
    only_in_intents = intent_names - knowledge_intents
    only_in_knowledge = knowledge_intents - intent_names
    matched_intents = intent_names & knowledge_intents
    
    print(f"\n✅ Matched intents ({len(matched_intents)}): {sorted(matched_intents)}")
    if only_in_intents:
        print(f"⚠️  Only in intents collection ({len(only_in_intents)}): {sorted(only_in_intents)}")
    if only_in_knowledge:
        print(f"⚠️  Only in knowledge collection ({len(only_in_knowledge)}): {sorted(only_in_knowledge)}")

# === MULTI-INTENT TEST === #
print("\n=== MULTI-INTENT TEST ===")

test_questions = [
    ("כמה עולה השירות", "pricing question"),
    ("מה אתם עושים", "about question"), 
    ("איך מתחילים", "onboarding question"),
    ("מה זה atarize", "about atarize question"),
    ("איך הבוט עובד", "tech explanation"),
]

def test_intent_flow(question, description):
    print(f"\nTest: \"{question}\" ({description})")
    
    if not intents_collection:
        print("  ❌ Intents collection not available")
        return
        
    try:
        # Query intents collection
        results = intents_collection.query(
            query_texts=[question], 
            n_results=1, 
            include=["metadatas", "distances"]
        )
        
        if results["ids"] and results["ids"][0]:
            intent_id = results["ids"][0][0]
            distance = results["distances"][0][0]
            print(f"  Intent detected: \"{intent_id}\" (distance: {distance:.4f})")
            
            # Check knowledge collection for this intent
            if knowledge_collection:
                try:
                    knowledge_results = knowledge_collection.get(
                        where={"intent": intent_id},
                        include=["documents", "metadatas"]
                    )
                    doc_count = len(knowledge_results["documents"])
                    print(f"  Knowledge docs for \"{intent_id}\": {doc_count}")
                    
                    if doc_count == 0:
                        print(f"  ❌ PROBLEM: No knowledge documents found for intent '{intent_id}'!")
                    else:
                        print(f"  ✅ Found {doc_count} knowledge documents")
                        # Show first document snippet
                        if knowledge_results["documents"]:
                            first_doc = knowledge_results["documents"][0]
                            print(f"     Sample: {first_doc[:100]}...")
                            
                except Exception as e:
                    print(f"  ❌ Error querying knowledge: {e}")
            else:
                print("  ❌ Knowledge collection not available")
                
        else:
            print("  ❌ No intent detected")
            
    except Exception as e:
        print(f"  ❌ Error in intent detection: {e}")

# Run all tests
for question, description in test_questions:
    test_intent_flow(question, description)

# === SUMMARY === #
print("\n" + "=" * 60)
print("🎯 SUMMARY")
print("=" * 60)

if intents_collection and knowledge_collection:
    print(f"✅ Intents collection: {len(intents_data['ids']) if intents_data['ids'] else 0} intents")
    print(f"✅ Knowledge collection: {knowledge_count} documents")
    
    if only_in_intents or only_in_knowledge:
        print("\n⚠️  POTENTIAL ISSUES FOUND:")
        if only_in_intents:
            print(f"   • {len(only_in_intents)} intent(s) have no knowledge documents: {sorted(only_in_intents)}")
        if only_in_knowledge:
            print(f"   • {len(only_in_knowledge)} knowledge intent(s) not in intents config: {sorted(only_in_knowledge)}")
    else:
        print("✅ All intent names match between collections")
else:
    print("❌ Could not access one or both collections")

print("\n🔧 NEXT STEPS:")
print("1. If you see intent name mismatches, update either intents_config.json or knowledge JSON")
print("2. If collections are empty, run load_intents.py and load_data.py")  
print("3. If distances are too high, adjust thresholds in app.py")
print("4. Check that .env file contains valid OPENAI_API_KEY")