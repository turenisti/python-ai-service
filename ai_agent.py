"""
AI Agent supporting both Ollama (local) and Claude (Anthropic)
"""
import os
import ollama
import anthropic
import logging
from typing import Dict, Optional, Iterator, Tuple
from prompts import get_system_prompt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TokenUsage:
    """Track token usage for LLM calls"""
    def __init__(self, input_tokens: int = 0, output_tokens: int = 0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens

    def to_dict(self):
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens
        }


class AIAgent:
    def __init__(self):
        # Ollama configuration
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        # Claude configuration
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Provider selection (ollama or claude)
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()

        # Initialize Claude client if provider is claude
        if self.provider == "claude" and self.anthropic_api_key:
            self.claude_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        else:
            self.claude_client = None

        # Track last token usage
        self.last_token_usage = TokenUsage()

    def chat(
        self,
        user_message: str,
        conversation_history: list = None,
        language: str = "id",
        model: str = None
    ) -> str:
        """
        Send message to LLM (Ollama or Claude) and get response

        Args:
            user_message: User's input message
            conversation_history: Previous conversation messages (for context)
            language: Language for system prompt (id/en)
            model: Override default model (for training mode)

        Returns:
            AI assistant's response
        """
        try:
            # Route to appropriate provider
            if self.provider == "claude" and self.claude_client:
                return self._chat_claude(user_message, conversation_history, language)
            else:
                return self._chat_ollama(user_message, conversation_history, language, model)

        except Exception as e:
            logger.error(f"❌ Error calling LLM: {e}")
            return self._fallback_response(language)

    def _chat_ollama(
        self,
        user_message: str,
        conversation_history: list = None,
        language: str = "id",
        model: str = None
    ) -> str:
        """Ollama chat implementation"""
        # Use provided model or default
        selected_model = model or self.model

        # Build messages
        messages = []

        # Add system prompt
        system_prompt = get_system_prompt(language)
        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # Add conversation history if exists
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Debug logging
        logger.info("="*60)
        logger.info("🔍 OLLAMA REQUEST")
        logger.info(f"Model: {selected_model}")
        logger.info(f"Messages: {len(messages)} messages")
        logger.info(f"User: {user_message[:100]}...")
        logger.info("="*60)

        # Call Ollama
        response = ollama.chat(
            model=selected_model,
            messages=messages,
            options={
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 100,
                "repeat_penalty": 1.2,
            }
        )

        # Extract response text
        assistant_message = response['message']['content'].strip()

        # Debug logging
        logger.info("="*60)
        logger.info("🤖 OLLAMA RESPONSE")
        logger.info(f"Response: {assistant_message[:200]}...")
        logger.info(f"Length: {len(assistant_message)} chars")
        logger.info("="*60)

        return assistant_message

    def _chat_claude(
        self,
        user_message: str,
        conversation_history: list = None,
        language: str = "id"
    ) -> str:
        """Claude chat implementation"""
        # Build messages for Claude (no system message in messages array)
        messages = []

        # Add conversation history if exists (skip system messages)
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") != "system":
                    messages.append(msg)

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Get system prompt
        system_prompt = get_system_prompt(language)

        # Debug logging
        logger.info("="*60)
        logger.info("🔍 CLAUDE REQUEST")
        logger.info(f"Model: {self.claude_model}")
        logger.info(f"Messages: {len(messages)} messages")
        logger.info(f"User: {user_message[:100]}...")
        logger.info("="*60)

        # Call Claude API
        response = self.claude_client.messages.create(
            model=self.claude_model,
            max_tokens=200,  # Similar to num_predict=100
            temperature=0.7,
            system=system_prompt,
            messages=messages
        )

        # Extract response text and usage stats
        assistant_message = response.content[0].text.strip()
        usage = response.usage

        # Store token usage
        self.last_token_usage = TokenUsage(usage.input_tokens, usage.output_tokens)

        # Debug logging with token usage
        logger.info("="*60)
        logger.info("🤖 CLAUDE RESPONSE")
        logger.info(f"Response: {assistant_message[:200]}...")
        logger.info(f"Length: {len(assistant_message)} chars")
        logger.info(f"💰 Tokens - Input: {usage.input_tokens} | Output: {usage.output_tokens} | Total: {usage.input_tokens + usage.output_tokens}")
        logger.info("="*60)

        return assistant_message

    def chat_stream(
        self,
        user_message: str,
        conversation_history: list = None,
        language: str = "id"
    ) -> Iterator[str]:
        """
        Stream chat response from LLM (Ollama or Claude)

        Yields:
            Chunks of assistant's response
        """
        try:
            # Route to appropriate provider
            if self.provider == "claude" and self.claude_client:
                yield from self._chat_stream_claude(user_message, conversation_history, language)
            else:
                yield from self._chat_stream_ollama(user_message, conversation_history, language)

        except Exception as e:
            logger.error(f"❌ Error in stream: {e}")
            yield self._fallback_response(language)

    def _chat_stream_ollama(
        self,
        user_message: str,
        conversation_history: list = None,
        language: str = "id"
    ) -> Iterator[str]:
        """Ollama streaming implementation"""
        # Build messages
        messages = []

        # Add system prompt
        system_prompt = get_system_prompt(language)
        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # Add conversation history if exists
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Debug logging
        logger.info("="*60)
        logger.info("🔍 OLLAMA STREAM REQUEST")
        logger.info(f"Model: {self.model}")
        logger.info(f"User: {user_message[:100]}...")

        # Call Ollama with streaming
        stream = ollama.chat(
            model=self.model,
            messages=messages,
            stream=True,
            options={
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 100,
                "repeat_penalty": 1.2,
            }
        )

        full_response = ""
        for chunk in stream:
            content = chunk['message']['content']
            full_response += content
            yield content

        logger.info(f"🤖 OLLAMA STREAM DONE: {len(full_response)} chars")
        logger.info("="*60)

    def _chat_stream_claude(
        self,
        user_message: str,
        conversation_history: list = None,
        language: str = "id"
    ) -> Iterator[str]:
        """Claude streaming implementation"""
        # Build messages for Claude (no system message in messages array)
        messages = []

        # Add conversation history if exists (skip system messages)
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") != "system":
                    messages.append(msg)

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Get system prompt
        system_prompt = get_system_prompt(language)

        # Debug logging
        logger.info("="*60)
        logger.info("🔍 CLAUDE STREAM REQUEST")
        logger.info(f"Model: {self.claude_model}")
        logger.info(f"User: {user_message[:100]}...")

        # Call Claude API with streaming
        full_response = ""
        input_tokens = 0
        output_tokens = 0

        with self.claude_client.messages.stream(
            model=self.claude_model,
            max_tokens=200,
            temperature=0.7,
            system=system_prompt,
            messages=messages
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text

            # Get final message to extract token usage
            final_message = stream.get_final_message()
            if final_message and hasattr(final_message, 'usage'):
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

        # Store token usage
        self.last_token_usage = TokenUsage(input_tokens, output_tokens)

        logger.info(f"🤖 CLAUDE STREAM DONE: {len(full_response)} chars")
        logger.info(f"💰 Tokens - Input: {input_tokens} | Output: {output_tokens} | Total: {input_tokens + output_tokens}")
        logger.info("="*60)

    def _fallback_response(self, language: str) -> str:
        """Fallback response if Ollama fails"""
        if language == "id":
            return "Maaf, terjadi kesalahan. Bisa coba lagi?"
        return "Sorry, an error occurred. Could you try again?"

    def test_connection(self) -> bool:
        """Test if LLM provider is available"""
        try:
            if self.provider == "claude" and self.claude_client:
                # Test Claude connection
                response = self.claude_client.messages.create(
                    model=self.claude_model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                print(f"✅ Claude connection OK ({self.claude_model})")
                return True
            else:
                # Test Ollama connection
                response = ollama.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": "test"}],
                    options={"num_predict": 10}
                )
                print(f"✅ Ollama connection OK ({self.model})")
                return True
        except Exception as e:
            print(f"❌ {self.provider.upper()} connection test failed: {e}")
            return False


# Quick test
if __name__ == "__main__":
    agent = AIAgent()

    # Test connection
    print("Testing Ollama connection...")
    if agent.test_connection():
        print("✅ Ollama connected!")
    else:
        print("❌ Ollama connection failed!")
        exit(1)

    # Test chat
    print("\nTesting chat...")
    response = agent.chat("buatkan report transaksi sukses untuk mid finpay770")
    print(f"AI: {response}")
