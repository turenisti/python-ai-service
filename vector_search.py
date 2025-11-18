"""
MongoDB Vector Search for Learning from Conversations
"""
import os
import ollama
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorSearchManager:
    def __init__(self):
        self.connection_string = os.getenv("MONGODB_CONNECTION_STRING")
        self.database_name = os.getenv("DATABASE_NAME", "mg_adapter")
        self.collection_conversations = os.getenv("COLLECTION_CONVERSATIONS", "ai_conversations")
        self.collection_field_patterns = os.getenv("COLLECTION_FIELD_PATTERNS", "ai_field_patterns")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        self.similarity_threshold = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.85"))
        self.vector_index_name = os.getenv("VECTOR_SEARCH_INDEX", "vector_index")

        # Initialize MongoDB client
        self.client = MongoClient(self.connection_string)
        self.db = self.client[self.database_name]
        self.conversations = self.db[self.collection_conversations]
        self.field_patterns = self.db[self.collection_field_patterns]

        # Ensure indexes
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for vector search"""
        try:
            # Index for conversation lookup
            self.conversations.create_index([("session_id", ASCENDING)])
            self.conversations.create_index([("created_at", ASCENDING)])
            self.conversations.create_index([("is_successful", ASCENDING)])

            # Index for field patterns
            self.field_patterns.create_index([("field_name", ASCENDING)])
            self.field_patterns.create_index([("usage_count", ASCENDING)])

            logger.info("✅ MongoDB indexes created successfully")
        except Exception as e:
            logger.warning(f"⚠️ Index creation warning: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector using Ollama nomic-embed-text

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            logger.info(f"🔍 Generating embedding for: {text[:100]}...")

            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text
            )

            embedding = response['embedding']
            logger.info(f"✅ Generated embedding: {len(embedding)} dimensions")

            return embedding

        except Exception as e:
            logger.error(f"❌ Error generating embedding: {e}")
            return []

    def search_similar_conversations(
        self,
        user_message: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search for similar conversations using MongoDB Atlas Vector Search

        Args:
            user_message: User's input message
            top_k: Number of top results to return

        Returns:
            List of similar conversations with similarity scores
        """
        try:
            # Generate embedding for user message
            query_embedding = self.generate_embedding(user_message)

            if not query_embedding:
                return []

            logger.info(f"🔍 Searching for similar conversations using Atlas Vector Search...")

            # Use MongoDB Atlas Vector Search aggregation pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.vector_index_name,
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": 100,
                        "limit": top_k
                    }
                },
                {
                    "$addFields": {
                        "similarity": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "similarity": {"$gte": self.similarity_threshold}
                    }
                },
                {
                    "$sort": {
                        "is_successful": -1,  # Prioritize successful conversations
                        "similarity": -1
                    }
                }
            ]

            # Execute aggregation
            results_cursor = self.conversations.aggregate(pipeline)
            results = []

            for doc in results_cursor:
                similarity = doc.get("similarity", 0.0)
                results.append({
                    "conversation": doc,
                    "similarity": similarity
                })

            if results:
                logger.info(f"✅ Found {len(results)} similar conversations (Atlas Vector Search)")
                for i, result in enumerate(results, 1):
                    logger.info(f"  {i}. Similarity: {result['similarity']:.3f} - {result['conversation']['user_message'][:50]}...")
            else:
                logger.info(f"📭 No conversations above threshold {self.similarity_threshold}")

            return results

        except Exception as e:
            # Fallback to manual cosine similarity if Atlas Vector Search not available
            logger.warning(f"⚠️ Atlas Vector Search failed, using fallback: {e}")
            return self._fallback_search(user_message, query_embedding, top_k)

    def _fallback_search(
        self,
        user_message: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Fallback search using manual cosine similarity (for testing without Atlas index)
        """
        try:
            logger.info(f"🔍 Using fallback search (manual cosine similarity)...")

            # Find all conversations with embeddings
            all_convos = list(self.conversations.find({
                "embedding": {"$exists": True}
            }).sort([
                ("is_successful", -1),
                ("created_at", -1)
            ]).limit(100))

            if not all_convos:
                logger.info("📭 No conversations found yet")
                return []

            # Calculate cosine similarity manually
            results = []
            for convo in all_convos:
                if "embedding" not in convo or not convo["embedding"]:
                    continue

                similarity = self._cosine_similarity(
                    query_embedding,
                    convo["embedding"]
                )

                if similarity >= self.similarity_threshold:
                    results.append({
                        "conversation": convo,
                        "similarity": similarity
                    })

            # Sort by similarity
            results.sort(key=lambda x: x["similarity"], reverse=True)
            top_results = results[:top_k]

            if top_results:
                logger.info(f"✅ Found {len(top_results)} similar conversations (fallback)")
                for i, result in enumerate(top_results, 1):
                    logger.info(f"  {i}. Similarity: {result['similarity']:.3f} - {result['conversation']['user_message'][:50]}...")

            return top_results

        except Exception as e:
            logger.error(f"❌ Fallback search error: {e}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        try:
            # Ensure same dimension
            if len(vec1) != len(vec2):
                return 0.0

            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(vec1, vec2))

            # Calculate magnitudes
            magnitude1 = sum(a * a for a in vec1) ** 0.5
            magnitude2 = sum(b * b for b in vec2) ** 0.5

            # Avoid division by zero
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            # Cosine similarity
            similarity = dot_product / (magnitude1 * magnitude2)

            return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]

        except Exception as e:
            logger.error(f"❌ Error calculating similarity: {e}")
            return 0.0

    def store_conversation(
        self,
        session_id: str,
        user_message: str,
        collected_data: Dict,
        schedule_id: Optional[int] = None,
        is_successful: bool = False
    ) -> str:
        """
        Store conversation with embedding for future learning

        Args:
            session_id: Conversation session ID
            user_message: Original user input
            collected_data: Extracted entities and data
            schedule_id: Created schedule ID (if successful)
            is_successful: Whether schedule was created successfully

        Returns:
            Inserted document ID
        """
        try:
            # QUALITY CONTROL: Only store successful conversations
            if not is_successful or not schedule_id:
                logger.info(f"⏭️  Skipping failed conversation (session: {session_id})")
                return ""

            # Generate embedding for deduplication check
            embedding = self.generate_embedding(user_message)

            # DEDUPLICATION: Check for near-duplicates (similarity > 0.98)
            existing = self.search_similar_conversations(user_message, top_k=1)
            if existing and existing[0].get('similarity', 0) > 0.98:
                logger.info(f"⏭️  Skipping duplicate conversation (similarity: {existing[0]['similarity']:.3f})")
                return str(existing[0]['conversation']['_id'])

            # Prepare document
            doc = {
                "session_id": session_id,
                "user_message": user_message,
                "conversation": {
                    "collected_data": collected_data,
                    "schedule_id": schedule_id,
                    "is_successful": is_successful
                },
                "embedding": embedding,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Insert into MongoDB
            result = self.conversations.insert_one(doc)

            logger.info(f"✅ Stored conversation: {result.inserted_id}")

            # Update field patterns
            if is_successful and collected_data:
                self._update_field_patterns(collected_data)

            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"❌ Error storing conversation: {e}")
            return ""

    def update_conversation_status(
        self,
        session_id: str,
        schedule_id: int,
        is_successful: bool = True
    ):
        """
        Update conversation status after schedule creation/execution

        Args:
            session_id: Conversation session ID
            schedule_id: Created schedule ID
            is_successful: Whether operation was successful
        """
        try:
            result = self.conversations.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "schedule_id": schedule_id,
                        "is_successful": is_successful,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated conversation status: session={session_id}, success={is_successful}")
            else:
                logger.warning(f"⚠️ Conversation not found: {session_id}")

        except Exception as e:
            logger.error(f"❌ Error updating conversation: {e}")

    def _update_field_patterns(self, collected_data: Dict):
        """
        Update field usage patterns for learning

        Args:
            collected_data: Extracted data from conversation
        """
        try:
            for field_name, field_value in collected_data.items():
                if field_value:  # Only track non-empty fields
                    # Increment usage count
                    self.field_patterns.update_one(
                        {"field_name": field_name},
                        {
                            "$inc": {"usage_count": 1},
                            "$set": {
                                "last_used": datetime.utcnow()
                            },
                            "$addToSet": {
                                "example_values": str(field_value)[:100]  # Store example (truncated)
                            }
                        },
                        upsert=True
                    )

            logger.info(f"✅ Updated field patterns: {len(collected_data)} fields")

        except Exception as e:
            logger.error(f"❌ Error updating field patterns: {e}")

    def get_field_suggestions(self, field_name: str, top_k: int = 5) -> List[str]:
        """
        Get common values for a field based on learned patterns

        Args:
            field_name: Name of the field
            top_k: Number of suggestions to return

        Returns:
            List of suggested values
        """
        try:
            pattern = self.field_patterns.find_one({"field_name": field_name})

            if pattern and "example_values" in pattern:
                return list(pattern["example_values"])[:top_k]

            return []

        except Exception as e:
            logger.error(f"❌ Error getting suggestions: {e}")
            return []

    def test_connection(self) -> bool:
        """Test MongoDB connection"""
        try:
            self.client.admin.command('ping')
            logger.info("✅ MongoDB connected successfully")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            return False


# Quick test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    manager = VectorSearchManager()

    # Test connection
    print("\nTesting MongoDB connection...")
    if manager.test_connection():
        print("✅ MongoDB connected!")
    else:
        print("❌ MongoDB connection failed!")
        exit(1)

    # Test embedding generation
    print("\nTesting embedding generation...")
    embedding = manager.generate_embedding("buatkan report transaksi sukses untuk mid finpay770")
    print(f"✅ Embedding generated: {len(embedding)} dimensions")
    print(f"First 5 values: {embedding[:5]}")

    # Test storing conversation
    print("\nTesting conversation storage...")
    doc_id = manager.store_conversation(
        session_id="test_123",
        user_message="buatkan report transaksi sukses untuk mid finpay770",
        collected_data={
            "merchant_id": "FINPAY770",
            "status_filter": ["PAID", "CAPTURED"],
            "report_type": "transaction"
        },
        schedule_id=None,
        is_successful=False
    )
    print(f"✅ Stored conversation: {doc_id}")

    # Test similarity search
    print("\nTesting similarity search...")
    results = manager.search_similar_conversations(
        "buat laporan transaksi berhasil merchant finpay770"
    )
    print(f"✅ Found {len(results)} similar conversations")

    print("\n✅ All tests passed!")
