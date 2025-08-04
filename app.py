from flask import Flask, request, session, jsonify
import os

# Import our new modules
from config.settings import Config
from config.logging_config import setup_logging
from core.database import ChromaDBManager
from core.openai_client import OpenAIClientManager
from utils.text_utils import detect_language, is_greeting
from utils.validation_utils import detect_lead_info

# Setup logging
logger = setup_logging()

# Initialize services
logger.info("🚀 Initializing modular chatbot services...")
db_manager = ChromaDBManager()
openai_manager = OpenAIClientManager()

# Create Flask app
app = Flask(__name__, static_folder="static/dist", static_url_path="")
app.secret_key = Config.FLASK_SECRET_KEY
app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME

# Import modular services
from services.chat_service import ChatService
from services.email_service import EmailService

# Initialize services
chat_service = ChatService(db_manager, openai_manager.get_client())
email_service = EmailService()

logger.info("✅ Modular app initialized successfully!")

@app.route("/health")
def health():
    """Health check endpoint"""
    try:
        knowledge_count = db_manager.get_knowledge_collection().count() if db_manager.get_knowledge_collection() else 0
        intents_count = db_manager.get_intents_collection().count() if db_manager.get_intents_collection() else 0
        
        return {
            "status": "healthy",
            "services": {
                "database": "connected",
                "openai": "connected",
                "knowledge_docs": knowledge_count,
                "intents_docs": intents_count
            }
        }, 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}, 500

@app.route("/")
def index():
    """Serve React frontend"""
    return app.send_static_file("index.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Main chat endpoint - now using modular services"""
    try:
        data = request.get_json()
        # Frontend sends "question" field, not "message"
        if not data or "question" not in data:
            return jsonify({"error": "Missing 'question' in request"}), 400
        
        user_message = data["question"].strip()
        if not user_message:
            return jsonify({"error": "Empty message"}), 400
        
        logger.info(f"[MODULAR_API] Processing message: '{user_message[:50]}...'")
        
        # Call the modular chat service
        answer, updated_session = chat_service.handle_question(
            user_message, 
            dict(session)
        )
        
        # Update Flask session
        for key, value in updated_session.items():
            session[key] = value
        session.modified = True
        
        logger.info(f"[MODULAR_API] ✅ Response generated successfully")
        return jsonify({"answer": answer})
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"[MODULAR_API] ❌ Error: {e}")
        logger.error(f"[MODULAR_API] ❌ Full traceback: {error_details}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route("/api/contact", methods=["POST"])  
def api_contact():
    """Contact form endpoint"""
    try:
        data = request.get_json()
        full_name = data.get("full_name", "").strip()
        phone = data.get("phone", "").strip()
        email = data.get("email", "").strip()
        
        if not all([full_name, phone, email]):
            return jsonify({"error": "Missing required fields"}), 400
        
        subject = "📞 New Contact Form Submission"
        message = f"New contact form submission:\n\nName: {full_name}\nPhone: {phone}\nEmail: {email}"
        
        success = email_service.send_email_notification(subject, message)
        
        if success:
            return jsonify({"message": "Thank you! We'll contact you soon."})
        else:
            return jsonify({"error": "Failed to send email"}), 500
            
    except Exception as e:
        logger.error(f"[MODULAR_CONTACT] Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Clear session endpoint"""
    session.clear()
    logger.info("[MODULAR_CLEAR] Session cleared")
    return jsonify({"message": "Session cleared"})

@app.route("/clear", methods=["POST"])
def clear_chat():
    """Legacy clear endpoint"""
    session.clear()
    return jsonify({"message": "Session cleared"})

if __name__ == "__main__":
    logger.info("🎯 Starting modular Flask app on port 5050...")
    app.run(host="0.0.0.0", port=5050, debug=True)