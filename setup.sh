#!/bin/bash

# Setup script for YouTube Video Summarizer

echo "YouTube Video Summarizer - Setup"
echo "=================================="
echo ""

# Check Python version
python3 --version

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and add your API keys!"
    echo ""
else
    echo ".env file already exists"
fi

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Edit .env file and add your API keys"
echo "3. Run: python main.py process <youtube_url>"
echo ""
