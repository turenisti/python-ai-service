"""
Python AI Service - FastAPI Application
Conversational AI for creating scheduled reports
"""
import os
import httpx
import json
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, AsyncGenerator
from dotenv import load_dotenv

# Setup logging
logger = logging.getLogger(__name__)

from ai_agent import AIAgent
from conversation_manager import ConversationManager
from entity_parser import EntityParser
from payload_builder import PayloadBuilder
from vector_search import VectorSearchManager
from chat_history_logger import ChatHistoryLogger
from merchant_validator import MerchantValidator
from cron_converter import CronConverter
from summary_builder import SummaryBuilder

# Load environment
load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="AI Report Assistant",
    description="Conversational AI for creating scheduled reports",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
ai_agent = AIAgent()
conversation_manager = ConversationManager()
entity_parser = EntityParser()
payload_builder = PayloadBuilder()
vector_search = VectorSearchManager()
chat_history = ChatHistoryLogger(
    mongo_uri=os.getenv("MONGODB_CONNECTION_STRING"),
    database=os.getenv("DATABASE_NAME")
)
merchant_validator = MerchantValidator()
cron_converter = CronConverter()
summary_builder = SummaryBuilder()

# Config
GO_API_URL = os.getenv("GO_API_URL", "http://localhost:3000")
SCHEDULES_COMPLETE_PATH = os.getenv("GO_API_SCHEDULES_COMPLETE", "/api/schedules/complete")

# Model configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
PRODUCTION_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
TRAINING_MODEL = os.getenv("OLLAMA_MODEL_TRAINING", "qwen2.5:0.5b-instruct")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")


# Helper Functions
def build_collected_context(collected_data: Dict, language: str = "id") -> str:
    """
    Build context message showing what data has been collected

    Args:
        collected_data: Dictionary of collected fields
        language: Language code

    Returns:
        Context string for AI
    """
    if not collected_data:
        return ""

    context_parts = []

    if language == "id":
        # Indonesian context
        if collected_data.get('merchant_id'):
            context_parts.append(f"Merchant: {collected_data['merchant_id']}")
        if collected_data.get('report_type'):
            type_map = {"transaction": "Transaksi", "settlement": "Settlement"}
            report_type = type_map.get(collected_data['report_type'], collected_data['report_type'])
            context_parts.append(f"Jenis: {report_type}")
        if collected_data.get('status_filter'):
            context_parts.append(f"Status: {collected_data['status_filter']}")
        if collected_data.get('date_range'):
            range_map = {
                "last_7_days": "7 hari terakhir",
                "last_30_days": "30 hari terakhir",
                "this_month": "Bulan ini"
            }
            date_range = range_map.get(collected_data['date_range'], collected_data['date_range'])
            context_parts.append(f"Periode: {date_range}")
        if collected_data.get('output_format'):
            format_map = {"xlsx": "Excel", "csv": "CSV", "pdf": "PDF"}
            output_format = format_map.get(collected_data['output_format'], collected_data['output_format'].upper())
            context_parts.append(f"Format: {output_format}")
        if collected_data.get('cron_schedule'):
            readable = cron_converter.to_readable(collected_data['cron_schedule'], "id")
            context_parts.append(f"Jadwal: {readable}")
        if collected_data.get('email_recipients'):
            recipients = collected_data['email_recipients']
            if isinstance(recipients, list):
                recipients = ', '.join(recipients)
            context_parts.append(f"Email: {recipients}")

        return f"\n[DATA TERKUMPUL: {' | '.join(context_parts)}]" if context_parts else ""
    else:
        # English context
        if collected_data.get('merchant_id'):
            context_parts.append(f"Merchant: {collected_data['merchant_id']}")
        if collected_data.get('report_type'):
            context_parts.append(f"Type: {collected_data['report_type']}")
        if collected_data.get('status_filter'):
            context_parts.append(f"Status: {collected_data['status_filter']}")
        if collected_data.get('date_range'):
            context_parts.append(f"Period: {collected_data['date_range']}")
        if collected_data.get('output_format'):
            context_parts.append(f"Format: {collected_data['output_format'].upper()}")
        if collected_data.get('cron_schedule'):
            readable = cron_converter.to_readable(collected_data['cron_schedule'], "en")
            context_parts.append(f"Schedule: {readable}")
        if collected_data.get('email_recipients'):
            recipients = collected_data['email_recipients']
            if isinstance(recipients, list):
                recipients = ', '.join(recipients)
            context_parts.append(f"Email: {recipients}")

        return f"\n[COLLECTED DATA: {' | '.join(context_parts)}]" if context_parts else ""


