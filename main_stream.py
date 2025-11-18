"""
Streaming endpoint for chat (optional - for real-time response)
"""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from ai_agent import AIAgent
from conversation_manager import ConversationManager
from entity_parser import EntityParser

app = FastAPI()
ai_agent = AIAgent()
conversation_manager = ConversationManager()
entity_parser = EntityParser()


class ChatStreamRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: str = "ai-assistant"
    language: str = "id"


@app.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """
    Chat with streaming response (Server-Sent Events)
    """
    async def generate():
        try:
            # Create or get session
            if not request.session_id:
                session_id = conversation_manager.create_session(
                    request.user_id,
                    request.language
                )
            else:
                session_id = request.session_id

            # Extract entities
            entities = entity_parser.parse_message(request.message)
            if entities:
                conversation_manager.update_session(
                    session_id,
                    collected_data=entities
                )

            # Add user message
            conversation_manager.add_message(session_id, "user", request.message)

            # Get history
            history = conversation_manager.get_conversation_history(session_id)

            # Stream AI response
            full_response = ""
            for chunk in ai_agent.chat_stream(
                request.message,
                conversation_history=history[-10:],
                language=request.language
            ):
                full_response += chunk
                # Send as SSE
                yield f"data: {json.dumps({'chunk': chunk, 'session_id': session_id})}\n\n"

            # Add to history
            conversation_manager.add_message(session_id, "assistant", full_response)

            # Check completeness
            is_complete = conversation_manager.check_completeness(session_id)
            next_action = conversation_manager.determine_next_action(session_id)

            conversation_manager.update_session(
                session_id,
                next_action=next_action,
                is_complete=is_complete
            )

            # Send final status
            session = conversation_manager.get_session(session_id)
            yield f"data: {json.dumps({'done': True, 'is_complete': is_complete, 'collected_data': session['collected_data']})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
