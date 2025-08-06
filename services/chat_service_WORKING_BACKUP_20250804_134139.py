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
            logger.info(f"[LEAD_COMPLETED] Lead already collected - checking if user has new questions")
            
            # Allow conversation to continue if user asks new questions
            # Only give closure message if user is asking about lead status
            lead_status_keywords = ["lead", "contact", "details", "when", "call", "email", "phone", "פרטים", "מתי", "אימייל", "טלפון", "חזרה"]
            question_lower = question.lower()
            
            if any(keyword in question_lower for keyword in lead_status_keywords):
                logger.info(f"[LEAD_COMPLETED] User asking about lead status - providing closure")
                lang = detect_language(question)
                if lang == "he":
                    final_message = "תודה על ההודעה! כבר קיבלנו את הפרטים שלך וצוות Atarize יחזור אליך בקרוב. אין צורך בפעולות נוספות מצידך 😊"
                else:
                    final_message = "Thank you for your message! We already have your details and the Atarize team will contact you soon. No further action is needed from you 😊"
                return final_message, session
            else:
                logger.info(f"[LEAD_COMPLETED] User asking new question - continuing conversation normally")
                # Continue with normal conversation flow
                session.pop("lead_collected", None)  # Allow normal conversation
        
        # Add user message to history
        session["history"].append({"role": "user", "content": question})
        
        # Debug: Always test lead detection on every input
        from utils.validation_utils import detect_lead_info
        lead_test = detect_lead_info(question)
        logger.debug(f"[DEBUG] Lead detection test on '{question}': {lead_test}")
        
        # Step 1: Detect greeting context for GPT enrichment (no early returns)
        is_first_greeting = is_greeting(question) and not session.get("intro_given")
        is_repeat_greeting = is_greeting(question) and session.get("intro_given")
        
        if is_first_greeting:
            logger.info(f"[CONTEXT] First-time greeting detected - will enrich GPT context")
            session["intro_given"] = True
        elif is_repeat_greeting:
            logger.debug(f"[CONTEXT] Repeat greeting detected - will enrich GPT context")
        
        # Store greeting context for GPT
        greeting_context = {
            "is_first_greeting": is_first_greeting,
            "is_repeat_greeting": is_repeat_greeting,
            "intro_given": session.get("intro_given", False)
        }
        
        # Step 2: Advanced context detection
        # Detect business type and use cases
        if self._detect_business_type(question):
            session["business_type_detected"] = True
            logger.info(f"[CONTEXT] Business type detected in: '{question}'")
        
        specific_use_case = self._detect_specific_use_case(question)
        if specific_use_case:
            session["specific_use_case"] = specific_use_case
            logger.info(f"[CONTEXT] Specific use case detected: {specific_use_case}")
        
        # Detect positive engagement
        if self._detect_positive_engagement(question):
            session["positive_engagement"] = True
            logger.info(f"[CONTEXT] Positive engagement detected")
        
        # Detect conversation context for follow-up questions
        contextual_intent, context_info = self._get_conversation_context(question, session)
        if contextual_intent:
            session["follow_up_context"] = context_info.get("topic")
            logger.info(f"[CONTEXT] Follow-up context detected: {context_info.get('topic')}")
        
        # Check for lead information FIRST (before greeting detection)
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
            
            # Use GPT with context for lead confirmation instead of canned response
            enhanced_question = f"{question} [LEAD_DETECTED: {lead_details.get('name', 'Unknown')} - {lead_details.get('email', 'Unknown')} - {lead_details.get('phone', 'Unknown')}]"
            
            # Get context for lead confirmation
            context = self._get_context_from_chroma(question, "lead_confirmation")
            
            # Create a more natural lead confirmation prompt
            lead_confirmation_prompt = f"""The user has provided complete lead information (name, email, phone). 
            A lead notification has been sent to the team. 
            Provide a warm, concise confirmation that:
            1. Thanks them briefly
            2. Confirms their details were received
            3. Mentions someone will contact them soon
            4. Keeps the conversation open for follow-up questions
            
            User message: {question}
            
            Available context: {context}
            
            Respond naturally, warmly, and concisely (max 2-3 sentences)."""
            
            # Use the enhanced context method with the specific prompt
            answer = self._generate_ai_response_with_enhanced_context(enhanced_question, session, lead_confirmation_prompt)
            
            session["history"].append({"role": "assistant", "content": answer})
            return answer, session
        
        # Handle greeting logic (AFTER lead detection)
        if is_greeting(question) and not session.get("greeted"):
            session["greeted"] = True
            session["intro_given"] = True
            lang = detect_language(question)
            
            # Use GPT with context for greeting instead of hardcoded response
            context = self._get_context_from_chroma(question, "greeting")
            greeting_prompt = f"""The user is greeting you with: "{question}"
            
            This is the first interaction. Provide a warm, welcoming greeting that:
            1. Greets them back naturally
            2. Introduces yourself as Atara from Atarize
            3. Mentions you help with smart chatbots for businesses
            4. Keeps it friendly and conversational (max 2 sentences)
            
            Available context: {context}
            
            Respond in {"Hebrew" if lang == "he" else "English"} naturally and warmly."""
            
            greeting_response = self._generate_ai_response_with_enhanced_context(question, session, greeting_prompt)
            session["history"].append({"role": "assistant", "content": greeting_response})
            return greeting_response, session
        
        # Handle lead collection flow
        if session.get("interested_lead_pending"):
            logger.info(f"[CHAT_SERVICE] 🔄 Lead collection mode active - processing user input")
            return self._handle_lead_collection(question, session)
        
        # Check for confirmation responses BEFORE treating as vague input
        confirmation_words = ["כן", "yes", "אוקיי", "okay", "ok", "טוב", "בסדר", "sure", "נכון", "בטח"]
        question_lower = question.lower().strip()
        
        if question_lower in confirmation_words and len(session.get("history", [])) > 0:
            logger.info(f"[CHAT_SERVICE] ✅ Confirmation detected: '{question}' - providing contextual response")
            
            # Get the last bot message to understand what the user is confirming
            last_bot_message = ""
            for msg in reversed(session.get("history", [])):
                if msg.get("role") == "assistant":
                    last_bot_message = msg.get("content", "")
                    break
            
            logger.info(f"[CONFIRMATION_DEBUG] Last bot message: {last_bot_message[:100]}...")
            
            # Build context-aware confirmation response
            lang = detect_language(question)
            
            # Determine what type of information they're confirming they want
            if "מחיר" in last_bot_message or "עלות" in last_bot_message or "pricing" in last_bot_message.lower():
                context = self._get_context_from_chroma("pricing information", "pricing")
                info_type = "pricing"
            elif "דוגמ" in last_bot_message or "example" in last_bot_message.lower():
                context = self._get_context_from_chroma("use cases examples", "use_cases")
                info_type = "examples"
            elif "תהליך" in last_bot_message or "process" in last_bot_message.lower():
                context = self._get_context_from_chroma("setup process", "work_process")
                info_type = "process"
            else:
                context = self._get_context_from_chroma("general information", "general")
                info_type = "general"
            
            confirmation_prompt = f"""The user said "{question}" confirming they want {info_type} information.
            
            Previous conversation context: "{last_bot_message[:300]}..."
            
            IMMEDIATELY provide the specific {info_type} information they confirmed they want:
            
            Available detailed context: {context}
            
            RULES:
            - NO questions, NO "let me know if you need more"
            - Give them exactly what they confirmed they want
            - Be specific and include concrete details/numbers
            - Maximum 4 sentences
            
            Respond in {"Hebrew" if lang == "he" else "English"}."""
            
            confirmation_response = self._generate_ai_response_with_enhanced_context(question, session, confirmation_prompt)
            session["history"].append({"role": "assistant", "content": confirmation_response})
            return confirmation_response, session
        
        # Check for vague input (only for truly unclear messages)
        if len(question.strip()) < 3 and question_lower not in confirmation_words:
            logger.info(f"[CHAT_SERVICE] Very short input - generating intelligent response")
            session["interested_lead_pending"] = True
            intelligent_response = self._generate_intelligent_response("vague_input", question, session)
            session["history"].append({"role": "assistant", "content": intelligent_response})
            return intelligent_response, session
        
        # Generate AI response using OpenAI with enhanced context
        try:
            # Build enriched context for GPT
            enriched_context = self._build_enriched_context(question, session, greeting_context)
            
            # Use enhanced context retrieval
            lang = detect_language(question)
            intent_name = contextual_intent if contextual_intent else "general"
            
            # Get enhanced context using multiple strategies
            context_docs = self._get_enhanced_context_retrieval(question, intent_name, lang)
            
            # Build context string from documents
            context_parts = []
            for doc, meta in context_docs:
                context_parts.append(f"Context ({meta.get('intent', 'general')}): {doc}")
            
            context = "\n\n".join(context_parts)
            
            # Add enriched context signals
            if enriched_context:
                context = f"{enriched_context}\n\n{context}"
            
            # Check for product-market fit and lead transition opportunity
            if self._detect_product_market_fit(question, session):
                logger.info(f"[LEAD_TRANSITION] 🎯 Product-market fit detected - transitioning to lead collection")
                session["interested_lead_pending"] = True
                session["product_market_fit_detected"] = True
                
                # Generate contextual lead transition message
                transition_message = self._generate_lead_transition_message(session, lang)
                
                session["history"].append({"role": "assistant", "content": transition_message})
                return transition_message, session
            
            answer = self._generate_ai_response_with_enhanced_context(question, session, context)
            
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
        
        # Check if this is a product-market fit triggered lead collection
        is_pmf_triggered = session.get("product_market_fit_detected", False)
        
        # Check for exit phrases
        exit_phrases = ["היי", "עזוב", "לא עכשיו", "שכח מזה", "לא רוצה", "תודה לא", "די", "סגור"]
        question_lower = question.lower().strip()
        
        for phrase in exit_phrases:
            if phrase in question_lower:
                logger.info(f"[LEAD_FLOW] ✅ Exit phrase detected: '{phrase}' - resetting lead mode")
                session.pop("interested_lead_pending", None)
                session.pop("lead_request_count", None)
                session.pop("product_market_fit_detected", None)
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
        
        # For product-market fit triggered lead collection, be more patient
        max_requests = 3 if is_pmf_triggered else 2
        
        # After max requests, reset and continue normal flow
        if lead_request_count >= max_requests:
            logger.info(f"[LEAD_FLOW] 🔄 Max requests reached - resetting lead mode and continuing")
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
            session.pop("product_market_fit_detected", None)
            # Continue to normal processing
            return self._generate_ai_response_with_enhanced_context(question, session, ""), session
        else:
            # Generate context-aware lead request based on use case
            if is_pmf_triggered:
                lang = detect_language(question)
                use_case = session.get("specific_use_case")
                
                if use_case == "education" and lang == "he":
                    context_message = "כדי שנוכל להתחיל להקים את הבוט לבית הספר שלך, אני צריכה את הפרטים שלך. אפשר שם מלא, טלפון ואימייל?"
                elif use_case == "education" and lang == "en":
                    context_message = "To start setting up the bot for your school, I need your details. Can you share your full name, phone, and email?"
                elif lang == "he":
                    context_message = "כדי שנוכל להתחיל להקים את הבוט המותאם לך, אני צריכה את הפרטים שלך. אפשר שם מלא, טלפון ואימייל?"
                else:
                    context_message = "To start setting up your personalized bot, I need your details. Can you share your full name, phone, and email?"
                
                return context_message, session
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
        
        # Get context from Chroma for better responses
        context = self._get_context_from_chroma(user_input, context_type)
        
        # Build context-specific prompt
        if context_type == "vague_input":
            if lang == "he":
                context_prompt = f"המשתמש שלח הודעה קצרה או לא ברורה: '{user_input}'. תענה בחום ותבקש ממנו לפרט מה הוא מחפש. הקשר רלוונטי: {context}"
            else:
                context_prompt = f"User sent a vague or short message: '{user_input}'. Respond warmly and ask them to clarify what they're looking for. Relevant context: {context}"
        
        elif context_type == "vague_gpt_response":
            if lang == "he":
                context_prompt = f"לא הצלחתי למצוא תשובה טובה לשאלה: '{user_input}'. תסביר בנימוס שאני רוצה לעזור אך צריך יותר פרטים. הקשר רלוונטי: {context}"
            else:
                context_prompt = f"I couldn't find a good answer for: '{user_input}'. Politely explain that I want to help but need more details. Relevant context: {context}"
        
        elif context_type == "technical_error":
            if lang == "he":
                context_prompt = f"התרחשה שגיאה טכנית בעת עיבוד השאלה: '{user_input}'. תתנצל בנימוס ותציע פתרונות חלופיים. הקשר רלוונטי: {context}"
            else:
                context_prompt = f"A technical error occurred processing: '{user_input}'. Apologize politely and offer alternative solutions. Relevant context: {context}"
        
        elif context_type == "lead_request":
            if lang == "he":
                context_prompt = f"המשתמש בתהליך איסוף פרטים. תבקש ממנו בנימוס להשאיר שם, טלפון ואימייל כדי שנוכל לחזור אליו. הקשר רלוונטי: {context}"
            else:
                context_prompt = f"User is in lead collection process. Politely ask them to share their name, phone, and email so we can follow up. Relevant context: {context}"
        
        try:
            # Create messages for OpenAI
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": context_prompt}
            ]
            
            # Call OpenAI for intelligent response
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=200  # Reduced for more concise responses
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

    def _should_offer_help(self, context, user_input):
        """Determine if we should offer help based on available context"""
        # Only offer help if we have substantial context
        if not context or len(context.strip()) < 50:
            return False
        
        # Check if context contains specific, actionable information
        context_lower = context.lower()
        has_specific_info = any(keyword in context_lower for keyword in [
            "pricing", "cost", "setup", "integration", "features", "examples",
            "מחיר", "עלות", "הקמה", "אינטגרציה", "תכונות", "דוגמאות"
        ])
        
        return has_specific_info

    def _generate_helpful_offer(self, context, user_input, lang="he"):
        """Generate a specific, helpful offer based on available context"""
        if lang == "he":
            if "pricing" in context.lower() or "מחיר" in context.lower():
                return "רוצה שאתן לך פרטים נוספים על המחירים והחבילות השונות?"
            elif "integration" in context.lower() or "אינטגרציה" in context.lower():
                return "רוצה לראות איך ההטמעה עובדת בפועל?"
            elif "features" in context.lower() or "תכונות" in context.lower():
                return "רוצה שאסביר לך על התכונות הספציפיות שיכולות לעזור לעסק שלך?"
            else:
                return "רוצה שאתן לך דוגמה איך זה עובד בפועל?"
        else:
            if "pricing" in context.lower():
                return "Would you like more details about our pricing and packages?"
            elif "integration" in context.lower():
                return "Would you like to see how the integration works in practice?"
            elif "features" in context.lower():
                return "Would you like me to explain the specific features that could help your business?"
            else:
                return "Would you like to see an example of how this works in practice?"

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
                max_tokens=300  # Reduced from 500 to make responses more concise
            )
            
            answer = completion.choices[0].message.content.strip()
            logger.info(f"[OPENAI] ✅ Response generated successfully")
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI] Error calling GPT: {e}")
            raise e

    def _generate_ai_response_with_context(self, question, session, context_type="general"):
        """Generate AI response with enhanced context from Chroma"""
        try:
            # Get context from Chroma
            context = self._get_context_from_chroma(question, context_type)
            
            # Build enhanced prompt with context
            enhanced_prompt = self._build_contextual_prompt(question, context, context_type)
            
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": enhanced_prompt}
            ]
            
            # Add conversation history (limit to prevent token overflow)
            history = session.get("history", [])
            if len(history) > 8:  # Keep last 8 messages to leave room for context
                history = history[-8:]
            
            # Add history as separate messages
            for msg in history:
                messages.append(msg)
            
            # Log token usage
            log_token_usage(messages, "gpt-4-turbo")
            
            # Call OpenAI
            logger.debug(f"[OPENAI_CONTEXT] Calling GPT-4 Turbo with enhanced context")
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            answer = completion.choices[0].message.content.strip()
            logger.info(f"[OPENAI_CONTEXT] ✅ Response generated with context successfully")
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI_CONTEXT] Error calling GPT with context: {e}")
            # Fallback to regular response
            return self._generate_ai_response(question, session)

    def _generate_ai_response_with_enhanced_context(self, question, session, context):
        """Generate AI response with enhanced context from multiple sources"""
        try:
            # Check if we should offer help based on available context
            should_offer = self._should_offer_help(context, question)
            lang = detect_language(question)
            
            # Build enhanced prompt with all context
            if should_offer:
                helpful_offer = self._generate_helpful_offer(context, question, lang)
                enhanced_prompt = f"""User question: {question}

Available context and signals:
{context}

Provide a helpful, accurate, and contextual response using all available information. 
Be conversational, professional, and address the user's specific needs based on the context provided.

IMPORTANT: End your response with a specific, helpful offer: "{helpful_offer}"
Only make this offer if you have substantial information to provide."""
            else:
                enhanced_prompt = f"""User question: {question}

Available context and signals:
{context}

Provide a helpful, accurate, and contextual response using all available information. 
Be conversational, professional, and address the user's specific needs based on the context provided.

IMPORTANT: Do NOT offer to provide more information unless you have substantial, specific details to share."""
            
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": enhanced_prompt}
            ]
            
            # Add conversation history (limit to prevent token overflow)
            history = session.get("history", [])
            if len(history) > 6:  # Keep last 6 messages to leave room for enhanced context
                history = history[-6:]
            
            # Add history as separate messages
            for msg in history:
                messages.append(msg)
            
            # Log token usage
            log_token_usage(messages, "gpt-4-turbo")
            
            # Call OpenAI
            logger.debug(f"[OPENAI_ENHANCED] Calling GPT-4 Turbo with enhanced context")
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=300  # Reduced for more concise responses
            )
            
            answer = completion.choices[0].message.content.strip()
            logger.info(f"[OPENAI_ENHANCED] ✅ Response generated with enhanced context successfully")
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI_ENHANCED] Error calling GPT with enhanced context: {e}")
            # Fallback to regular response
            return self._generate_ai_response(question, session)

    def _get_context_from_chroma(self, question, context_type="general"):
        """Get relevant context from Chroma database"""
        try:
            # Get knowledge collection
            knowledge_collection = self.db_manager.get_knowledge_collection()
            if not knowledge_collection:
                logger.warning("[CONTEXT] No knowledge collection available")
                return ""
            
            # Search for relevant context
            results = knowledge_collection.query(
                query_texts=[question],
                n_results=3
            )
            
            if not results or not results['documents']:
                logger.debug("[CONTEXT] No relevant context found")
                return ""
            
            # Build context from results
            context_parts = []
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                context_parts.append(f"Context {i+1} ({metadata.get('intent', 'general')}): {doc}")
            
            context = "\n\n".join(context_parts)
            logger.info(f"[CONTEXT] Retrieved {len(context_parts)} context pieces")
            
            return context
            
        except Exception as e:
            logger.error(f"[CONTEXT] Error getting context from Chroma: {e}")
            return ""

    def _build_contextual_prompt(self, question, context, context_type="general"):
        """Build enhanced prompt with context"""
        if context_type == "lead_confirmation":
            base_prompt = f"""The user has provided complete lead information (name, email, phone). 
            A lead notification has been sent to the team. 
            Now provide a warm, professional confirmation message that:
            1. Thanks them for their interest
            2. Confirms their details were received
            3. Mentions someone will contact them soon
            4. Maintains the conversational tone
            
            User message: {question}
            
            Available context: {context}
            
            Respond naturally and warmly."""
        else:
            base_prompt = f"""User question: {question}
            
            Relevant context: {context}
            
            Provide a helpful, accurate response using the context provided."""
        
        return base_prompt

    def _get_conversation_context(self, question, session):
        """Analyze conversation history to understand follow-up questions in context"""
        history = session.get("history", [])
        if len(history) < 2:
            return None, None
        
        # Get recent conversation context (last 4 messages)
        recent_context = history[-4:]
        
        # Extract topics from recent conversation
        context_text = " ".join([msg.get("content", "") for msg in recent_context])
        context_lower = context_text.lower()
        question_lower = question.lower()
        
        # Context-aware topic detection
        contextual_intent = None
        context_info = {}
        
        # WhatsApp + Meta context
        if any(term in context_lower for term in ["whatsapp", "וואטסאפ"]) and \
           any(term in question_lower for term in ["meta", "approval", "אישור", "verification", "מאומת", "operator"]):
            contextual_intent = "faq"
            context_info = {
                "topic": "whatsapp_meta_verification",
                "specific_question": "Meta business verification for WhatsApp integration"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected WhatsApp+Meta follow-up question")
        
        # CRM + Integration context
        elif any(term in context_lower for term in ["crm", "integration", "אינטגרציה", "מערכות"]) and \
             any(term in question_lower for term in ["how", "איך", "possible", "אפשר", "requirements", "דרישות"]):
            contextual_intent = "faq" 
            context_info = {
                "topic": "crm_integration",
                "specific_question": "CRM and system integration capabilities"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected CRM integration follow-up question")
        
        # Pricing + Plans context
        elif any(term in context_lower for term in ["price", "cost", "מחיר", "עלות", "שח"]) and \
             any(term in question_lower for term in ["what about", "מה לגבי", "other", "אחר", "more", "עוד"]):
            contextual_intent = "pricing"
            context_info = {
                "topic": "pricing_details", 
                "specific_question": "Additional pricing information or plan details"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected pricing follow-up question")
        
        # Business use cases context
        elif any(term in context_lower for term in ["business", "עסק", "industry", "תחום"]) and \
             any(term in question_lower for term in ["example", "דוגמה", "how", "איך", "like mine", "כמו שלי"]):
            contextual_intent = "chatbot_use_cases"
            context_info = {
                "topic": "business_specific_examples",
                "specific_question": "Industry-specific chatbot use cases"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected business use case follow-up question")
        
        if contextual_intent:
            logger.info(f"[CONTEXT_BRIDGE] ✅ Contextual intent detected: {contextual_intent} | Topic: {context_info.get('topic')}")
            return contextual_intent, context_info
        else:
            logger.debug(f"[CONTEXT_BRIDGE] No specific context detected for follow-up")
            return None, None

    def _build_enriched_context(self, question, session, greeting_context=None):
        """Build enriched context from all detection signals for GPT"""
        context_signals = []
        
        # Greeting context
        if greeting_context:
            if greeting_context.get("is_first_greeting"):
                context_signals.append("CONTEXT: This is the user's first greeting - provide a warm welcome and introduction.")
            elif greeting_context.get("is_repeat_greeting"):
                context_signals.append("CONTEXT: This is a repeat greeting in an ongoing conversation - respond naturally and continue.")
        
        # Use case context
        if session.get("specific_use_case"):
            context_signals.append(f"CONTEXT: User has specific business use case: {session['specific_use_case']}")
        
        # Follow-up context
        if session.get("follow_up_context"):
            context_signals.append(f"CONTEXT: User is asking follow-up about: {session['follow_up_context']}")
        
        # Engagement context
        if session.get("positive_engagement"):
            context_signals.append("CONTEXT: User shows positive engagement and interest")
        
        # Conversion opportunity
        if session.get("conversion_opportunity"):
            context_signals.append("CONTEXT: This is a potential conversion opportunity - be helpful and guide naturally")
        
        # Lead collection context
        if session.get("interested_lead_pending"):
            context_signals.append("CONTEXT: User may be interested in leaving contact details if appropriate")
        
        return "\n".join(context_signals) if context_signals else ""

    def _get_knowledge_by_intent(self, intent_name):
        """Retrieve documents from the knowledge collection where metadata.intent == intent_name"""
        try:
            knowledge_collection = self.db_manager.get_knowledge_collection()
            if not knowledge_collection:
                return []
            
            results = knowledge_collection.get(where={"intent": intent_name}, include=["documents", "metadatas"])
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            logger.debug(f"[KNOWLEDGE_RETRIEVAL] Retrieved {len(docs)} documents for intent '{intent_name}'")
            return list(zip(docs, metas))
        except Exception as e:
            logger.error(f"[KNOWLEDGE_RETRIEVAL_ERROR] {e}")
            return []

    def _get_enhanced_context_retrieval(self, question, intent_name, lang="he", n_results=4):
        """Enhanced context retrieval that surfaces underutilized content through multiple strategies"""
        logger.debug(f"[ENHANCED_RETRIEVAL] Starting enhanced retrieval for: '{question}'")
        
        # Strategy 1: Intent-based retrieval
        knowledge_docs = self._get_knowledge_by_intent(intent_name)
        
        # Strategy 2: If intent fails or returns insufficient results, try semantic search on question
        if len(knowledge_docs) < 2:
            logger.debug(f"[ENHANCED_RETRIEVAL] Intent retrieval insufficient ({len(knowledge_docs)} docs), trying semantic search")
            try:
                knowledge_collection = self.db_manager.get_knowledge_collection()
                if not knowledge_collection:
                    return knowledge_docs
                
                # Semantic search on user question to catch underutilized content
                semantic_results = knowledge_collection.query(
                    query_texts=[question],
                    n_results=n_results,
                    where={"language": lang} if lang else None,
                    include=["documents", "metadatas"]
                )
                
                semantic_docs = semantic_results.get("documents", [[]])[0] if semantic_results.get("documents") else []
                semantic_metas = semantic_results.get("metadatas", [[]])[0] if semantic_results.get("metadatas") else []
                
                # Combine and deduplicate by document ID
                seen_ids = set()
                combined_docs = []
                
                # Add intent-based results first (higher priority)
                for doc, meta in knowledge_docs:
                    doc_id = meta.get("id", "")
                    if doc_id not in seen_ids:
                        combined_docs.append((doc, meta))
                        seen_ids.add(doc_id)
                
                # Add semantic results if not already included
                for doc, meta in zip(semantic_docs, semantic_metas):
                    doc_id = meta.get("id", "")
                    if doc_id not in seen_ids and len(combined_docs) < n_results:
                        combined_docs.append((doc, meta))
                        seen_ids.add(doc_id)
                
                logger.info(f"[ENHANCED_RETRIEVAL] Combined retrieval: {len(knowledge_docs)} intent + {len(semantic_docs)} semantic = {len(combined_docs)} total")
                return combined_docs
                
            except Exception as e:
                logger.error(f"[ENHANCED_RETRIEVAL] Semantic search failed: {e}")
                return knowledge_docs
        
        logger.debug(f"[ENHANCED_RETRIEVAL] Intent retrieval sufficient ({len(knowledge_docs)} docs)")
        return knowledge_docs

    def _detect_business_type(self, text):
        """Detect when user provides business type information"""
        text_lower = text.strip().lower()
        
        # Business type patterns in Hebrew
        business_patterns_he = [
            "יש לי חנות", "יש לי מסעדה", "יש לי קליניקה", "יש לי משרד", "יש לי עסק",
            "אני עובד", "אני מנהל", "אני בעלים", "אני סוכן", "אני רופא", "אני עורך דין",
            "חנות", "מסעדה", "קליניקה", "משרד", "בית מרקחת", "מרפאה", "סלון", "מכון כושר",
            "נדל\"ן", "ביטוח", "רכב", "תכשיטים", "אופנה", "טכנולוגיה", "חינוך", "ייעוץ",
            "אני עוסק", "אני עובד בתחום", "התחום שלי", "העסק שלי", "החברה שלי"
        ]
        
        # Business type patterns in English  
        business_patterns_en = [
            "i have a store", "i have a restaurant", "i have a clinic", "i have an office", "i have a business",
            "i work in", "i manage", "i own", "i am a doctor", "i am a lawyer", "i am an agent",
            "store", "restaurant", "clinic", "office", "pharmacy", "salon", "gym", "fitness",
            "real estate", "insurance", "automotive", "jewelry", "fashion", "technology", "education", "consulting",
            "my business", "my company", "my field", "our business", "our company"
        ]
        
        # Check for business type indicators
        is_business_response = (
            any(pattern in text_lower for pattern in business_patterns_he) or
            any(pattern in text_lower for pattern in business_patterns_en)
        )
        
        if is_business_response:
            logger.info(f"[BUSINESS_TYPE] Detected business type in: '{text}'")
            return True
        
        return False

    def _detect_specific_use_case(self, text):
        """Detect when user describes a specific business use case or pain point"""
        text_lower = text.strip().lower()
        
        # Education/Teaching use case patterns
        education_patterns = [
            "מורה", "מלמד", "בית ספר", "תלמידים", "לימודים", "חומר לימודי", "נושא לימודי",
            "מתמטיקה", "מדעים", "היסטוריה", "שפות", "כיתה", "חינוך", "אקדמיה", "אוניברסיטה",
            "teacher", "teaching", "school", "students", "education", "learning material", "subject",
            "mathematics", "science", "history", "languages", "classroom", "university", "academic"
        ]
        
        # Recruitment/HR use case patterns
        recruitment_patterns = [
            "מגייס עובדים", "גיוס עובדים", "מגייס אנשים", "מחפש עובדים", "רוצה לגייס",
            "מקבל טלפונים", "מלא טלפונים", "הרבה טלפונים", "טלפונים ללא הפסקה",
            "לסנן", "לסנן אנשים", "לסנן מועמדים", "סינון", "לא רלוונטי", "לא מתאים",
            "recruiting", "hiring", "hr", "human resources", "filter candidates", "screen applicants",
            "too many calls", "phone overload", "unqualified", "irrelevant candidates"
        ]
        
        # Restaurant/Food service patterns
        restaurant_patterns = [
            "מסעדה", "בר", "קפה", "אוכל", "תפריט", "הזמנות", "מקומות", "שולחנות",
            "restaurant", "cafe", "bar", "food", "menu", "reservations", "tables", "booking"
        ]
        
        # Retail/Store patterns  
        retail_patterns = [
            "חנות", "קמעונאות", "מוצרים", "מלאי", "מבצעים", "קניות", "לקוחות",
            "store", "retail", "shop", "products", "inventory", "sales", "customers", "shopping"
        ]
        
        # Real estate patterns
        realestate_patterns = [
            "נדל\"ן", "דירות", "בתים", "השכרה", "מכירה", "נכסים", "סיורים",
            "real estate", "apartments", "houses", "rental", "property", "tours", "listings"
        ]
        
        # Medical/Clinic patterns
        medical_patterns = [
            "קליניקה", "רופא", "מרפאה", "תורים", "חולים", "ביטוח", "טיפול",
            "clinic", "doctor", "medical", "appointments", "patients", "insurance", "treatment"
        ]
        
        # Check for specific use cases
        use_cases = {
            "education": any(pattern in text_lower for pattern in education_patterns),
            "recruitment": any(pattern in text_lower for pattern in recruitment_patterns),
            "restaurant": any(pattern in text_lower for pattern in restaurant_patterns),
            "retail": any(pattern in text_lower for pattern in retail_patterns),
            "real_estate": any(pattern in text_lower for pattern in realestate_patterns),
            "medical": any(pattern in text_lower for pattern in medical_patterns)
        }
        
        detected_use_cases = [use_case for use_case, detected in use_cases.items() if detected]
        
        if detected_use_cases:
            logger.info(f"[USE_CASE] Detected use case(s): {detected_use_cases} in: '{text}'")
            return detected_use_cases[0]  # Return first detected use case
        
        return None

    def _detect_positive_engagement(self, text):
        """Detect when user shows positive engagement or interest"""
        text_lower = text.strip().lower()
        
        # Positive engagement patterns in Hebrew
        positive_patterns_he = [
            "זה נשמע טוב", "זה מעניין", "אני מעוניין", "אני רוצה", "זה בדיוק מה שאני צריך",
            "זה יכול לעזור", "זה נראה טוב", "אני אוהב את זה", "זה נהדר", "זה מושלם",
            "כן", "בטח", "אפשר", "למה לא", "בואו ננסה", "אני רוצה לנסות"
        ]
        
        # Positive engagement patterns in English
        positive_patterns_en = [
            "sounds good", "interesting", "i'm interested", "i want", "this is exactly what i need",
            "this could help", "this looks good", "i like this", "this is great", "this is perfect",
            "yes", "sure", "okay", "why not", "let's try", "i want to try"
        ]
        
        # Check for positive engagement
        is_positive = (
            any(pattern in text_lower for pattern in positive_patterns_he) or
            any(pattern in text_lower for pattern in positive_patterns_en)
        )
        
        if is_positive:
            logger.info(f"[ENGAGEMENT] Detected positive engagement in: '{text}'")
            return True
        
        return False

    def _detect_product_market_fit(self, question, session):
        """Detect when there's clear alignment between user needs and product capabilities"""
        question_lower = question.lower()
        history = session.get("history", [])
        
        # Check for strong conversion signals - require more specific commitment language
        conversion_signals = [
            # Direct implementation/setup questions (stronger commitment)
            "איך בונים", "איך מקימים", "איך מתחילים", "איך נתחיל", "איך אפשר להתחיל",
            "how do we build", "how do we set up", "how do we start", "how can we start",
            
            # Specific personal use case questions (stronger intent)
            "אם אני רוצה לבנות", "אם אני רוצה להקים", "אם אני רוצה ליצור",
            "if i want to build", "if i want to set up", "if i want to create",
            
            # Direct process/next steps questions
            "מה התהליך", "מה השלבים", "מה צריך לעשות", "איך ממשיכים",
            "what's the process", "what are the steps", "what do we need to do", "how do we proceed",
            
            # Ready-to-start language
            "רוצה להתחיל", "רוצים להתחיל", "מוכן להתחיל", "איך נקדם",
            "want to get started", "ready to start", "how do we move forward"
        ]
        
        # Exclude questions that are just seeking general information
        information_seeking_patterns = [
            "מה דוגמאות", "איזה דוגמאות", "אפשר דוגמאות", "תן לי דוגמאות",
            "what examples", "give me examples", "can you give examples",
            "איך זה עובד בעסקים", "איך זה עובד למסעדות", "איך זה עובד בכלל",
            "how does it work for businesses", "how does it work in general"
        ]
        
        # Don't trigger if this is just an information request
        is_information_seeking = any(pattern in question_lower for pattern in information_seeking_patterns)
        
        # Check for conversion signals in current question (but exclude information seeking)
        has_conversion_signal = (
            any(signal in question_lower for signal in conversion_signals) and 
            not is_information_seeking
        )
        
        # Check for positive engagement in recent history
        recent_positive_engagement = False
        if len(history) >= 2:
            recent_messages = history[-4:]  # Last 4 messages
            for msg in recent_messages:
                if msg.get("role") == "user" and self._detect_positive_engagement(msg.get("content", "")):
                    recent_positive_engagement = True
                    break
        
        # Check for use case detection in session
        has_use_case = session.get("specific_use_case") is not None
        
        # Check for business type detection
        has_business_type = session.get("business_type_detected", False)
        
        # Determine if there's clear product-market fit (more conservative approach)
        product_market_fit = (
            # Strong conversion signal with context
            (has_conversion_signal and (has_use_case or has_business_type)) or
            # Multiple positive indicators together
            (recent_positive_engagement and has_use_case and has_business_type)
        )
        
        if product_market_fit:
            logger.info(f"[PRODUCT_MARKET_FIT] ✅ Detected clear alignment - conversion signal: {has_conversion_signal}, positive engagement: {recent_positive_engagement}, use case: {has_use_case}, business type: {has_business_type}")
            return True
        
        return False

    def _generate_lead_transition_message(self, session, lang="he"):
        """Generate a smooth transition message to lead collection based on context"""
        use_case = session.get("specific_use_case")
        business_type = session.get("business_type_detected", False)
        
        if lang == "he":
            if use_case == "education":
                return "נשמע שזה בדיוק מה שאתה צריך! רוצה שנתחיל להקים את הבוט המותאם לבית הספר שלך? אשמח לקבל את הפרטים שלך כדי שנוכל להתחיל."
            elif use_case == "restaurant":
                return "זה נשמע כמו פתרון מושלם למסעדה שלך! רוצה שנתחיל להקים את הבוט? אשמח לקבל את הפרטים שלך כדי שנוכל להתחיל."
            elif use_case == "recruitment":
                return "זה בדיוק מה שיעזור לך עם הגיוס! רוצה שנתחיל להקים את הבוט המותאם לצרכים שלך? אשמח לקבל את הפרטים שלך."
            elif business_type:
                return "נשמע שזה בדיוק מה שהעסק שלך צריך! רוצה שנתחיל להקים את הבוט המותאם אישית? אשמח לקבל את הפרטים שלך."
            else:
                return "נשמע שזה בדיוק מה שאתה צריך! רוצה שנתחיל להקים את הבוט המותאם אישית? אשמח לקבל את הפרטים שלך."
        else:
            if use_case == "education":
                return "This sounds exactly like what you need! Want to start setting up the bot for your school? I'd love to get your details so we can get started."
            elif use_case == "restaurant":
                return "This sounds like the perfect solution for your restaurant! Want to start setting up the bot? I'd love to get your details so we can get started."
            elif use_case == "recruitment":
                return "This is exactly what will help with your recruitment! Want to start setting up the bot tailored to your needs? I'd love to get your details."
            elif business_type:
                return "This sounds exactly like what your business needs! Want to start setting up the personalized bot? I'd love to get your details."
            else:
                return "This sounds exactly like what you need! Want to start setting up the personalized bot? I'd love to get your details."