#!/bin/bash

echo "🚀 DEPLOYING OPTIMIZED CHATBOT TO PRODUCTION"
echo "=============================================="

# Connect to server and deploy
ssh root@188.34.160.159 << 'ENDSSH'

echo "📍 Current directory: $(pwd)"
cd /root/atarize-bot

echo "🧹 Cleaning git state..."
git reset --hard HEAD
git clean -fd

echo "📥 Pulling latest optimized code from GitHub..."
git pull origin main

echo "🔍 Checking if Node.js/npm installed..."
if ! command -v npm &> /dev/null; then
    echo "📦 Installing Node.js and npm..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    apt-get install -y nodejs
fi

echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

echo "🔧 Building React frontend..."
npm install
npm run build

echo "🐍 Installing Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

echo "🚀 Restarting services..."
# Stop existing processes
pkill -f "python.*app.py" || true
pkill -f "gunicorn" || true

# Start Gunicorn in background
cd /root/atarize-bot
source venv/bin/activate
nohup gunicorn --bind 0.0.0.0:5050 --workers 4 --timeout 120 app:app > gunicorn.log 2>&1 &

echo "✅ DEPLOYMENT COMPLETE!"
echo "🌐 Server accessible at: http://188.34.160.159:5050"
echo "📊 Check logs: tail -f /root/atarize-bot/gunicorn.log"

ENDSSH

echo "🎉 PRODUCTION DEPLOYMENT FINISHED!"
echo "🌐 Your chatbot should be available at: http://188.34.160.159:5050"