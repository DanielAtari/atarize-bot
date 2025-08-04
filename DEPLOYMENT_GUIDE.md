# 🚀 Hetzner Server Deployment Guide
## Modular Flask + React Project (Atarize Bot Demo)

This guide provides step-by-step instructions for deploying your newly modular Flask + React project to your Hetzner server with a clean setup.

---

## 📋 **Pre-Deployment Checklist**

- [x] Modular project structure ready (core/, config/, services/, etc.)
- [x] GitHub connected to Hetzner server
- [x] All critical fixes applied to chatbot
- [ ] Environment variables documented
- [ ] Domain/subdomain configured (if needed)

---

## 🧹 **Phase 1: Clean Environment Setup**

### **Step 1: Connect to Server**
```bash
ssh your-username@your-server-ip
```

### **Step 2: Backup Current Installation (Optional)**
```bash
# Create backup of current app if it exists
sudo mv /var/www/atarize_bot_demo /var/www/atarize_bot_demo_backup_$(date +%Y%m%d)
```

### **Step 3: Remove Old Application Files**
```bash
# Stop any running services
sudo systemctl stop atarize-bot || true
sudo systemctl stop nginx || true

# Remove old application directory
sudo rm -rf /var/www/atarize_bot_demo

# Remove old virtual environment
sudo rm -rf /var/www/venv_atarize

# Remove old systemd service file
sudo rm -f /etc/systemd/system/atarize-bot.service
sudo systemctl daemon-reload
```

### **Step 4: Update System**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nodejs npm nginx git
```

---

## 📥 **Phase 2: Clone and Setup New Project**

### **Step 5: Clone Repository**
```bash
# Navigate to web directory
cd /var/www

# Clone your repository (replace with your actual repo URL)
sudo git clone https://github.com/your-username/atarize_bot_demo.git
sudo chown -R $USER:$USER /var/www/atarize_bot_demo
cd /var/www/atarize_bot_demo
```

### **Step 6: Verify Project Structure**
```bash
# Verify modular structure exists
ls -la
# Should see: core/, config/, services/, utils/, static/, etc.
```

---

## 🐍 **Phase 3: Python Backend Setup**

### **Step 7: Create Virtual Environment**
```bash
cd /var/www/atarize_bot_demo
python3 -m venv venv
source venv/bin/activate
```

### **Step 8: Install Python Dependencies**
```bash
# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Verify key packages are installed
pip list | grep -E "(flask|openai|chromadb|gunicorn)"
```

### **Step 9: Setup Environment Variables**
```bash
# Create environment file
sudo nano /var/www/atarize_bot_demo/.env

# Add your environment variables:
# OPENAI_API_KEY=your_openai_key_here
# FLASK_SECRET_KEY=your_secret_key_here
# EMAIL_USER=your_email@gmail.com
# EMAIL_PASS=your_app_password
# EMAIL_TARGET=notifications@atarize.com
```

### **Step 10: Test Flask Application**
```bash
# Test the modular app works
cd /var/www/atarize_bot_demo
source venv/bin/activate
python app.py
# Should start without errors on port 5000
# Press Ctrl+C to stop
```

---

## ⚛️ **Phase 4: React Frontend Build**

### **Step 11: Install Node Dependencies**
```bash
cd /var/www/atarize_bot_demo
npm install
```

### **Step 12: Build React Frontend**
```bash
# Build for production
npm run build

