#!/bin/bash
# Start Python AI Service

echo "🚀 Starting AI Report Assistant Service..."
echo ""

# Check if ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️  Ollama is not running!"
    echo "   Start it with: ollama serve"
    exit 1
fi

# Check if qwen2.5 model exists
if ! ollama list | grep -q "qwen2.5:3b-instruct"; then
    echo "⚠️  Qwen2.5 3B model not found!"
    echo "   Download it with: ollama pull qwen2.5:3b-instruct"
    exit 1
fi

echo "✅ Ollama is running"
echo "✅ Qwen2.5 3B model found"
echo ""

# Start service
python3 main.py
