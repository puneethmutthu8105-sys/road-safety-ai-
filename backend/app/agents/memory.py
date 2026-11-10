"""
Agent Memory using ChromaDB vector store.
Each agent gets its own collection for semantic retrieval.
"""
import uuid
import logging
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Any] = None


def get_chroma_client():
    global _client
    if _client is None:
        if not CHROMA_AVAILABLE:
            return None
        try:
            _client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        except Exception:
            try:
                _client = chromadb.Client()
            except Exception:
                return None
    return _client


class AgentMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.collection_name = f"agent_{agent_name}_memory"
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            client = get_chroma_client()
            if client is None:
                return None
            try:
                self._collection = client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning(f"[Memory] collection init failed: {e}")
        return self._collection

    def store(self, content: str, metadata: Dict[str, Any] = None, doc_id: str = None):
        """Store a text entry in agent memory."""
        try:
            col = self._get_collection()
            if col is None:
                return
            doc_id = doc_id or str(uuid.uuid4())
            col.add(
                documents=[content],
                metadatas=[metadata or {}],
                ids=[doc_id]
            )
        except Exception as e:
            logger.warning(f"[Memory] store failed: {e}")

    def retrieve(self, query: str, n_results: int = 5) -> List[str]:
        """Retrieve semantically similar memories."""
        try:
            col = self._get_collection()
            if col is None:
                return []
            results = col.query(query_texts=[query], n_results=n_results)
            return results.get("documents", [[]])[0]
        except Exception as e:
            logger.warning(f"[Memory] retrieve failed: {e}")
            return []

    def clear(self):
        try:
            client = get_chroma_client()
            client.delete_collection(self.collection_name)
            self._collection = None
        except Exception as e:
            logger.warning(f"[Memory] clear failed: {e}")
