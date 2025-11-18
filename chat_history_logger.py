"""
Chat History Logger - Save full conversation history to MongoDB
Separate from RAG embeddings for analysis and improvement
"""
import os
import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ChatHistoryLogger:
    """Log full conversation history to ai_chat_history collection"""

    def __init__(self, mongo_uri: str, database: str):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[database]
        self.collection = self.db['ai_chat_history']

        # Create indexes for better query performance
        self._create_indexes()

        logger.info("✅ ChatHistoryLogger initialized")

    def _create_indexes(self):
        """Create MongoDB indexes"""
        try:
            self.collection.create_index([("session_id", ASCENDING)], unique=True)
            self.collection.create_index([("user_id", ASCENDING)])
            self.collection.create_index([("created_at", DESCENDING)])
            self.collection.create_index([("is_complete", ASCENDING)])
            logger.info("✅ Chat history indexes created")
        except Exception as e:
            logger.warning(f"⚠️  Index creation failed (may already exist): {e}")

    def create_session(
        self,
        session_id: str,
        user_id: str,
        language: str = "id",
        user_context: Optional[Dict] = None
    ) -> str:
        """
        Create new chat history session

        Args:
            session_id: Unique session ID
            user_id: User email/ID
            language: Conversation language
            user_context: {username, email, allowed_merchant_ids}

        Returns:
            session_id
        """
        try:
            doc = {
                "session_id": session_id,
                "user_id": user_id,
                "language": language,
                "user_info": user_context or {},
                "messages": [],
                "collected_data": {},
                "missing_fields": [],
                "is_complete": False,
                "schedule_id": None,
                "metadata": {
                    "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
                    "llm_model": os.getenv("CLAUDE_MODEL") if os.getenv("LLM_PROVIDER") == "claude" else os.getenv("OLLAMA_MODEL"),
                    "total_messages": 0,
                    "total_tokens": 0,
                    "session_duration_seconds": 0
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "completed_at": None
            }

            self.collection.insert_one(doc)
            logger.info(f"📝 Created chat history session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"❌ Failed to create chat history session: {e}")
            return session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):
        """
        Add message to conversation history

        Args:
            session_id: Session ID
            role: 'user' or 'assistant'
            content: Message content
        """
        try:
            self.collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "messages": {
                            "role": role,
                            "content": content,
                            "timestamp": datetime.utcnow()
                        }
                    },
                    "$inc": {"metadata.total_messages": 1},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            logger.debug(f"💬 Added {role} message to session {session_id}")

        except Exception as e:
            logger.error(f"❌ Failed to add message: {e}")

    def update_collected_data(
        self,
        session_id: str,
        collected_data: Dict,
        missing_fields: List[str]
    ):
        """
        Update collected data and missing fields

        Args:
            session_id: Session ID
            collected_data: Current collected data
            missing_fields: List of missing field names
        """
        try:
            self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "collected_data": collected_data,
                        "missing_fields": missing_fields,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.debug(f"📊 Updated collected data for session {session_id}")

        except Exception as e:
            logger.error(f"❌ Failed to update collected data: {e}")

    def add_token_usage(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int
    ):
        """
        Add token usage (for Claude/paid LLMs)

        Args:
            session_id: Session ID
            input_tokens: Input token count
            output_tokens: Output token count
        """
        try:
            self.collection.update_one(
                {"session_id": session_id},
                {
                    "$inc": {
                        "metadata.total_tokens": input_tokens + output_tokens
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

        except Exception as e:
            logger.error(f"❌ Failed to add token usage: {e}")

    def mark_complete(
        self,
        session_id: str,
        schedule_id: Optional[int] = None,
        success: bool = True
    ):
        """
        Mark session as complete

        Args:
            session_id: Session ID
            schedule_id: Created schedule ID (if successful)
            success: Whether schedule was created successfully
        """
        try:
            # Calculate session duration
            session = self.collection.find_one({"session_id": session_id})
            if session:
                created_at = session.get("created_at")
                duration = (datetime.utcnow() - created_at).total_seconds()
            else:
                duration = 0

            self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "is_complete": True,
                        "schedule_id": schedule_id,
                        "success": success,
                        "completed_at": datetime.utcnow(),
                        "metadata.session_duration_seconds": duration,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"✅ Marked session {session_id} as complete (schedule_id: {schedule_id})")

        except Exception as e:
            logger.error(f"❌ Failed to mark session complete: {e}")

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get chat history session"""
        try:
            return self.collection.find_one({"session_id": session_id})
        except Exception as e:
            logger.error(f"❌ Failed to get session: {e}")
            return None

    def get_user_sessions(
        self,
        user_id: str,
        limit: int = 10,
        completed_only: bool = False
    ) -> List[Dict]:
        """Get user's chat sessions"""
        try:
            query = {"user_id": user_id}
            if completed_only:
                query["is_complete"] = True

            return list(
                self.collection
                .find(query)
                .sort("created_at", DESCENDING)
                .limit(limit)
            )

        except Exception as e:
            logger.error(f"❌ Failed to get user sessions: {e}")
            return []

    def get_stats(self) -> Dict:
        """Get overall statistics"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_sessions": {"$sum": 1},
                        "completed": {"$sum": {"$cond": ["$is_complete", 1, 0]}},
                        "successful": {"$sum": {"$cond": [{"$ne": ["$schedule_id", None]}, 1, 0]}},
                        "avg_messages": {"$avg": "$metadata.total_messages"},
                        "avg_tokens": {"$avg": "$metadata.total_tokens"},
                        "avg_duration": {"$avg": "$metadata.session_duration_seconds"}
                    }
                }
            ]

            result = list(self.collection.aggregate(pipeline))

            if result:
                stats = result[0]
                stats.pop("_id", None)
                return stats

            return {}

        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}

    def test_connection(self) -> bool:
        """Test MongoDB connection"""
        try:
            self.collection.find_one()
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB connection test failed: {e}")
            return False


# Quick test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logger = ChatHistoryLogger(
        mongo_uri=os.getenv("MONGODB_CONNECTION_STRING"),
        database=os.getenv("DATABASE_NAME")
    )

    # Test
    session_id = "test-session-123"

    print("Testing ChatHistoryLogger...")

    # Create session
    logger.create_session(
        session_id=session_id,
        user_id="test@example.com",
        user_context={
            "username": "test_user",
            "allowed_merchant_ids": ["FINPAY770"]
        }
    )

    # Add messages
    logger.add_message(session_id, "user", "Mau buat report")
    logger.add_message(session_id, "assistant", "Merchant ID-nya?")

    # Update collected data
    logger.update_collected_data(
        session_id,
        {"merchant_id": "FINPAY770"},
        ["report_type", "output_format"]
    )

    # Mark complete
    logger.mark_complete(session_id, schedule_id=999)

    # Get stats
    stats = logger.get_stats()
    print(f"\n✅ Stats: {stats}")

    print("\n✅ ChatHistoryLogger test completed!")
