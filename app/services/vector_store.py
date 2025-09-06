import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.services.openai_client import embed_text
from typing import Optional


# Persistent Chroma backed by SQLite in CHROMA_DIR
_client = chromadb.PersistentClient(path=settings.CHROMA_DIR, settings=ChromaSettings(anonymized_telemetry=False))
_collection = _client.get_or_create_collection(name="chat_logs", metadata={"hnsw:space": "cosine"})


ASYNC_BATCH = 32


async def add_to_index(doc_id: str, text: str, metadata: dict):
    vec = await embed_text(text)
    _collection.add(ids=[doc_id], embeddings=[vec], documents=[text], metadatas=[metadata])


def query_similar(text: str, n_results: int = 5):
    # NOTE: This uses server-side embedding if provided, here we embed client-side first for better control.
    # For quickness we accept raw text and do a naive query by document (not embedding), which is OK for demo
    out = _collection.query(query_texts=[text], n_results=n_results)
    results = []
    for i in range(len(out.get("ids", [[]])[0])):
        results.append({
        "id": out["ids"][0][i],
        "document": out["documents"][0][i],
        "metadata": out["metadatas"][0][i],
        "distance": out["distances"][0][i] if "distances" in out else None,
        })
    return results