#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🏥 MEDICAL RAG SYSTEM - SETUP SCRIPT 🏥                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "📁 Project Directory: $PROJECT_DIR"
echo ""

echo "🔍 Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found! Please install Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Found Python $PYTHON_VERSION"
echo ""

echo "🔧 Creating virtual environment..."
python3 -m venv backend/venv
echo "✅ Virtual environment created"
echo ""

echo "🚀 Activating virtual environment..."
source backend/venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

echo "📦 Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r backend/requirements.txt
echo "✅ Dependencies installed"
echo ""

echo "🔑 Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env file created (copy of .env.example)"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your OpenAI API key:"
    echo "   OPENAI_API_KEY=sk-your-api-key-here"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ SETUP COMPLETE! ✅                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📖 Next steps:"
echo "1. Edit .env and add your OpenAI API key: nano .env"
echo "2. Start backend: source backend/venv/bin/activate && python3 backend/main.py"
echo "3. Open frontend/index.html in your browser"
echo ""
echo "📚 Read: 00_READ_ME_FIRST.txt / START_HERE.md / docs/QUICKSTART.md"
echo ""
echo "🎉 Good luck!"
