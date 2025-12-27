"""Vector knowledge base module (Pinecone + embeddings)."""

from typing import Any, Dict, List

import pinecone
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Pinecone
from openai import OpenAI

from src.core.config import settings

# Initialize OpenAI client (do not rely on env vars)
client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.openai_base_url,
)


class KnowledgeBase:
    """Knowledge base wrapper for storing/searching texts in a vector DB."""

    def __init__(self) -> None:
        """Initialize the knowledge base."""
        # Initialize Pinecone
        pinecone.init(
            api_key=settings.PINECONE_API_KEY,
            host=settings.PINECONE_HOST,
        )

        # Create the index if it does not exist
        if settings.PINECONE_INDEX_NAME not in pinecone.list_indexes():
            pinecone.create_index(
                name=settings.PINECONE_INDEX_NAME,
                dimension=1536,  # Dimension for text-embedding-3-small
                metric="cosine",
            )

        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            client=client,
            model=settings.OPENAI_EMBEDDING_MODEL,
        )

        # Connect to the Pinecone index
        self.index = pinecone.Index(settings.PINECONE_INDEX_NAME)

        # Initialize vector store wrapper
        self.vectorstore = Pinecone(
            index=self.index,
            embedding=self.embeddings,
            text_key="text",
        )

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    async def add_knowledge(
        self, texts: List[str], metadata: List[Dict[str, Any]] = None
    ) -> None:
        """Add texts to the knowledge base.

        Args:
            texts: List of texts to add
            metadata: List of metadata objects for the texts
        """
        if metadata is None:
            metadata = [{} for _ in texts]

        # Split texts into chunks
        documents = []
        for text, meta in zip(texts, metadata):
            chunks = self.text_splitter.split_text(text)
            for chunk in chunks:
                documents.append({"text": chunk, "metadata": meta})

        # Add to the vector store
        self.vectorstore.add_texts(
            texts=[doc["text"] for doc in documents],
            metadatas=[doc["metadata"] for doc in documents],
        )

    async def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant information by query.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of documents with metadata and relevance score
        """
        results = self.vectorstore.similarity_search_with_score(query, k=k)

        return [
            {
                "text": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in results
        ]

    async def get_relevant_context(self, query: str, k: int = 3) -> str:
        """Get relevant context for a query.

        Args:
            query: Search query
            k: Number of results

        Returns:
            Combined text of relevant documents
        """
        results = await self.search(query, k=k)
        return "\n\n".join([r["text"] for r in results])

    async def initialize_knowledge_base(self) -> None:
        """Initialize the knowledge base with seed data."""
        # Medical information
        medical_info = [
            {
                "text": (
                    "Dementia is a syndrome in which memory, thinking, behavior, "
                    "and the ability to perform everyday activities deteriorate."
                ),
                "metadata": {"type": "definition", "topic": "dementia"},
            },
            {
                "text": (
                    "Common dementia symptoms include memory problems, speech difficulties, "
                    "disorientation, and changes in behavior and personality."
                ),
                "metadata": {"type": "symptoms", "topic": "dementia"},
            },
        ]

        # Care guidelines
        care_guidelines = [
            {
                "text": (
                    "When caring for a person with dementia, it is important to maintain a regular routine, "
                    "create a safe environment, and use simple instructions."
                ),
                "metadata": {"type": "care_guidelines", "topic": "daily_care"},
            },
        ]

        # Crisis protocols
        crisis_protocols = [
            {
                "text": (
                    "In a crisis situation: stay calm, assess the level of risk, and call emergency services if needed."
                ),
                "metadata": {"type": "crisis_protocol", "topic": "emergency"},
            },
        ]

        # Add all seed texts to the knowledge base
        all_texts = [
            item["text"] for item in medical_info + care_guidelines + crisis_protocols
        ]
        all_metadata = [
            item["metadata"]
            for item in medical_info + care_guidelines + crisis_protocols
        ]

        await self.add_knowledge(all_texts, all_metadata)