# Request/Response Models
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID (optional for first message)")
    user_id: str = Field(default="ai-assistant", description="User ID")
    language: str = Field(default="id", description="Language (id/en)")
    user_context: Optional[Dict] = Field(None, description="User context with allowed_merchant_ids")


class ChatResponse(BaseModel):
    message: str
    session_id: str
    collected_data: Dict
    missing_fields: List[str]
    next_action: str
    is_complete: bool


class ConfirmRequest(BaseModel):
    session_id: str
    user_id: str = "ai-assistant"


class ConfirmResponse(BaseModel):
    success: bool
    message: str
    schedule_id: Optional[int] = None
    config_id: Optional[int] = None
    payload: Optional[Dict] = None


# Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AI Report Assistant",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check"""
    llm_ok = ai_agent.test_connection()
    mongodb_ok = vector_search.test_connection()

    # Build response based on provider
    model_info = {
        "provider": LLM_PROVIDER,
        "model": CLAUDE_MODEL if LLM_PROVIDER == "claude" else ai_agent.model
    }

    return {
        "status": "healthy" if (llm_ok and mongodb_ok) else "degraded",
        "llm": "connected" if llm_ok else "disconnected",
        "mongodb": "connected" if mongodb_ok else "disconnected",
        **model_info,
        "embedding_model": vector_search.embedding_model
    }


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Chat with AI assistant (streaming response)

    Returns Server-Sent Events (SSE) stream with:
    - data: AI response chunks
    - event: status updates
    - done: completion signal
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Create or get session
            if not request.session_id:
                session_id = conversation_manager.create_session(
                    request.user_id,
                    request.language
                )

                # Create chat history session
                chat_history.create_session(
                    session_id=session_id,
                    user_id=request.user_id,
                    language=request.language,
                    user_context=request.user_context
                )
            else:
                session_id = request.session_id
                session = conversation_manager.get_session(session_id)
                if not session:
                    yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
                    return

            # Send session ID
            yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

            # Handle /verify command - show summary
            if request.message.strip().lower() == "/verify":
                session = conversation_manager.get_session(session_id)
                collected_data = session.get("collected_data", {})

                if collected_data:
                    summary = summary_builder.build(collected_data, request.language)
                    if request.language == "id":
                        response_msg = f"📋 Data yang sudah terkumpul:\n\n{summary}\n\n{'✅ Data lengkap! Ketik /confirm untuk eksekusi.' if session.get('is_complete') else '⏳ Masih ada yang kurang.'}"
                    else:
                        response_msg = f"📋 Collected data:\n\n{summary}\n\n{'✅ Data complete! Type /confirm to execute.' if session.get('is_complete') else '⏳ Still missing some data.'}"
                else:
                    response_msg = "Belum ada data yang terkumpul." if request.language == "id" else "No data collected yet."

                # Add to chat history
                chat_history.add_message(session_id, "user", request.message)
                chat_history.add_message(session_id, "assistant", response_msg)

                # Send response
                yield f"data: {json.dumps({'chunk': response_msg})}\n\n"
                yield f"event: done\ndata: {json.dumps({'collected_data': collected_data, 'missing_fields': session.get('missing_fields', [])})}\n\n"
                return

            # Get allowed merchants
            allowed_merchants = None
            if request.user_context:
                allowed_merchants = request.user_context.get("allowed_merchant_ids")

            # Check vector search (for reference, but ALWAYS parse current message)
            yield f"event: status\ndata: {json.dumps({'status': 'Checking cache...'})}\n\n"

            similar_convos = vector_search.search_similar_conversations(
                request.message,
                top_k=1
            )

            # ALWAYS parse current message to catch corrections and new data
            # This ensures user can correct previously provided values
            entities = entity_parser.parse_message(request.message, allowed_merchants)
            logger.critical(f"[ENTITY_PARSE] Session {session_id[:8]}: Parsed entities = {entities}")

            # Check if we have cache hit (for logging/metrics)
            if similar_convos and len(similar_convos) > 0:
                cached_convo = similar_convos[0]
                yield f"event: cache\ndata: {json.dumps({'cache_hit': True, 'similarity': cached_convo['similarity']})}\n\n"
                logger.info(f"[CACHE_HIT] Session {session_id[:8]}: Similar conversation found (similarity: {cached_convo['similarity']:.3f}), but using fresh entity parse")
            else:
                yield f"event: cache\ndata: {json.dumps({'cache_hit': False})}\n\n"

            # Check for merchant authorization error
            if "_merchant_error" in entities:
                invalid_merchant = entities["_merchant_error"]
                allowed_list = entities.get("_allowed_merchants", [])

                # Friendly error message (conversational style)
                if request.language == "id":
                    merchant_list = ", ".join(allowed_list) if allowed_list else "tidak ada"
                    error_msg = f"Maaf, {invalid_merchant} ga ada di akses kamu. Merchant yang tersedia: {merchant_list}"
                else:
                    merchant_list = ", ".join(allowed_list) if allowed_list else "none"
                    error_msg = f"Sorry, you don't have access to {invalid_merchant}. Available merchants: {merchant_list}"

                # Log error to chat history
                chat_history.add_message(session_id, "user", request.message)
                chat_history.add_message(session_id, "assistant", error_msg)

                # Send error response
                yield f"data: {json.dumps({'chunk': error_msg})}\n\n"
                yield f"event: done\ndata: {json.dumps({'error': error_msg, 'collected_data': {}, 'missing_fields': []})}\n\n"
                return

            # Update session
            if entities:
                conversation_manager.update_session(session_id, collected_data=entities)
                logger.critical(f"[SESSION_UPDATE] Session {session_id[:8]}: Updated with entities = {entities}")

            # Add user message to conversation history
            conversation_manager.add_message(session_id, "user", request.message)

            # Add user message to chat history
            chat_history.add_message(session_id, "user", request.message)

            # Get conversation history
            history = conversation_manager.get_conversation_history(session_id)

            # Get current session state
            session = conversation_manager.get_session(session_id)

            # ALWAYS add context about missing fields to help AI ask the right questions
            missing_fields = session["missing_fields"]
            collected_data = session["collected_data"]
            logger.critical(f"[BEFORE_AI] Session {session_id[:8]}: collected_data = {collected_data}, cron_schedule = '{collected_data.get('cron_schedule')}'")

            user_message_lower = request.message.lower()

            # Build context with all collected data
            collected_context = build_collected_context(collected_data, request.language)

            # Build enhanced message with missing fields context
            if missing_fields:
                # User said "proses/proceed" but data incomplete
                if any(keyword in user_message_lower for keyword in ["proses", "proceed", "lanjut", "buatkan", "create"]):
                    context_msg = f"\n\n[SYSTEM: User wants to proceed but data incomplete! Missing: {', '.join(missing_fields)}. You MUST ask for ONE missing field. DO NOT say 'will process'.]"
                # User asks what's missing
                elif any(keyword in user_message_lower for keyword in ["kurang", "missing", "apa lagi", "butuh apa", "informasi apa"]):
                    context_msg = f"\n\n[CONTEXT: Collected: {list(collected_data.keys())}. Missing: {missing_fields}. Explain simply what each missing field is with examples.]"
                # Normal flow - just inform AI about missing fields
                else:
                    context_msg = f"\n\n[SYSTEM: Missing fields: {', '.join(missing_fields)}. Continue asking for ONE field at a time.]"

                enhanced_message = request.message + collected_context + context_msg
            else:
                # All data complete
                if any(keyword in user_message_lower for keyword in ["proses", "proceed", "lanjut", "buatkan", "create"]):
                    context_msg = "\n\n[SYSTEM: All data complete! Tell user to type /confirm to execute.]"
                    enhanced_message = request.message + collected_context + context_msg
                else:
                    enhanced_message = request.message + collected_context

            # Stream AI response
            yield f"event: status\ndata: {json.dumps({'status': 'Generating response...'})}\n\n"

            ai_response = ""
            for chunk in ai_agent.chat_stream(
                enhanced_message,
                conversation_history=history[-10:],
                language=request.language
            ):
                ai_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for better UX

            # Add AI response to history
            conversation_manager.add_message(session_id, "assistant", ai_response)

            # Log AI response to chat history
            chat_history.add_message(session_id, "assistant", ai_response)

            # Check completeness
            is_complete = conversation_manager.check_completeness(session_id)
            next_action = conversation_manager.determine_next_action(session_id)

            conversation_manager.update_session(
                session_id,
                next_action=next_action,
                is_complete=is_complete
            )

            # Get current session
            session = conversation_manager.get_session(session_id)

            # Update collected data in chat history
            chat_history.update_collected_data(
                session_id,
                session["collected_data"],
                session["missing_fields"]
            )

            # Add token usage to chat history if available
            if ai_agent.provider == "claude" and ai_agent.last_token_usage:
                chat_history.add_token_usage(
                    session_id,
                    ai_agent.last_token_usage.input_tokens,
                    ai_agent.last_token_usage.output_tokens
                )

            # Store in vector DB
            logger.critical(f"[VECTOR_DB_WRITE] Session {session_id[:8]}: collected_data = {session['collected_data']}, cron = '{session['collected_data'].get('cron_schedule')}'")
            vector_search.store_conversation(
                session_id=session_id,
                user_message=request.message,
                collected_data=session["collected_data"],
                schedule_id=None,
                is_successful=False
            )

            # Send completion with token usage
            completion_data = {
                'collected_data': session['collected_data'],
                'missing_fields': session['missing_fields'],
                'next_action': next_action,
                'is_complete': is_complete,
                'token_usage': ai_agent.last_token_usage.to_dict() if ai_agent.provider == "claude" else None
            }
            yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/chat/train", response_model=ChatResponse)
