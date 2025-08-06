from flask import Flask, request, session, jsonify
from flask_cors import CORS
import os
import threading

# Import our new modules
from config.settings import Config
from config.logging_config import setup_logging
from core.database import DatabaseManager
from core.optimized_openai_client import OpenAIClient
from utils.text_utils import detect_language, is_greeting
from utils.validation_utils import detect_lead_info

# Setup logging
logger = setup_logging()

# Initialize services
logger.info("🚀 Initializing modular chatbot services...")
db_manager = DatabaseManager()
openai_manager = OpenAIClient()

# Create Flask app
app = Flask(__name__, static_folder="static/dist", static_url_path="")
app.secret_key = Config.FLASK_SECRET_KEY
app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME

# CORS configuration for development (enabled by default for local development)
# Only disable in production by setting PRODUCTION=true environment variable
if os.environ.get("PRODUCTION") != "true":
    logger.info("🔧 Enabling CORS for development mode")
    CORS(app, origins=[
        "http://localhost:5050",
        "http://127.0.0.1:5050", 
        "http://192.168.1.134:5050",
        "http://192.168.1.245:5050",
        "http://192.168.1.245"
    ], supports_credentials=True)
else:
    logger.info("🔒 CORS disabled for production mode")

# Import modular services
from services.chat_service import ChatService
from services.email_service import EmailService
from services.streaming_chat_service import StreamingChatService, StreamingResponseHandler

# Initialize services
chat_service = ChatService(db_manager, openai_manager.get_client())
streaming_chat_service = StreamingChatService(db_manager, openai_manager.get_client())
email_service = EmailService()

# Simple cache pre-warming for common questions
def pre_warm_common_questions():
    """Pre-warm cache with common questions for faster responses"""
    import threading
    import time
    
    def pre_warm_worker():
        time.sleep(3)  # Wait for server to start
        common_questions = [
            "כמה עולה השירות?",
            "מה המחיר?", 
            "איך זה עובד?",
            "מה התכונות?"
        ]
        
        clean_session = {
            "history": [],
            "greeted": False,
            "intro_given": False,
            "lead_collected": False,
            "interested_lead_pending": False,
            "product_market_fit_detected": False
        }
        
        logger.info("🔥 Starting simple cache pre-warming...")
        for question in common_questions:
            try:
                chat_service.handle_question(question, clean_session.copy())
                logger.debug(f"Pre-warmed: {question}")
            except Exception as e:
                logger.debug(f"Pre-warming failed for {question}: {e}")
        
        cache_stats = chat_service.cache_manager.get_advanced_stats()
        logger.info(f"✅ Pre-warming completed. Cache now has {cache_stats['total_entries']} entries")
    
    thread = threading.Thread(target=pre_warm_worker, daemon=True)
    thread.start()
    logger.info("🚀 Simple pre-warming started in background")

# Start pre-warming
pre_warm_common_questions()

logger.info("✅ Modular app initialized successfully!")

