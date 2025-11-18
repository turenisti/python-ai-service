"""
Conversation State Manager - Tracks conversation state per session
"""
import uuid
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation state in-memory (no Redis for PoC)"""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def create_session(self, user_id: str, language: str = "id") -> str:
        """Create new conversation session"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "started_at": datetime.now().isoformat(),
            "conversation_history": [],
            "collected_data": {},
            "missing_fields": [
                "merchant_id",
                "report_type",
                "status_filter",
                # "date_range",  # REMOVED: Auto-calculated from cron_schedule
                "output_format",
                "cron_schedule",
                # "timezone",  # REMOVED: Optional, has default Asia/Jakarta
                "email_recipients"
            ],
            "next_action": "ask_merchant",
            "is_complete": False
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data"""
        return self.sessions.get(session_id)

    def update_session(
        self,
        session_id: str,
        collected_data: Optional[Dict] = None,
        missing_fields: Optional[List[str]] = None,
        next_action: Optional[str] = None,
        is_complete: Optional[bool] = None
    ) -> bool:
        """Update session data"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        if collected_data:
            # Log what's being updated
            for key, value in collected_data.items():
                old_value = session["collected_data"].get(key)
                if old_value != value:
                    logger.critical(f"[UPDATE_SESSION] Session {session_id[:8]}: {key}: '{old_value}' → '{value}'")

            session["collected_data"].update(collected_data)

            # Verify cron_schedule after update
            if 'cron_schedule' in collected_data:
                stored = session["collected_data"].get('cron_schedule')
                logger.critical(f"[VERIFY_UPDATE] Session {session_id[:8]}: cron_schedule stored = '{stored}'")

            # Auto-update missing fields based on what's collected
            self._update_missing_fields(session_id)

        if missing_fields is not None:
            session["missing_fields"] = missing_fields

        if next_action:
            session["next_action"] = next_action

        if is_complete is not None:
            session["is_complete"] = is_complete

        return True

    def _update_missing_fields(self, session_id: str):
        """Update missing fields list based on collected data"""
        session = self.sessions[session_id]
        collected = session["collected_data"]

        all_fields = [
            "merchant_id",
            "report_type",
            "status_filter",
            # "date_range",  # Optional: Auto-calculated from cron
            "output_format",
            "cron_schedule",
            # "timezone",  # Optional: Has default
            "email_recipients"
        ]

        missing = [field for field in all_fields if field not in collected or not collected[field]]
        session["missing_fields"] = missing

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> bool:
        """Add message to conversation history"""
        if session_id not in self.sessions:
            return False

        self.sessions[session_id]["conversation_history"].append({
            "role": role,
            "content": content
        })
        return True

    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for a session"""
        session = self.get_session(session_id)
        if not session:
            return []
        return session.get("conversation_history", [])

    def check_completeness(self, session_id: str) -> bool:
        """Check if all required data is collected"""
        session = self.get_session(session_id)
        if not session:
            return False

        collected = session["collected_data"]
        required_fields = [
            "merchant_id",
            # "date_range",  # Optional: Auto-calculated
            "output_format",
            "cron_schedule",
            # "timezone",  # Optional: Has default
            "email_recipients"
        ]

        # Auto-fill defaults if not specified
        if "status_filter" not in collected:
            collected["status_filter"] = ["PAID", "CAPTURED"]  # Default: sukses
        if "report_type" not in collected:
            collected["report_type"] = "transaction"  # Default
        if "timezone" not in collected:
            collected["timezone"] = "Asia/Jakarta"  # Default

        # Check if all required fields are collected
        for field in required_fields:
            if field not in collected or not collected[field]:
                return False

        return True

    def determine_next_action(self, session_id: str) -> str:
        """Determine what to ask next based on missing data"""
        session = self.get_session(session_id)
        if not session:
            return "ask_merchant"

        collected = session["collected_data"]

        # Priority order
        if "merchant_id" not in collected:
            return "ask_merchant"
        if "report_type" not in collected:
            return "ask_report_type"
        if "status_filter" not in collected:
            return "ask_status"
        # Removed: date_range (auto-calculated from cron)
        if "output_format" not in collected:
            return "ask_format"
        if "cron_schedule" not in collected:
            return "ask_schedule"
        # Removed: timezone (has default)
        if "email_recipients" not in collected:
            return "ask_recipients"

        return "confirm"

    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def get_all_sessions(self) -> Dict[str, Dict]:
        """Get all sessions (for debugging)"""
        return self.sessions


# Quick test
if __name__ == "__main__":
    manager = ConversationManager()

    # Test create session
    session_id = manager.create_session("test@example.com", language="id")
    print(f"✅ Created session: {session_id}")

    # Test get session
    session = manager.get_session(session_id)
    print(f"✅ Retrieved session: {session['user_id']}")

    # Test add message
    manager.add_message(session_id, "user", "buatkan report transaksi")
    manager.add_message(session_id, "assistant", "Baik! Untuk merchant apa?")
    print(f"✅ Added messages: {len(manager.get_conversation_history(session_id))}")

    # Test update collected data
    manager.update_session(
        session_id,
        collected_data={"merchant_id": "FINPAY770"}
    )
    print(f"✅ Updated data: {session['collected_data']}")

    # Test determine next action
    next_action = manager.determine_next_action(session_id)
    print(f"✅ Next action: {next_action}")

    # Test check completeness
    is_complete = manager.check_completeness(session_id)
    print(f"✅ Is complete: {is_complete}")

    print("\n✅ All tests passed!")