# Verify build directory exists
ls -la static/dist/
# Should contain index.html, assets/, etc.
```

---

## 🔧 **Phase 5: Gunicorn + Systemd Setup**

### **Step 13: Create Gunicorn Configuration**
```bash
sudo nano /var/www/atarize_bot_demo/gunicorn_config.py
```

**Content:**
```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
user = "www-data"
group = "www-data"
chdir = "/var/www/atarize_bot_demo"
pythonpath = "/var/www/atarize_bot_demo"
```

### **Step 14: Create Systemd Service**
```bash
sudo nano /etc/systemd/system/atarize-bot.service
```

**Content:**
```ini
[Unit]
Description=Atarize Bot Demo (Modular Flask App)
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/atarize_bot_demo
Environment=PATH=/var/www/atarize_bot_demo/venv/bin
EnvironmentFile=/var/www/atarize_bot_demo/.env
ExecStart=/var/www/atarize_bot_demo/venv/bin/gunicorn -c gunicorn_config.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **Step 15: Set Permissions and Start Service**
```bash
# Set proper ownership
sudo chown -R www-data:www-data /var/www/atarize_bot_demo

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable atarize-bot
sudo systemctl start atarize-bot

# Check status
sudo systemctl status atarize-bot
```

---

## 🌐 **Phase 6: NGINX Configuration**

### **Step 16: Create NGINX Site Configuration**
```bash
sudo nano /etc/nginx/sites-available/atarize_bot_demo
```

**Content:**
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;  # Replace with your domain
    
    # Serve static files directly
    location /static/ {
        alias /var/www/atarize_bot_demo/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # API routes to Flask
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    # Serve React app for all other routes
    location / {
        root /var/www/atarize_bot_demo/static/dist;
        try_files $uri $uri/ /index.html;
        
        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
    }
    
    # Handle favicon and robots.txt
    location /favicon.ico {
        root /var/www/atarize_bot_demo/static/dist;
        log_not_found off;
        access_log off;
    }
    
    location /robots.txt {
        root /var/www/atarize_bot_demo/static/dist;
        log_not_found off;
        access_log off;
    }
}
```

### **Step 17: Enable Site and Restart NGINX**
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/atarize_bot_demo /etc/nginx/sites-enabled/

# Remove default site if it exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test NGINX configuration
sudo nginx -t

# Restart NGINX
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 🔍 **Phase 7: Testing and Verification**

### **Step 18: Test All Components**
```bash
# Check services are running
sudo systemctl status atarize-bot
sudo systemctl status nginx

# Check if Flask is responding
curl http://127.0.0.1:8000/api/chat -X POST -H "Content-Type: application/json" -d '{"question":"test"}'

# Check if frontend is accessible
curl http://your-domain.com
```

### **Step 19: Test Chatbot Functionality**
- Visit your domain in browser
- Test chat functionality
- Verify contact form works
- Check that emails are sent correctly

---

## 🔒 **Phase 8: SSL Certificate (Optional but Recommended)**

### **Step 20: Install Certbot and Get SSL**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## 📝 **Deployment Commands Quick Reference**

### **Update Deployment:**
```bash
cd /var/www/atarize_bot_demo
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
npm install
npm run build
sudo systemctl restart atarize-bot
sudo systemctl reload nginx
```

### **View Logs:**
```bash
# Flask app logs
sudo journalctl -u atarize-bot -f

# NGINX logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### **Check Status:**
```bash
sudo systemctl status atarize-bot nginx
sudo netstat -tlnp | grep -E ":80|:8000"
```

---

## ⚠️ **Troubleshooting Common Issues**

### **Flask App Won't Start:**
- Check environment variables in `.env`
- Verify all Python dependencies installed
- Check service logs: `sudo journalctl -u atarize-bot`

### **Frontend Not Loading:**
- Ensure `npm run build` completed successfully
- Check NGINX configuration syntax: `sudo nginx -t`
- Verify static files exist in `static/dist/`

### **API Calls Failing:**
- Check Flask is running on port 8000
- Verify NGINX proxy configuration
- Test direct API call: `curl http://127.0.0.1:8000/api/chat`

### **Email Not Working:**
- Verify email environment variables
- Check Gmail app password settings
- Test with a simple email function

---

## 📞 **Need Help?**

If you encounter any issues during deployment, we can:
1. Debug specific error messages together
2. Check logs and configurations
3. Test individual components step by step
4. Optimize performance if needed

**Ready to deploy when you are!** 🚀