async def chat_train(request: ChatRequest):
    """
    Chat with AI assistant (TRAINING MODE - uses fast 0.5b model)

    Process:
    1. Create or get session
    2. Check vector search for similar conversations
    3. If similar found (>threshold), use cached entities
    4. Otherwise, extract entities from user message
    5. Get AI response for next question (using fast model)
    6. Return response with current state

    Use this endpoint for training to collect data faster
    """
    return await _process_chat(request, model=TRAINING_MODEL)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with AI assistant (PRODUCTION MODE - uses quality 1.5b model)

    Process:
    1. Create or get session
    2. Check vector search for similar conversations
    3. If similar found (>threshold), use cached entities
    4. Otherwise, extract entities from user message
    5. Get AI response for next question
    6. Return response with current state
    """
    return await _process_chat(request, model=PRODUCTION_MODEL)


async def _process_chat(request: ChatRequest, model: str) -> ChatResponse:
    """
    Shared chat processing logic for both training and production endpoints

    Args:
        request: ChatRequest with user message
        model: Which Ollama model to use
    """
    try:
        # Create or get session
        if not request.session_id:
            session_id = conversation_manager.create_session(
                request.user_id,
                request.language
            )
        else:
            session_id = request.session_id
            session = conversation_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

        # Check vector search for similar conversations
        similar_convos = vector_search.search_similar_conversations(
            request.message,
            top_k=1
        )

        entities = {}

        if similar_convos and len(similar_convos) > 0:
            # Found similar conversation - use cached entities
            cached_convo = similar_convos[0]
            similarity = cached_convo["similarity"]
            cached_data = cached_convo["conversation"].get("collected_data", {})

            print(f"🎯 Vector cache hit! Similarity: {similarity:.3f}")
            print(f"📦 Using cached entities: {list(cached_data.keys())}")

            # Use cached entities
            entities = cached_data.copy()

        else:
            # No similar conversation - use entity parser + LLM
            print(f"🔍 No cache hit - using entity parser + LLM")
            entities = entity_parser.parse_message(request.message)

        # Update collected data
        if entities:
            conversation_manager.update_session(
                session_id,
                collected_data=entities
            )

        # Add user message to history
        conversation_manager.add_message(session_id, "user", request.message)

        # Get conversation history
        history = conversation_manager.get_conversation_history(session_id)

        # Get current session state
        session = conversation_manager.get_session(session_id)

        # ALWAYS add context about missing fields to help AI ask the right questions
        missing_fields = session["missing_fields"]
        collected_data = session["collected_data"]

        user_message_lower = request.message.lower()

        # Build enhanced message with missing fields context
        if missing_fields:
            # User said "proses/proceed" but data incomplete
            if any(keyword in user_message_lower for keyword in ["proses", "proceed", "lanjut", "buatkan", "create"]):
                context_msg = f"\n\n[SYSTEM: User wants to proceed but data incomplete! Missing: {', '.join(missing_fields)}. You MUST ask for ONE missing field. DO NOT say 'will process'.]"
            # User asks what's missing
            elif any(keyword in user_message_lower for keyword in ["kurang", "missing", "apa lagi", "butuh apa", "informasi apa"]):
                context_msg = f"\n\n[CONTEXT: Collected: {list(collected_data.keys())}. Missing: {missing_fields}. Explain simply what each missing field is with examples.]"
            # Normal flow - just inform AI about missing fields
            else:
                context_msg = f"\n\n[SYSTEM: Missing fields: {', '.join(missing_fields)}. Continue asking for ONE field at a time.]"

            enhanced_message = request.message + context_msg
        else:
            # All data complete
            if any(keyword in user_message_lower for keyword in ["proses", "proceed", "lanjut", "buatkan", "create"]):
                context_msg = "\n\n[SYSTEM: All data complete! Tell user to type /confirm to execute.]"
                enhanced_message = request.message + context_msg
            else:
                enhanced_message = request.message

        # Get AI response (with specified model)
        ai_response = ai_agent.chat(
            enhanced_message,
            conversation_history=history[-10:],  # Last 10 messages for context
            language=request.language,
            model=model  # Use training or production model
        )

        # Add AI response to history
        conversation_manager.add_message(session_id, "assistant", ai_response)

        # Check if data collection is complete
        is_complete = conversation_manager.check_completeness(session_id)

        # Determine next action
        next_action = conversation_manager.determine_next_action(session_id)

        # Update session
        conversation_manager.update_session(
            session_id,
            next_action=next_action,
            is_complete=is_complete
        )

        # Get current session state
        session = conversation_manager.get_session(session_id)

        # NOTE: Don't store during chat - only store after successful /confirm
        # Quality control prevents storing failed conversations

        return ChatResponse(
            message=ai_response,
            session_id=session_id,
            collected_data=session["collected_data"],
            missing_fields=session["missing_fields"],
            next_action=next_action,
            is_complete=is_complete
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/confirm", response_model=ConfirmResponse)
async def confirm(request: ConfirmRequest):
    """
    Confirm and create schedule

    Process:
    1. Get session data
    2. Build payload
    3. Call Go API POST /api/schedules/complete
    4. Return result
    """
    try:
        # Get session
        session = conversation_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if complete
        if not session["is_complete"]:
            return ConfirmResponse(
                success=False,
                message="Data collection not complete yet",
                payload=None
            )

        # Build payload
        collected_data = session["collected_data"]
        logger.critical(f"[CONFIRM_START] Session {request.session_id[:8]}: collected_data = {collected_data}, cron = '{collected_data.get('cron_schedule')}'")
        payload = payload_builder.build_payload(collected_data, request.user_id)
        logger.critical(f"[PAYLOAD_BUILT] Session {request.session_id[:8]}: payload cron_expression = '{payload.get('cron_expression')}'")
        logger.critical(f"[PAYLOAD_FULL] Session {request.session_id[:8]}: Full payload = {json.dumps(payload, indent=2)}")

        # Call Go API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GO_API_URL}{SCHEDULES_COMPLETE_PATH}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-User-ID": request.user_id
                }
            )

            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                data = result.get("data", {})
                schedule_id = data.get("schedule_id")

                # Store successful conversation in vector DB
                # Get first user message from session
                first_message = session.get("messages", [{}])[0].get("content", "")

                logger.critical(f"[SUCCESS_STORE] Session {request.session_id[:8]}: schedule_id = {schedule_id}, collected_data = {collected_data}, cron = '{collected_data.get('cron_schedule')}'")
                vector_search.store_conversation(
                    session_id=request.session_id,
                    user_message=first_message,
                    collected_data=collected_data,
                    schedule_id=schedule_id,
                    is_successful=True  # Only store successful conversations
                )

                # Mark chat history as complete with schedule_id
                chat_history.mark_complete(request.session_id, schedule_id, success=True)

                return ConfirmResponse(
                    success=True,
                    message="Schedule created successfully!",
                    schedule_id=schedule_id,
                    config_id=data.get("config_id"),
                    payload=payload
                )
            else:
                error_detail = response.json() if response.text else {"error": "Unknown error"}
                return ConfirmResponse(
                    success=False,
                    message=f"Failed to create schedule: {error_detail}",
                    payload=payload
                )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Go API timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)"""
    sessions = conversation_manager.get_all_sessions()
    return {
        "total": len(sessions),
        "sessions": list(sessions.keys())
    }


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details"""
    session = conversation_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session"""
    success = conversation_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


# Run server
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AI_SERVICE_PORT", "8003"))
    host = os.getenv("AI_SERVICE_HOST", "0.0.0.0")

    # Show provider and model info
    if LLM_PROVIDER == "claude":
        model_info = f"Provider: Claude | Model: {CLAUDE_MODEL}"
    else:
        model_info = f"Provider: Ollama | Model: {ai_agent.model}"

    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║  🤖 AI Report Assistant Service                         ║
    ║                                                          ║
    ║  Port: {port}                                            ║
    ║  {model_info:<56} ║
    ║  Go API: {GO_API_URL}                         ║
    ║                                                          ║
    ║  Endpoints:                                              ║
    ║    POST /chat      - Chat with AI                       ║
    ║    POST /confirm   - Confirm & create schedule          ║
    ║    GET  /health    - Health check                       ║
    ║    GET  /sessions  - List sessions                      ║
    ║                                                          ║
    ║  Ready to accept requests! 🚀                           ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
