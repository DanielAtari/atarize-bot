import logging
import os
import json
from config.settings import Config
from utils.text_utils import detect_language, is_greeting, get_natural_greeting, is_small_talk
from utils.validation_utils import detect_lead_info, is_vague_gpt_answer
from utils.token_utils import count_tokens, log_token_usage

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db_manager, openai_client):
        self.db_manager = db_manager
        self.openai_client = openai_client
        
        # Load system prompt and intents at initialization
        self._load_system_prompt()
        self._load_intents()
    
    def _load_system_prompt(self):
        """Load system prompt from file"""
        try:
            system_prompt_path = os.path.join(Config.DATA_DIR, "system_prompt_atarize.txt")
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read().strip()
                logger.info("[CHAT_SERVICE] System prompt loaded successfully")
        except Exception as e:
            logger.error(f"[CHAT_SERVICE] Failed to load system prompt: {e}")
            self.system_prompt = "You are a helpful assistant for Atarize."
    
    def _load_intents(self):
        """Load intents configuration from file"""
        try:
            intents_path = os.path.join(Config.DATA_DIR, "intents_config.json")
            with open(intents_path, "r", encoding="utf-8") as f:
                self.intents = json.load(f)
                logger.info(f"[CHAT_SERVICE] Loaded {len(self.intents)} intents")
        except Exception as e:
            logger.error(f"[CHAT_SERVICE] Failed to load intents: {e}")
            self.intents = []
    
    def handle_question(self, question, session):
        """
        Main chat handling logic - modular version of the original handle_question
        """
        # Performance timing
        import time
        overall_start_time = time.time()
        
        # Initialize variables to prevent UnboundLocalError
        answer = None
        intent_name = "unknown"
        
        logger.debug(f"\n{'='*60}")
        logger.info(f"[CHAT_SERVICE] Starting processing for: '{question}'")
        
        # Initialize session keys if they don't exist
        if "history" not in session:
            session["history"] = []
            logger.debug(f"[SESSION_INIT] Initialized empty history")
        if "greeted" not in session:
            session["greeted"] = False
        if "intro_given" not in session:
            session["intro_given"] = False
        
        # Validate session state consistency
        self._validate_session_state(session)
        
        # Check if lead collection is already completed
        if session.get("lead_collected"):
            logger.info(f"[LEAD_COMPLETED] Lead already collected - providing final closure message")
            lang = detect_language(question)
            if lang == "he":
                final_message = "תודה על ההודעה! כבר קיבלנו את הפרטים שלך וצוות Atarize יחזור אליך בקרוב. אין צורך בפעולות נוספות מצידך 😊"
            else:
                final_message = "Thank you for your message! We already have your details and the Atarize team will contact you soon. No further action is needed from you 😊"
            return final_message, session
        
        # Add user message to history
        session["history"].append({"role": "user", "content": question})
        
        # Debug: Always test lead detection on every input
        from utils.validation_utils import detect_lead_info
        lead_test = detect_lead_info(question)
        logger.debug(f"[DEBUG] Lead detection test on '{question}': {lead_test}")
        
        # Handle greeting logic
        if is_greeting(question) and not session.get("greeted"):
            session["greeted"] = True
            session["intro_given"] = True
            lang = detect_language(question)
            greeting_response = get_natural_greeting(lang, question)
            session["history"].append({"role": "assistant", "content": greeting_response})
            return greeting_response, session
        
        # Handle lead collection flow
        if session.get("interested_lead_pending"):
            logger.info(f"[CHAT_SERVICE] 🔄 Lead collection mode active - processing user input")
            return self._handle_lead_collection(question, session)
        
        # Check for lead information FIRST (before AI generation)
        if detect_lead_info(question):
            logger.info(f"[LEAD_FLOW] ✅ COMPLETE LEAD INFO DETECTED!")
            logger.info(f"[LEAD_FLOW] User message: '{question}'")
            
            from services.email_service import EmailService
            from utils.lead_parser import format_lead_notification, extract_lead_details
            
            # Extract and log lead details
            lead_details = extract_lead_details(question)
            logger.info(f"[LEAD_FLOW] 📋 Extracted details:")
            logger.info(f"[LEAD_FLOW]   👤 Name: {lead_details.get('name', 'Not found')}")
            logger.info(f"[LEAD_FLOW]   📞 Phone: {lead_details.get('phone', 'Not found')}")
            logger.info(f"[LEAD_FLOW]   📧 Email: {lead_details.get('email', 'Not found')}")
            
            # Prepare and send email
            email_service = EmailService()
            formatted_message = format_lead_notification(question)
            
            logger.info(f"[LEAD_FLOW] 📤 Attempting to send email notification...")
            email_success = email_service.send_email_notification(
                subject="🆕 New Lead from Atarize Chatbot",
                message=formatted_message
            )
            
            if email_success:
                logger.info(f"[LEAD_FLOW] ✅ EMAIL NOTIFICATION SENT SUCCESSFULLY!")
            else:
                logger.error(f"[LEAD_FLOW] ❌ EMAIL NOTIFICATION FAILED!")
                logger.error(f"[LEAD_FLOW] Lead details will be lost! Consider manual follow-up.")
                
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
            session["lead_collected"] = True
            
            # Determine language for response
            lang = detect_language(question)
            if lang == "he":
                closure_message = "תודה רבה! קיבלנו את הפרטים שלך ומישהו מהצוות יחזור אליך בהקדם. שיהיה לך יום נהדר! 😊"
            else:
                closure_message = "Thank you! We received your details and someone from our team will get back to you soon. Have a great day! 😊"
            
            session["history"].append({"role": "assistant", "content": closure_message})
            return closure_message, session
        
        # Check for vague input
        if len(question.strip()) < 3:
            logger.info(f"[CHAT_SERVICE] Very short input - generating intelligent response")
            session["interested_lead_pending"] = True
            intelligent_response = self._generate_intelligent_response("vague_input", question, session)
            session["history"].append({"role": "assistant", "content": intelligent_response})
            return intelligent_response, session
        
        # Generate AI response using OpenAI
        try:
            answer = self._generate_ai_response(question, session)
            
            if not answer or is_vague_gpt_answer(answer):
                logger.info(f"[CHAT_SERVICE] Vague response generated - generating intelligent follow-up")
                session["interested_lead_pending"] = True
                intelligent_response = self._generate_intelligent_response("vague_gpt_response", question, session)
                session["history"].append({"role": "assistant", "content": intelligent_response})
                return intelligent_response, session
            
            # Success - add to history and return
            session["history"].append({"role": "assistant", "content": answer})
            
            # Performance summary
            total_time = time.time() - overall_start_time
            logger.info(f"[PERFORMANCE] 🏁 TOTAL REQUEST TIME: {total_time:.3f}s")
            if total_time > 3.0:
                logger.warning(f"[PERFORMANCE] ⚠️  SLOW REQUEST: {total_time:.3f}s > 3.0s threshold")
            
            return answer, session
            
        except Exception as e:
            logger.error(f"[CHAT_SERVICE] Error generating response: {e}")
            session["interested_lead_pending"] = True
            intelligent_response = self._generate_intelligent_response("technical_error", question, session)
            session["history"].append({"role": "assistant", "content": intelligent_response})
            return intelligent_response, session
    
    def _handle_lead_collection(self, question, session):
        """Handle lead collection flow"""
        logger.info(f"[LEAD_FLOW] 🚀 LEAD COLLECTION MODE ACTIVE")
        logger.info(f"[LEAD_FLOW] Processing user input: '{question}'")
        
        # Check for exit phrases
        exit_phrases = ["היי", "עזוב", "לא עכשיו", "שכח מזה", "לא רוצה", "תודה לא", "די", "סגור"]
        question_lower = question.lower().strip()
        
        for phrase in exit_phrases:
            if phrase in question_lower:
                logger.info(f"[LEAD_FLOW] ✅ Exit phrase detected: '{phrase}' - resetting lead mode")
                session.pop("interested_lead_pending", None)
                session.pop("lead_request_count", None)
                lang = detect_language(question)
                if lang == "he":
                    return "בסדר גמור! אם תרצה עזרה בעתיד, אני כאן. איך אפשר לעזור? 😊", session
                else:
                    return "No worries, let's continue. Feel free to ask me anything! 😊", session
        
        # REMOVED: Duplicate lead detection logic
        # Lead detection is now handled ONLY in main flow (lines 98-141)
        # This prevents duplicate processing and double email notifications
        
        # If user is in lead collection mode but hasn't provided complete info yet:
        # Increment request count
        lead_request_count = session.get("lead_request_count", 0) + 1
        session["lead_request_count"] = lead_request_count
        logger.debug(f"[LEAD_FLOW] ❌ No lead info detected - request count now: {lead_request_count}")
        
        # After 2 requests, reset and continue normal flow
        if lead_request_count >= 2:
            logger.info(f"[LEAD_FLOW] 🔄 Max requests reached - resetting lead mode and continuing")
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
            # Continue to normal processing
            return self._generate_ai_response(question, session), session
        else:
            # Ask for details again with intelligent response
            intelligent_response = self._generate_intelligent_response("lead_request", question, session)
            return intelligent_response, session
    
    def _validate_session_state(self, session):
        """Validate session state consistency and fix conflicts"""
        # Rule 1: lead_collected and interested_lead_pending are mutually exclusive
        if session.get("lead_collected") and session.get("interested_lead_pending"):
            logger.warning("[SESSION_FIX] ⚠️ Conflict: lead_collected=True and interested_lead_pending=True")
            logger.warning("[SESSION_FIX] 🔧 Fixing: Removing interested_lead_pending (lead already collected)")
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
        
        # Rule 2: If lead_collected is True, request_count should be cleared
        if session.get("lead_collected") and session.get("lead_request_count"):
            logger.warning("[SESSION_FIX] ⚠️ Conflict: lead_collected=True but lead_request_count exists")
            logger.warning("[SESSION_FIX] 🔧 Fixing: Clearing lead_request_count")
            session.pop("lead_request_count", None)
        
        # Rule 3: request_count should not exist without interested_lead_pending
        if session.get("lead_request_count") and not session.get("interested_lead_pending"):
            logger.warning("[SESSION_FIX] ⚠️ Conflict: lead_request_count exists without interested_lead_pending")
            logger.warning("[SESSION_FIX] 🔧 Fixing: Clearing lead_request_count")
            session.pop("lead_request_count", None)
        
        # Rule 4: History should always be a list
        if "history" in session and not isinstance(session["history"], list):
            logger.warning("[SESSION_FIX] ⚠️ Invalid: history is not a list")
            logger.warning("[SESSION_FIX] 🔧 Fixing: Resetting history to empty list")
            session["history"] = []
        
        # Log current session state for debugging
        logger.debug(f"[SESSION_STATE] greeted={session.get('greeted', False)}, "
                    f"intro_given={session.get('intro_given', False)}, "
                    f"lead_pending={session.get('interested_lead_pending', False)}, "
                    f"lead_collected={session.get('lead_collected', False)}, "
                    f"request_count={session.get('lead_request_count', 0)}, "
                    f"history_length={len(session.get('history', []))}")

    def _generate_intelligent_response(self, context_type, user_input, session, reason=""):
        """Generate contextually appropriate, language-aware responses using GPT"""
        from utils.text_utils import detect_language
        
        lang = detect_language(user_input)
        
        # Build context-specific prompt
        if context_type == "vague_input":
            if lang == "he":
                context_prompt = f"המשתמש שלח הודעה קצרה או לא ברורה: '{user_input}'. תענה בחום ותבקש ממנו לפרט מה הוא מחפש או תציע לו להשאיר פרטים לחזרה."
            else:
                context_prompt = f"User sent a vague or short message: '{user_input}'. Respond warmly and ask them to clarify what they're looking for or offer to have someone contact them."
        
        elif context_type == "vague_gpt_response":
            if lang == "he":
                context_prompt = f"לא הצלחתי למצוא תשובה טובה לשאלה: '{user_input}'. תסביר בנימוס שאני רוצה לעזור אך צריך יותר פרטים או תציע לחבר אותו למישהו מהצוות."
            else:
                context_prompt = f"I couldn't find a good answer for: '{user_input}'. Politely explain that I want to help but need more details or offer to connect them with the team."
        
        elif context_type == "technical_error":
            if lang == "he":
                context_prompt = f"התרחשה שגיאה טכנית בעת עיבוד השאלה: '{user_input}'. תתנצל בנימוס ותציע פתרונות חלופיים או דרכי התחברות."
            else:
                context_prompt = f"A technical error occurred processing: '{user_input}'. Apologize politely and offer alternative solutions or ways to connect."
        
        elif context_type == "lead_request":
            if lang == "he":
                context_prompt = f"המשתמש בתהליך איסוף פרטים. תבקש ממנו בנימוס להשאיר שם, טלפון ואימייל כדי שנוכל לחזור אליו."
            else:
                context_prompt = f"User is in lead collection process. Politely ask them to share their name, phone, and email so we can follow up."
        
        try:
            # Create messages for GPT
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context_prompt}
            ]
            
            # Call OpenAI for intelligent response
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            response = completion.choices[0].message.content.strip()
            logger.info(f"[INTELLIGENT_RESPONSE] Generated {context_type} response for '{user_input[:30]}...'")
            return response
            
        except Exception as e:
            logger.error(f"[INTELLIGENT_RESPONSE] Failed to generate response: {e}")
            # Fallback to simple language-appropriate response
            if lang == "he":
                return "אני רוצה לעזור לך! אפשר שמישהו מהצוות יחזור אליך? אשמח לקבל שם, טלפון ואימייל."
            else:
                return "I'd love to help you! Would you like someone from our team to follow up? Please share your name, phone, and email."

    def _generate_ai_response(self, question, session):
        """Generate AI response using OpenAI"""
        try:
            # Prepare messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history (limit to prevent token overflow)
            history = session.get("history", [])
            if len(history) > 10:  # Keep last 10 messages
                history = history[-10:]
            
            messages.extend(history)
            
            # Log token usage
            log_token_usage(messages, "gpt-4-turbo")
            
            # Call OpenAI
            logger.debug(f"[OPENAI] Calling GPT-4 Turbo with {len(messages)} messages")
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            answer = completion.choices[0].message.content.strip()
            logger.info(f"[OPENAI] ✅ Response generated successfully")
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI] Error calling GPT: {e}")
            raise e