#!/bin/bash

# Deep Research Agent Setup Script
echo "🔍 Deep Research Agent - Setup Script"
echo "======================================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found. Please install Python 3.8+."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not found. Please install pip."
    exit 1
fi

echo "✅ pip3 found"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Skipping creation."
else
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Verify activation
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

echo "✅ pip3 found"

# Check if Node.js/npm is available (for MCP server)
if ! command -v npx &> /dev/null; then
    echo "⚠️ Node.js/npx not found. Installing Node.js is recommended for web research."
    echo "   You can install it from: https://nodejs.org/"
else
    echo "✅ Node.js/npx found: $(node --version)"
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Check installation
echo ""
echo "🔍 Verifying installation..."

# Test imports
python3 -c "
import sys
try:
    import chainlit
    print('✅ Chainlit installed')
except ImportError:
    print('❌ Chainlit not installed')
    sys.exit(1)

try:
    import langchain_google_genai
    print('✅ LangChain Google GenAI installed')
except ImportError:
    print('❌ LangChain Google GenAI not installed')
    sys.exit(1)

try:
    import langgraph
    print('✅ LangGraph installed')
except ImportError:
    print('❌ LangGraph not installed')
    sys.exit(1)

try:
    import mcp
    print('✅ MCP installed')
except ImportError:
    print('❌ MCP not installed')
    sys.exit(1)

try:
    from dotenv import load_dotenv
    print('✅ Python-dotenv installed')
except ImportError:
    print('❌ Python-dotenv not installed')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All dependencies installed successfully!"
else
    echo ""
    echo "❌ Some dependencies failed to install. Please check the error messages above."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your API keys."
else
    echo ""
    echo "ℹ️ .env file already exists."
fi

# Final instructions
echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit the .env file and add your API keys:"
echo "   - GOOGLE_API_KEY (required)"
echo "   - BRIGHTDATA_API_TOKEN (optional, for web research)"
echo ""
echo "2. Test your setup:"
echo "   python3 test_environment.py"
echo ""
echo "3. Start the application:"
echo "   chainlit run app.py"
echo ""
echo "For help with API keys:"
echo "- Google API: https://makersuite.google.com/app/apikey"
echo "- BrightData: https://brightdata.com/"
