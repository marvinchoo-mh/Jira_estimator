"""
build_vector_index.py

Builds a ChromaDB vector index from the training knowledge base
(data/train_knowledge_base.csv). Uses BAAI/bge-small-en-v1.5 for embeddings,
which runs locally with no API key needed.

Also provides a search_similar_tickets() function used by the estimation
script to find semantically similar historical tickets.
"""

import csv
import chromadb
from chromadb.utils import embedding_functions

from config import DATA_DIR, CHROMA_DB_DIR

TRAIN_FILE = DATA_DIR / "train_knowledge_base.csv"
COLLECTION_NAME = "jira_tickets"

# ============================================================================
# EMBEDDING MODEL: BAAI/bge-small-en-v1.5
#
# Why this model:
#   - Free and local: no API key, runs entirely on CPU
#   - Trained specifically for retrieval/search tasks
#   - Small: ~130MB download, 384 dimensions
#   - High quality: ranks well on MTEB retrieval benchmarks
#   - Downloads once on first run, then cached at ~/.cache/huggingface/
#
# If you want to swap models later, change EMBEDDING_MODEL below.
# Other options: "all-MiniLM-L6-v2", "all-mpnet-base-v2"
# ============================================================================
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def get_embedding_function():
    """Create the sentence-transformers embedding function for ChromaDB."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )


def get_chroma_client():
    """Create a persistent ChromaDB client that saves to disk."""
    return chromadb.PersistentClient(path=str(CHROMA_DB_DIR))


def get_collection(client=None):
    """Get or create the jira_tickets collection with the embedding function."""
    if client is None:
        client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
    )


def build_index():
    """
    Build the vector index from train_knowledge_base.csv.
    Deletes any existing index and rebuilds from scratch.
    """
    print(f"Loading training data from {TRAIN_FILE}...")
    rows = []
    with open(TRAIN_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"Loaded {len(rows)} training tickets.")

    print(f"\nInitializing ChromaDB at {CHROMA_DB_DIR}...")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    client = get_chroma_client()

    # Delete existing collection if it exists, then recreate
    try:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted existing collection.")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
    )

    # Prepare data for ChromaDB
    documents = []
    metadatas = []
    ids = []

    for row in rows:
        combined_text = row.get("combined_text", "")
        if not combined_text.strip():
            continue

        # Parse story_points safely (may be empty string or None)
        sp = row.get("story_points", "")
        story_points = float(sp) if sp else None

        ct = row.get("cycle_time_working_days", "")
        cycle_time = int(ct) if ct else None

        metadata = {
            "issue_key": row["issue_key"],
            "issue_type": row["issue_type"],
            "component": row.get("component", ""),
        }
        # ChromaDB doesn't allow None in metadata, so only add if present
        if story_points is not None:
            metadata["story_points"] = story_points
        if cycle_time is not None:
            metadata["cycle_time_working_days"] = cycle_time

        documents.append(combined_text)
        metadatas.append(metadata)
        ids.append(row["issue_key"])

    # Add in batches (ChromaDB handles embedding automatically)
    BATCH_SIZE = 50
    total = len(documents)
    print(f"\nIndexing {total} tickets...")

    for i in range(0, total, BATCH_SIZE):
        batch_end = min(i + BATCH_SIZE, total)
        collection.add(
            documents=documents[i:batch_end],
            metadatas=metadatas[i:batch_end],
            ids=ids[i:batch_end],
        )
        print(f"  Indexed {batch_end}/{total}...")

    # Print stats
    types = {}
    for m in metadatas:
        t = m["issue_type"]
        types[t] = types.get(t, 0) + 1

    print(f"\n--- Index Stats ---")
    print(f"Total documents indexed: {collection.count()}")
    print(f"Issue types: {types}")
    print(f"Stored at: {CHROMA_DB_DIR}")
    print("\nVector index build complete.")


# ============================================================================
# ISSUE TYPE GROUPING
#
# Tech and Story are treated as equivalent for similarity matching because
# on board 520 they represent the same kind of work (feature implementation,
# code changes). The distinction is often arbitrary — the same work might be
# logged as "Tech" or "Story" depending on who created the ticket.
#
# This means: a new Story will also retrieve similar Tech tickets, and vice versa.
# Other types (Task, Bug, Sub-task) remain separate.
# ============================================================================
ISSUE_TYPE_GROUPS = {
    "Tech": ["Tech", "Story"],
    "Story": ["Tech", "Story"],
}


def search_similar_tickets(combined_text, issue_type, top_k=5):
    """
    Search for similar historical tickets in the vector index.

    Args:
        combined_text: The combined_text of the new ticket to find matches for.
        issue_type: Filter results to this issue type (or its group —
                    Tech and Story are treated as equivalent).
        top_k: Number of similar tickets to return.

    Returns:
        List of dicts with keys: issue_key, issue_type, story_points,
        cycle_time_working_days, distance, combined_text
    """
    collection = get_collection()

    # Check if this type belongs to a group (Tech/Story share results)
    type_group = ISSUE_TYPE_GROUPS.get(issue_type)
    if type_group:
        where_filter = {"issue_type": {"$in": type_group}}
    else:
        where_filter = {"issue_type": issue_type}

    results = collection.query(
        query_texts=[combined_text],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    similar_tickets = []
    if results and results["ids"] and results["ids"][0]:
        for i, ticket_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            similar_tickets.append({
                "issue_key": ticket_id,
                "issue_type": metadata.get("issue_type", ""),
                "story_points": metadata.get("story_points"),
                "cycle_time_working_days": metadata.get("cycle_time_working_days"),
                "distance": results["distances"][0][i],
                "combined_text": results["documents"][0][i],
            })

    return similar_tickets


if __name__ == "__main__":
    build_index()
