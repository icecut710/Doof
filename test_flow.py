import json
from doof.intelligence.store import get_store
from doof.intelligence.rag import retrieve_memories, build_context
from doof.intelligence.quality import score_response
from doof.intelligence.dataset import build_dataset
from database import get_db

def run():
    print("--- 1. Testing Memory ---")
    store = get_store()
    mem = store.add("Kaeden likes futuristic dark interfaces", importance="high", category="preferences")
    print("Added memory:", mem)

    print("\n--- 2. Testing RAG ---")
    retrieved = retrieve_memories("What kind of UI style does Kaeden like?", store)
    print("Retrieved:", retrieved)
    if retrieved:
        context = build_context(retrieved)
        print("Context block:\n", context)
    else:
        print("FAILED to retrieve memory.")

    print("\n--- 3. Testing Quality Scoring ---")
    score_good = score_response("What style does Kaeden like?", "Kaeden prefers futuristic dark interfaces.", rating="good", memories_used=retrieved)
    print("Good Score:", score_good)

    print("\n--- 4. Testing Dataset Builder ---")
    db = get_db()
    # Insert a fake feedback
    db.insert_feedback({
        "prompt": "What style?",
        "response": "Kaeden prefers futuristic dark interfaces.",
        "rating": "bad",
        "correction": "He likes futuristic dark interfaces with violet accents.",
        "memories_used": retrieved,
        "approved": True,
        "quality": 85.0
    })
    
    ds = build_dataset()
    print("Dataset built:", ds)

run()