@app.route("/health")
def health():
    """Health check endpoint"""
    try:
        knowledge_count = db_manager.get_knowledge_collection().count() if db_manager.get_knowledge_collection() else 0
        intents_count = db_manager.get_intents_collection().count() if db_manager.get_intents_collection() else 0
        
        # Get cache stats for performance monitoring
        cache_stats = chat_service.cache_manager.get_advanced_stats()
        
        return {
            "status": "healthy",
            "services": {
                "database": "connected",
                "openai": "connected",
                "knowledge_docs": knowledge_count,
                "intents_docs": intents_count,
                "pre_warming": "active"
            },
            "performance": {
                "cache_enabled": True,
                "cache_entries": cache_stats["total_entries"],
                "cache_hit_rate": f"{cache_stats['hit_rate_percent']}%",
                "optimization_status": "Performance optimized with intelligent caching + pre-warming"
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
    """Main chat endpoint with async processing for faster first-time responses"""
    import time
    start_time = time.time()
    
    try:
        data = request.get_json()
        # Frontend sends "question" field, not "message"
        if not data or "question" not in data:
            return jsonify({"error": "Missing 'question' in request"}), 400
        
        user_message = data["question"].strip()
        if not user_message:
            return jsonify({"error": "Empty message"}), 400
        
        # Use optimized chat service with pre-warmed cache
        logger.info(f"[MODULAR_API] ⚡ Processing message: '{user_message[:50]}...' (optimized)")
        
        # Use the enhanced chat service with caching and response variation
        answer, updated_session = chat_service.handle_question(user_message, dict(session))
        
        # Update Flask session
        for key, value in updated_session.items():
            session[key] = value
        session.modified = True
        
        # Performance logging
        response_time = time.time() - start_time
        performance_level = "⚡ Excellent" if response_time < 2.0 else "🔄 Good" if response_time < 5.0 else "⚠️ Slow"
        
        logger.info(f"[MODULAR_API] {performance_level} response time: {response_time:.3f}s (optimized)")
        
        return jsonify({
            "answer": answer,
            "response_time": response_time,
            "processing_type": "optimized",
            "performance": performance_level
        })
        
    except Exception as e:
        import traceback
        response_time = time.time() - start_time
        error_details = traceback.format_exc()
        logger.error(f"[MODULAR_API] ❌ Error: {e}")
        logger.error(f"[MODULAR_API] ❌ Full traceback: {error_details}")
        return jsonify({
            "error": "Internal server error", 
            "details": str(e),
            "response_time": response_time
        }), 500

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
            return jsonify({"success": True, "message": "Thank you! We'll contact you soon."})
        else:
            return jsonify({"success": False, "error": "Failed to send email"}), 500
            
    except Exception as e:
        logger.error(f"[MODULAR_CONTACT] Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """Streaming chat endpoint for better perceived performance"""
    try:
        data = request.get_json()
        if not data or "question" not in data:
            return jsonify({"error": "Missing question in request"}), 400
        
        question = data["question"].strip()
        if not question:
            return jsonify({"error": "Empty question"}), 400
        
        logger.info(f"[STREAMING] Processing question: {question}")
        
        # Create streaming response
        generator = streaming_chat_service.stream_response(question, session)
        return StreamingResponseHandler.create_streaming_response(generator)
        
    except Exception as e:
        logger.error(f"[STREAMING] Error: {e}")
        return jsonify({"error": "Streaming failed"}), 500

@app.route("/api/chat/quick", methods=["POST"])
def api_chat_quick():
    """Quick chat endpoint that checks cache first"""
    try:
        data = request.get_json()
        if not data or "question" not in data:
            return jsonify({"error": "Missing question in request"}), 400
        
        question = data["question"].strip()
        if not question:
            return jsonify({"error": "Empty question"}), 400
        
        # Check cache first for instant response
        import hashlib
        cache_key = hashlib.md5(question.lower().encode()).hexdigest()
        cached_response = streaming_chat_service.cache_manager.get(cache_key)
        
        if cached_response:
            logger.info(f"[QUICK] Cache hit for: {question}")
            return jsonify({
                "answer": cached_response["answer"],
                "cached": True,
                "response_time": 0.1
            })
        
        # Not cached - indicate streaming needed
        return jsonify({
            "cached": False,
            "message": "Use streaming endpoint for full response",
            "stream_endpoint": "/api/chat/stream"
        })
        
    except Exception as e:
        logger.error(f"[QUICK] Error: {e}")
        return jsonify({"error": "Quick check failed"}), 500

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

@app.route("/api/cache/stats", methods=["GET"])
def api_cache_stats():
    """Get detailed cache statistics"""
    try:
        stats = chat_service.get_cache_stats()
        performance = chat_service.get_performance_summary()
        return jsonify({
            "cache_stats": stats,
            "performance": {
                "efficiency": f"{stats['hit_rate_percent']}% hit rate",
                "memory_usage": f"{stats['total_entries']}/{stats['max_size']} entries",
                "cost_savings": "Reduced OpenAI API calls" if stats['cache_hits'] > 0 else "No savings yet",
                "optimization": performance["optimization_status"]
            }
        })
    except Exception as e:
        logger.error(f"[CACHE_STATS] Error: {e}")
        return jsonify({"error": "Failed to get cache stats"}), 500

@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    """Clear cache entries"""
    try:
        data = request.get_json() or {}
        pattern = data.get("pattern")  # Optional pattern to clear specific entries
        
        chat_service.clear_cache(pattern)
        
        message = f"Cache cleared (pattern: {pattern})" if pattern else "All cache entries cleared"
        logger.info(f"[CACHE_CLEAR] {message}")
        
        return jsonify({"message": message})
    except Exception as e:
        logger.error(f"[CACHE_CLEAR] Error: {e}")
        return jsonify({"error": "Failed to clear cache"}), 500

@app.route("/api/performance", methods=["GET"])
def api_performance():
    """Get performance summary"""
    try:
        performance = chat_service.get_performance_summary()
        return jsonify(performance)
    except Exception as e:
        logger.error(f"[PERFORMANCE] Error: {e}")
        return jsonify({"error": "Failed to get performance data"}), 500

@app.route("/api/variation/stats", methods=["GET"])
def api_variation_stats():
    """Get response variation statistics"""
    try:
        stats = chat_service.get_variation_stats()
        return jsonify({
            "variation_stats": stats,
            "status": "Response variation active",
            "benefit": "Eliminates repetitive phrases for natural conversation"
        })
    except Exception as e:
        logger.error(f"[VARIATION_STATS] Error: {e}")
        return jsonify({"error": "Failed to get variation stats"}), 500

@app.route("/api/variation/clear", methods=["POST"])
def api_variation_clear():
    """Clear conversation state for response variation"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        chat_service.clear_conversation_state(session_id)
        
        message = f"Cleared conversation state for session: {session_id}" if session_id else "Cleared all conversation states"
        logger.info(f"[VARIATION_CLEAR] {message}")
        
        return jsonify({"message": message})
    except Exception as e:
        logger.error(f"[VARIATION_CLEAR] Error: {e}")
        return jsonify({"error": "Failed to clear conversation state"}), 500

@app.route("/api/performance/stats", methods=["GET"])
def api_performance_stats():
    """Get performance statistics"""
    try:
        cache_stats = chat_service.get_cache_stats()
        variation_stats = chat_service.get_variation_stats()
        
        return jsonify({
            "cache_stats": cache_stats,
            "variation_stats": variation_stats,
            "status": "Performance optimized with caching + response variation + pre-warming",
            "benefit": "Faster responses through intelligent caching and varied responses"
        })
    except Exception as e:
        logger.error(f"[PERFORMANCE_STATS] Error: {e}")
        return jsonify({"error": "Failed to get performance stats"}), 500

@app.route("/api/performance/pre-warm", methods=["POST"])
def api_performance_pre_warm():
    """Manually trigger cache pre-warming"""
    try:
        def pre_warm_worker():
            pre_warm_common_questions()
        
        thread = threading.Thread(target=pre_warm_worker, daemon=True)
        thread.start()
        
        logger.info("[PERFORMANCE_PRE_WARM] Pre-warming started manually")
        return jsonify({"message": "Cache pre-warming started in background"})
    except Exception as e:
        logger.error(f"[PERFORMANCE_PRE_WARM] Error: {e}")
        return jsonify({"error": "Failed to start pre-warming"}), 500

@app.route("/api/openai/stats", methods=["GET"])
def api_openai_stats():
    """Get OpenAI performance statistics"""
    try:
        stats = openai_manager.get_performance_stats()
        return jsonify({
            "openai_performance": stats,
            "optimization": "Using smart model selection and optimized prompts",
            "models": {
                "fast": "gpt-3.5-turbo (simple queries)",
                "smart": "gpt-4-turbo (complex queries)"
            }
        })
    except Exception as e:
        logger.error(f"[OPENAI_STATS] Error: {e}")
        return jsonify({"error": "Failed to get OpenAI stats"}), 500

@app.route("/api/context/stats", methods=["GET"])
def api_context_stats():
    """Get context management statistics"""
    try:
        from services.context_manager import context_manager
        context_summary = context_manager.get_context_summary(session)
        return jsonify({
            "context_management": {
                "active_sessions": len(context_manager.user_profiles),
                "current_session": context_summary,
                "features": [
                    "Business type detection",
                    "Context correction tracking", 
                    "Response validation",
                    "Context-aware prompting"
                ]
            }
        })
    except Exception as e:
        logger.error(f"[CONTEXT_STATS] Error: {e}")
        return jsonify({"error": "Failed to get context stats"}), 500

if __name__ == "__main__":
    logger.info("🎯 Starting modular Flask app with performance optimizations on port 5050...")
    app.run(host="0.0.0.0", port=5050, debug=True)