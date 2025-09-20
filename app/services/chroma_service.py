import asyncio
from contextlib import contextmanager
from datetime import timezone, datetime, timedelta
from app.core.config import Settings
import chromadb
from fastapi import HTTPException


GLOBAL_EMBEDDING_MODEL = Settings.OPENAI_EMBEDDING_MODEL
CHROMA_DB_PATH = Settings.CHROMA_DB_PATH
CLIENT = chromadb.PersistentClient(
    path=CHROMA_DB_PATH,
    settings=chromadb.Settings(allow_reset=True)
)

class ChromaDBService:
    def __init__(self):
        """Initialize ChromaDB Client."""
        self.client = None
        # Use a lock to avoid race conditions when initializing the client
        self._client_lock = asyncio.Lock()

    async def get_client_async(self):
        """Get or initialize a ChromaDB client asynchronously with proper locking"""
        def init_client():
            try:
                client = CLIENT
                return client
            except Exception as e:
                raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB")
            
        async with self._client_lock:
            if self.client is None:
                # Initialize a client in a thread to avoid blocking
                self.client = await asyncio.to_thread(init_client)
        return self.client

    @contextmanager
    def get_client(self):
        """Synchronous client getter for compatibility"""
        if self.client is None:
            try:
                self.client = CLIENT
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to connect to ChromaDB")
        yield self.client

    async def get_or_create_collection(self, name="Document"):
        """Asynchronously create or retrieve a collection in ChromaDB."""
        client = await self.get_client_async()

        def sync_get_or_create():
            collections = client.list_collections()
            collection_names = [c.name for c in collections]

            if name in collection_names:
                return client.get_collection(name)
            else:
                print(f"Creating collection '{name}'")
                return client.create_collection(name)

        return await asyncio.to_thread(sync_get_or_create)

    def __create_collection(self, name="Document"):
        """Synchronously create a collection for compatibility"""
        with self.get_client() as client:
            collections = client.list_collections()
            collection_names = collections

            if name in collection_names:
                return client.get_collection(name)
            else:
                print(f"Creating collection '{name}'")
                return client.create_collection(name)

    async def store_document_async(self, text: str, embedding: list, metadata: dict, collection_name="Document"):
        """Asynchronously store a document with embedding and metadata in ChromaDB."""
        if not isinstance(embedding, list) or len(embedding) == 0:
            return {"status": "failed", "reason": "Invalid embedding"}

        collection = await self.get_or_create_collection(collection_name)
        document_id = f"{metadata.get('file_id', 'unknown_id')}_{metadata.get('chunk_number', '000')}"

        def sync_add():
            try:
                collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[document_id]
                )
                total_docs = collection.count()
                print(f"Document with ID: {document_id} inserted successfully! Total Documents: {total_docs}")
                return {"status": "success"}
            except Exception as e:
                    return {"status": "failed", "reason": str(e)}
                    
        return await asyncio.to_thread(sync_add)

    def store_document(self, text: str, embedding: list, metadata: dict, collection_name="Document"):
        """Store a document with embedding and metadata in ChromaDB (synchronous for compatibility)."""
        with self.get_client() as client:
            collection = self.__create_collection(collection_name)

            if not isinstance(embedding, list) or len(embedding) == 0:
                return {"status": "failed", "reason": "Invalid embedding"}

            document_id = f"{metadata.get('file_id', 'unknown_id')}_{metadata.get('chunk_number', '000')}"
            try:
                collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[document_id]
                )

                total_docs = collection.count()
                print(f"Document with ID: {document_id} inserted successfully! Total Documents: {total_docs}")
                return {"status": "success"}
            except Exception as e:
                return {"status": "failed", "reason": str(e)}

    async def get_document_async(self, collection_name="Document"):
        """Asynchronously retrieve documents from a ChromaDB collection."""
        client = await self.get_client_async()

        def sync_get():
            try:
                collection = client.get_collection(collection_name)
                response = collection.get(include=["documents", "metadatas"], limit=None)

                if not response or "documents" not in response:
                    return {"data": []}

                data = [{"text": doc, "metadata": meta} for doc, meta in
                        zip(response["documents"], response["metadatas"])]
                return {"data": data}

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        return await asyncio.to_thread(sync_get)

    def get_document(self, collection_name="Document"):
        """Retrieve documents from a ChromaDB collection (synchronous for compatibility)."""
        with self.get_client() as client:
            try:
                collection = client.get_collection(collection_name)
                response = collection.get(include=["documents", "metadatas"], limit=None)

                if not response or "documents" not in response:
                    return {"data": []}

                data = [{"text": doc, "metadata": meta} for doc, meta in
                        zip(response["documents"], response["metadatas"])]
                return {"data": data}

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def delete_document_async(self, source, hours=None, collection_name="Document"):
        """Asynchronously delete documents from ChromaDB based on filters."""
        client = await self.get_client_async()

        def sync_delete():
            try:
                collection = client.get_collection(collection_name)

                # If NO filter is provided → DELETE ENTIRE COLLECTION
                if source == "all":
                    client.delete_collection(collection_name)
                    return {"message": f"Deleted entire collection '{collection_name}'"}

                # Filter for selective deletion
                delete_filter = {"source": source.value}

                if hours is not None:
                    cutoff_timestamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
                    if source.value == "web":
                        delete_filter = {"updated_at": {"$lt": cutoff_timestamp}}
                    if source.value == "file":
                        delete_filter = {"uploaded_at": {"$lt": cutoff_timestamp}}

                # Batch Deletion Logic to avoid request limit errors
                batch_size = 5000  # ChromaDB limit
                total_deleted = 0

                while True:
                    matching_docs = collection.get(where=delete_filter, include=["metadatas"], limit=batch_size)
                    doc_ids = matching_docs.get("ids", [])
                    if not doc_ids:
                        break

                    # Delete the current batch
                    collection.delete(ids=doc_ids)
                    total_deleted += len(doc_ids)

                if total_deleted > 0:
                    print(f"\n\nDeleted {total_deleted} documents with filter: {delete_filter}")
                    return f"Deleted {total_deleted} documents with filter: {delete_filter}"
                else:
                    print(f"No matching documents found for filter: {delete_filter}")
                    return f"No matching documents found for filter: {delete_filter}"

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        return await asyncio.to_thread(sync_delete)

    def delete_document(self, source, hours=None, collection_name="Document"):
        """Delete documents from ChromaDB (synchronous for compatibility)."""
        with self.get_client() as client:
            try:
                collection = client.get_collection(collection_name)

                # If NO filter is provided → DELETE ENTIRE COLLECTION
                if source == "all":
                    client.delete_collection(collection_name)
                    return {"message": f"Deleted entire collection '{collection_name}'"}

                # Filter for selective deletion
                delete_filter = {"source": source.value}

                if hours is not None:
                    cutoff_timestamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
                    if source.value == "web":
                        delete_filter = {"updated_at": {"$lt": cutoff_timestamp}}
                    if source.value == "file":
                        delete_filter = {"uploaded_at": {"$lt": cutoff_timestamp}}

                # Batch Deletion Logic to avoid request limit errors
                batch_size = 5000  # ChromaDB limit
                total_deleted = 0

                while True:
                    matching_docs = collection.get(where=delete_filter, include=["metadatas"], limit=batch_size)
                    doc_ids = matching_docs.get("ids", [])
                    if not doc_ids:
                        break

                    # Delete the current batch
                    collection.delete(ids=doc_ids)
                    total_deleted += len(doc_ids)

                if total_deleted > 0:
                    print(f"\n\nDeleted {total_deleted} documents with filter: {delete_filter}")
                    return f"Deleted {total_deleted} documents with filter: {delete_filter}"
                else:
                    print(f"No matching documents found for filter: {delete_filter}")
                    return f"No matching documents found for filter: {delete_filter}"

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def __semantic_search_async(self, embedding: list, collection_name="Document", top_k=5,
                                      include_embeddings=False):
        """Asynchronously perform semantic search."""
        client = await self.get_client_async()

        def sync_search():
            try:
                collection = client.get_collection(collection_name)

                # Check if a collection is empty to avoid errors
                if collection.count() == 0:
                    return {"status": "success", "documents": []}

                include_fields = ["documents", "metadatas", "distances"]
                if include_embeddings:
                    include_fields.append("embeddings")

                response = collection.query(
                    query_embeddings=[embedding],
                    n_results=top_k,
                    include=include_fields
                )

                if not response or not response.get("documents"):
                    return {"status": "success", "documents": []}

                results = []
                for i, doc in enumerate(response["documents"][0]):  # Access the first list of documents
                    result = {
                        "id": response["ids"][0][i] if i < len(response["ids"][0]) else None,
                        "text": doc,
                        "metadata": response["metadatas"][0][i] if i < len(response["metadatas"][0]) else {},
                        "distance": response["distances"][0][i] if i < len(response["distances"][0]) else None,
                    }

                    if include_embeddings and "embeddings" in response:
                        result["embedding"] = response["embeddings"][0][i]

                    results.append(result)

                return {"status": "success", "documents": results}

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        return await asyncio.to_thread(sync_search)

    def __semantic_search(self, embedding: list, collection_name="Document", top_k=5, include_embeddings=False):
        """Perform semantic search (synchronous for compatibility)."""
        with self.get_client() as client:
            try:
                collection = client.get_collection(collection_name)

                # Check if a collection is empty to avoid errors
                if collection.count() == 0:
                    return {"status": "success", "documents": []}

                include_fields = ["documents", "metadatas", "distances"]
                if include_embeddings:
                    include_fields.append("embeddings")

                response = collection.query(
                    query_embeddings=[embedding],
                    n_results=top_k,
                    include=include_fields
                )

                if not response or not response.get("documents"):
                    return {"status": "success", "documents": []}

                results = []
                for i, doc in enumerate(response["documents"][0]):  # Access the first list of documents
                    result = {
                        "id": response["ids"][0][i] if i < len(response["ids"][0]) else None,
                        "text": doc,
                        "metadata": response["metadatas"][0][i] if i < len(response["metadatas"][0]) else {},
                        "distance": response["distances"][0][i] if i < len(response["distances"][0]) else None,
                    }

                    if include_embeddings and "embeddings" in response:
                        result["embedding"] = response["embeddings"][0][i]
                    results.append(result)

                return {"status": "success", "documents": results}

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))


    async def similar_search_async(self, query):
        """Asynchronously perform similar search with proper dependency injection."""
        try:


            query_embedding = await asyncio.to_thread(self._get_text_embedding, query)

            raw_response = await self.__semantic_search_async(query_embedding)

            structured_documents = []
            context_parts = []

            if raw_response.get("status") == "error":
                return f"Error during search: {raw_response.get('error', 'Unknown error')}"

            if raw_response.get("documents") and len(raw_response["documents"]) > 0:
                documents = raw_response["documents"]

                for i in range(min(6, len(documents))):
                    doc = documents[i]
                    structured_documents.append(doc)
                    distance = doc.get("distance", 0)

                    relevance = round((1 - distance) * 100, 2) if distance is not None else "Unknown"

                    source = doc["metadata"].get("source", "Unknown")
                    if source == "file":
                        filename = doc["metadata"].get("file_name", "Unnamed file")
                        context_parts.append(f"Source (Relevance: {relevance}%) -> File: {filename}\n{doc['text']}")

            top_k_match = "\n\n".join(context_parts) if context_parts else "No relevant context found."
            return top_k_match

        except Exception as e:
            raise e

    def similar_search(self, query):
        """Perform a similar search (synchronous for compatibility)."""
        try:
            query_embedding = self._get_text_embedding(query)
            raw_response = self.__semantic_search(query_embedding)

            # Restructure the response and format the top_k_match string
            structured_documents = []
            context_parts = []

            if raw_response.get("documents") and len(raw_response["documents"]) > 0:
                documents = raw_response["documents"]

                # Create structured documents and format the context for each
                for i in range(min(5, len(documents))):
                    doc = documents[i]
                    structured_documents.append(doc)

                    # Format the context for this document
                    source = doc["metadata"].get("source", "Unknown")
                    context_parts.append(f"Source - {source}: {doc['text']}")

            # Create the formatted top_k_match string
            # top_k_match = "\n\n".join(context_parts) if context_parts else "No relevant context found."
            return structured_documents

        except Exception as e:
            raise e


    @staticmethod
    def _get_text_embedding(sentence):
        embeddings = GLOBAL_EMBEDDING_MODEL.encode(sentence)
        return embeddings.tolist()

    @staticmethod
    def refine_query(user_query, previous_response):
        """
        Enhances the user's query by incorporating context from previous bot messages.
        This is a pure function with no side effects, so it's thread-safe.
        """
        if len(user_query.split()) > 3 or not previous_response:  # If the query is already meaningful, return it
            return user_query

        redefined_query = "previous_response: " + previous_response + ". user_query: " + user_query
        return redefined_query

