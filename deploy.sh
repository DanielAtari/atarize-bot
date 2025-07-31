#!/bin/bash

echo "🔄 מתחבר לשרת ומבצע עדכון..."

ssh root@188.34.160.159 << 'ENDSSH'
cd /root/atarize-bot

echo "📥 מושך עדכונים מגיטהאב..."
git pull

echo "🔧 בונה את הפרונטאנד..."
npm install
npm run build

echo "🚀 מאתחל את Gunicorn..."
systemctl restart gunicorn

echo "✅ סיום! האתר עודכן בהצלחה."
ENDSSH
