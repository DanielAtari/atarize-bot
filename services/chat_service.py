import logging
import os
import json
import hashlib
from config.settings import Config
from utils.text_utils import detect_language, is_greeting, get_natural_greeting, is_small_talk
from utils.validation_utils import detect_lead_info, is_vague_gpt_answer, detect_buying_intent
from utils.token_utils import count_tokens, log_token_usage
from services.advanced_cache_service import AdvancedCacheService
from services.response_variation_service import ResponseVariationService
from services.context_manager import context_manager
from services.fast_response_service import fast_response_service

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db_manager, openai_client):
        self.db_manager = db_manager
        self.openai_client = openai_client
        
        # Initialize advanced caching with predictive capabilities
        self.cache_manager = AdvancedCacheService(
            max_size=1000,  # Larger cache for advanced features
            default_ttl=3600  # 1 hour default TTL
        )
        
        # Initialize response variation service to eliminate repetitive phrases
        self.response_variation = ResponseVariationService()
        
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
    
    def _get_session_id(self, session):
        """Generate consistent session ID for response variation tracking"""
        # Create session ID from session data
        if "session_id" not in session:
            # Generate session ID from history or create new one
            history_str = str(session.get("history", []))
            session_id = hashlib.md5(history_str.encode()).hexdigest()[:8]
            session["session_id"] = session_id
        return session["session_id"]
    
    def handle_question(self, question, session, lang=None):
        """
        Main chat handling logic - Fixed version with consistent intent detection
        """
        # Performance timing
        import time
        overall_start_time = time.time()
        
        # Initialize variables to prevent UnboundLocalError
        answer = None
        intent_name = "unknown"
        
        # 🔧 FIX: LANGUAGE DETECTION FALLBACK
        if not lang:
            lang = detect_language(question)
            logger.debug(f"[LANGUAGE_FALLBACK] Auto-detected language: {lang} for question: '{question[:30]}...'")
        else:
            logger.debug(f"[LANGUAGE_PROVIDED] Using provided language: {lang}")
        
        logger.debug(f"\n{'='*60}")
        logger.info(f"[CHAT_SERVICE] Starting processing for: '{question}' (lang: {lang})")
        
        # Initialize session keys if they don't exist
        if "history" not in session:
            session["history"] = []
            logger.debug(f"[SESSION_INIT] Initialized empty history")
        if "greeted" not in session:
            session["greeted"] = False
        if "intro_given" not in session:
            session["intro_given"] = False
        if "information_provided" not in session:
            session["information_provided"] = False
        if "helpful_responses_count" not in session:
            session["helpful_responses_count"] = 0
        
        # Validate session state consistency
        self._validate_session_state(session)
        
        # 🔧 FIX 1: CONSISTENT INTENT DETECTION AT START
        from services.intent_service import IntentService
        intent_service = IntentService(self.db_manager)
        intent_name = intent_service.detect_intent_chroma(question)
        if not intent_name:
            intent_name = "unknown"
        logger.info(f"[INTENT_DETECTION] Detected intent: {intent_name} for question: '{question[:50]}...'")
        
        # ✅ REMOVED: HIGH-CONFIDENCE INTENTS BYPASS 
        # All intents now follow proper GPT-FIRST → VAGUE-FALLBACK → CONTEXT-ENHANCED flow
        # Intent detection is logged but doesn't trigger automatic responses
        
        # 🔧 UX FIX: Handle "speak to someone" requests without assumptions
        speak_to_someone_patterns = [
            "i want to speak to someone", "want to speak to someone", "talk to someone", 
            "speak to a person", "talk to a person", "human agent", "real person",
            "אני רוצה לדבר עם מישהו", "רוצה לדבר עם מישהו", "לדבר עם נציג", "אדם אמיתי"
        ]
        if any(pattern in question.lower() for pattern in speak_to_someone_patterns):
            logger.info(f"[SPEAK_TO_SOMEONE] Detected request to speak to someone")
            speak_response = self._generate_intelligent_response("speak_to_someone", question, session)
            if speak_response:
                session["history"].append({"role": "assistant", "content": speak_response})
                return speak_response, session
        
        # Note: Response variation is handled by the existing ResponseVariationService
        # which is already integrated and working properly
        
        # Check if lead collection is already completed
        if session.get("lead_collected"):
            logger.info(f"[LEAD_COMPLETED] Lead already collected - checking message type")
            
            question_lower = question.lower().strip()
            
            # Check for goodbye/thank you messages - provide warm closure
            goodbye_patterns = ["תודה", "תודה רבה", "ביי", "להתראות", "שיהיה לך יום טוב", "thank you", "thanks", "bye", "goodbye", "have a good day"]
            if any(pattern in question_lower for pattern in goodbye_patterns):
                logger.info(f"[LEAD_COMPLETED] Goodbye/thank you detected - providing warm closure")
                # Using already detected lang
                if lang == "he":
                    final_message = "תודה לך! אנחנו כאן אם תצטרך משהו נוסף. שיהיה לך יום נהדר! 😊"
                else:
                    final_message = "Thank you! We're here if you need anything else. Have a great day! 😊"
                return final_message, session
            
            # Check for lead status questions
            lead_status_keywords = ["lead", "contact", "details", "when", "call", "email", "phone", "פרטים", "מתי", "אימייל", "טלפון", "חזרה", "נציג", "representative"]
            if any(keyword in question_lower for keyword in lead_status_keywords):
                logger.info(f"[LEAD_COMPLETED] User asking about lead status - providing status update")
                # Using already detected lang
                if lang == "he":
                    final_message = "מעולה! כבר קיבלנו את הפרטים שלך ונציג מצוות Atarize יחזור אליך בהקדם. אתה בתור! 😊"
                else:
                    final_message = "Perfect! We already have your details and a representative from Atarize will contact you soon. You're all set! 😊"
                return final_message, session
            
            # For any other questions, provide helpful answers while maintaining lead_collected state
            logger.info(f"[LEAD_COMPLETED] User asking new question - continuing conversation while preserving lead status")
            
            # Check if this is a process/implementation question - provide focused answer
            process_keywords = ["איך זה יכול לעבוד", "איך זה עובד", "איך זה יעבוד", "how will it work", "how does it work", "how will this work"]
            if any(keyword in question_lower for keyword in process_keywords):
                logger.info(f"[LEAD_COMPLETED] Process question after lead collection - providing focused implementation answer")
                # Get relevant context and provide a focused answer about implementation
                context = self._get_context_from_chroma(question, "implementation_process")
                
                implementation_prompt = f"""The user has already provided their lead details and committed to getting a bot. 
                They're now asking about the implementation process/how it will work in practice.
                
                This is a FOLLOW-UP question from a converted lead. Be:
                1. Specific about the implementation process
                2. Confident about the results they'll get
                3. Brief but informative (2-3 sentences)
                4. Reassuring about the next steps
                
                User question: {question}
                Context: {context}
                
                Answer their implementation question while maintaining the excitement about their decision."""
                
                answer = self._generate_ai_response_with_enhanced_context(question, session, implementation_prompt)
                session["history"].append({"role": "assistant", "content": answer})
                return answer, session
            
            # For other questions, continue with normal flow but maintain lead status
            # DON'T remove lead_collected - just continue with normal flow
        
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
        
        # Step 2: Advanced context detection with context manager
        # Update user context with the new question
        context_manager.update_user_context(session, question)
        
        # Detect business type and use cases (only for information purposes, not for early customization)
        if self._detect_business_type(question):
            session["business_type_detected"] = True
            logger.info(f"[CONTEXT] Business type detected in: '{question}' (for information only)")
        
        specific_use_case = self._detect_specific_use_case(question)
        if specific_use_case:
            session["specific_use_case"] = specific_use_case
            logger.info(f"[CONTEXT] Specific use case detected: {specific_use_case} (for information only)")
        
        # ✅ ENHANCED: Detect positive engagement with improved satisfaction recognition
        if self._detect_positive_engagement(question):
            session["positive_engagement"] = True
            # ✅ NEW: Track consecutive positive engagement for stronger lead signals
            session["positive_engagement_count"] = session.get("positive_engagement_count", 0) + 1
            logger.info(f"[ENGAGEMENT] Positive engagement detected (count: {session['positive_engagement_count']})")
        
        # Detect conversation context for follow-up questions
        contextual_intent, context_info = self._get_conversation_context(question, session)
        if contextual_intent:
            session["follow_up_context"] = context_info.get("topic")
            logger.info(f"[CONTEXT] Follow-up context detected: {context_info.get('topic')}")
        
        # Buying intent detection moved to the beginning of handle_question method
        # This section is now handled earlier in the flow
        
        # Check for lead information (after buying intent detection)
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
            
            # Use Response Variation Service for varied lead confirmations
            session_id = self._get_session_id(session)
            has_hebrew_name = any(char in question for char in 'אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
            lang = detect_language(question)
            
            # Force Hebrew if we detect Hebrew characters in the lead info  
            if lang == "he" or has_hebrew_name:
                response_lang = "he"
            else:
                response_lang = "en"
            
            # Get varied lead confirmation response
            answer = self.response_variation.select_varied_response(
                category="lead_confirmation",
                language=response_lang,
                session_id=session_id,
                context="lead_provided"
            )
            
            logger.info(f"[RESPONSE_VARIATION] Generated varied lead confirmation (lang: {response_lang})")
            
            session["history"].append({"role": "assistant", "content": answer})
            return answer, session
        
        # Check for buying intent FIRST (before greeting logic) - HIGHEST PRIORITY
        from utils.validation_utils import detect_buying_intent
        if detect_buying_intent(question):
            logger.info(f"[BUYING_INTENT] 🎯 IMMEDIATE BUYING INTENT DETECTED - PRIORITY FLOW!")
            logger.info(f"[BUYING_INTENT] User message: '{question}'")
            session["interested_lead_pending"] = True
            session["buying_intent_detected"] = True
            session["conversion_critical_moment"] = True
            
            # Pure buying intent - request lead details
            lang = detect_language(question)
            if lang == "he":
                buying_response = "מעולה! כדי שנתקדם, אשמח שתשאיר את הפרטים שלך: שם מלא, טלפון ואימייל – ונחזור אליך לתיאום ההקמה."
            else:
                buying_response = "Excellent! To proceed, I'd be happy if you could share your details: full name, phone, and email – and we'll get back to you to coordinate the setup."
            
            session["history"].append({"role": "assistant", "content": buying_response})
            return buying_response, session

        # Handle greeting logic (AFTER buying intent check)
        if is_greeting(question) and not session.get("greeted") and not session.get("buying_intent_detected"):
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
        
        # Continue with other logic after buying intent and greeting detection

        # REMOVED: Automatic pricing detection - all responses now come from context only

        # Check for simple goodbye OR thank you BEFORE processing 
        simple_goodbye_patterns = ["ביי", "להתראות", "bye", "goodbye", "תודה רבה", "thank you", "thanks"]
        question_lower = question.lower().strip()
        if any(pattern in question_lower for pattern in simple_goodbye_patterns) and not session.get("lead_collected"):
            logger.info(f"[GOODBYE] Simple goodbye/thank you detected - providing clean closure")
            lang = detect_language(question)
            if "תודה" in question_lower or "thank" in question_lower:
                if lang == "he":
                    goodbye_response = "בשמחה! אם תצטרך עזרה בעתיד, אני כאן 😊"
                else:
                    goodbye_response = "You're welcome! If you need help in the future, I'm here 😊"
            else:
                if lang == "he":
                    goodbye_response = "להתראות! אם תצטרך עזרה בעתיד, אני כאן 😊"
                else:
                    goodbye_response = "Goodbye! If you need help in the future, I'm here 😊"
            session["history"].append({"role": "assistant", "content": goodbye_response})
            return goodbye_response, session

        # Handle lead collection flow
        if session.get("interested_lead_pending"):
            logger.info(f"[CHAT_SERVICE] 🔄 Lead collection mode active - processing user input")
            return self._handle_lead_collection(question, session)
        
        # Check for confirmation responses BEFORE treating as vague input
        confirmation_words = ["כן", "yes", "אוקיי", "okay", "ok", "טוב", "בסדר", "sure", "נכון", "בטח"]
        question_lower = question.lower().strip()
        
        if question_lower in confirmation_words and len(session.get("history", [])) > 0:
            logger.info(f"[CHAT_SERVICE] ✅ Confirmation detected: '{question}' - using Response Variation Service")
            
            # Get the last bot message to understand context
            last_bot_message = ""
            for msg in reversed(session.get("history", [])):
                if msg.get("role") == "assistant":
                    last_bot_message = msg.get("content", "")
                    break
            
            # Use existing Response Variation Service for varied responses
            session_id = self._get_session_id(session)
            lang = detect_language(question)
            
            # Determine response category based on conversation context
            if "מחיר" in last_bot_message or "price" in last_bot_message.lower():
                category = "pricing_follow"
            elif "טכני" in last_bot_message or "technical" in last_bot_message.lower():
                category = "technical_follow"
            else:
                category = "general_help"
            
            # Get varied response from Response Variation Service
            varied_response = self.response_variation.select_varied_response(
                category=category,
                language=lang,
                session_id=session_id,
                context="confirmation"
            )
            
            logger.info(f"[RESPONSE_VARIATION] Generated varied confirmation response (category: {category})")
            session["history"].append({"role": "assistant", "content": varied_response})
            return varied_response, session
        
        # Check for vague input (only for truly unclear messages)
        if len(question.strip()) < 3 and question_lower not in confirmation_words:
            logger.info(f"[CHAT_SERVICE] Very short input - will try to understand and offer help naturally")
            # Don't immediately set lead_pending - let GPT try to understand first
            # If GPT can't help, then we'll offer assistance as a natural follow-up
        
        # Generate AI response using OpenAI with enhanced context
        try:
            # ⚡ PERFORMANCE OPTIMIZATION: Use lighter context for simple questions
            lang = detect_language(question)
            
            # Check if this is a simple question that doesn't need heavy context
            simple_patterns = ["היי", "שלום", "מה", "כמה", "איך", "hello", "hi", "what", "how", "much"]
            is_simple_question = len(question.split()) <= 3 and any(pattern in question.lower() for pattern in simple_patterns)
            
            if is_simple_question:
                # Fast path for simple questions - minimal context
                context = self._get_context_from_chroma(question, "general")
                logger.info(f"[PERFORMANCE] ⚡ Fast path for simple question: '{question}'")
            else:
                # Full context for complex questions
                enriched_context = self._build_enriched_context(question, session, greeting_context)
                intent_name = contextual_intent if contextual_intent else "general"
                context_docs = self._get_enhanced_context_retrieval(question, intent_name, lang)
                
                # Build context string from documents
                context_parts = []
                for doc, meta in context_docs:
                    context_parts.append(f"Context ({meta.get('intent', 'general')}): {doc}")
                
                context = "\n\n".join(context_parts)
                
                # Add enriched context signals
                if enriched_context:
                    context = f"{enriched_context}\n\n{context}"
            
            # Buying intent detection now handled at the start of the method
            # Check if buying intent was already detected earlier
            buying_intent_detected = session.get("buying_intent_detected", False)
            if buying_intent_detected:
                logger.info(f"[BUYING_INTENT] Using previously detected buying intent")
            
            # Check for product-market fit (for non-buying intent cases)
            product_market_fit_detected = self._detect_product_market_fit(question, session)
            if product_market_fit_detected and not buying_intent_detected:
                logger.info(f"[LEAD_TRANSITION] 🎯 Product-market fit detected - will answer question then offer assistance")
                session["product_market_fit_detected"] = True
                # Continue to generate answer first, then we'll add assistance offer
            
            answer = self._generate_ai_response_with_enhanced_context(question, session, context, is_simple_question)
            
            # 🔧 FIX 4: IMPROVED VAGUE GPT FALLBACK WITH CHROMA RETRY
            if not answer or is_vague_gpt_answer(answer):
                logger.info(f"[VAGUE_FALLBACK] Vague GPT response detected - trying Chroma fallback")
                
                # First try: Get the best semantic match from Chroma and generate GPT response with it
                context_fallback = self._get_context_from_chroma(question, "general")
                if context_fallback and len(context_fallback.strip()) > 100:
                    logger.info(f"[VAGUE_FALLBACK] ✅ Retrieved Chroma context ({len(context_fallback)} chars) - generating GPT response")
                    # ✅ FIXED: Use GPT with Chroma context instead of raw Chroma content
                    answer = self._generate_ai_response_with_enhanced_context(question, session, context_fallback, is_simple_question)
                    # 🔧 FIX 3: CLEAN SESSION FLAGS after successful fallback
                    session.pop("interested_lead_pending", None)
                    session.pop("lead_request_count", None)
                    self._mark_information_provided(session)
                else:
                    # Second try: Generate alternative response
                    alternative_response = self._generate_intelligent_response("helpful_alternative", question, session)
                    if alternative_response and not is_vague_gpt_answer(alternative_response):
                        answer = alternative_response
                        logger.info(f"[VAGUE_FALLBACK] ✅ Generated better alternative response")
                        self._mark_information_provided(session)
                    else:
                        # Only trigger lead collection if we have provided some information first
                        if session.get("information_provided", False) or session.get("helpful_responses_count", 0) >= 1:
                            logger.info(f"[VAGUE_FALLBACK] Could not generate helpful response - offering assistance after providing info")
                            session["interested_lead_pending"] = True
                            assistance_response = self._generate_intelligent_response("vague_gpt_response", question, session)
                            session["history"].append({"role": "assistant", "content": assistance_response})
                            return assistance_response, session
                        else:
                            # ✅ FIXED: Generate helpful response via GPT instead of hardcoded text
                            logger.info(f"[VAGUE_FALLBACK] Generating helpful response via GPT instead of lead collection")
                            gpt_helpful_response = self._generate_intelligent_response("helpful_fallback", question, session)
                            if gpt_helpful_response:
                                session["history"].append({"role": "assistant", "content": gpt_helpful_response})
                                return gpt_helpful_response, session
                            else:
                                # Final fallback only if GPT generation fails
                                logger.warning(f"[VAGUE_FALLBACK] GPT generation failed - using minimal fallback")
                                minimal_response = self._generate_ai_response("אני כאן לעזור לך! איך אני יכולה לסייע?", session)
                                session["history"].append({"role": "assistant", "content": minimal_response})
                                return minimal_response, session
            
            # Mark that helpful information was provided (if we have a good answer)
            if answer and not is_vague_gpt_answer(answer):
                self._mark_information_provided(session)
            
            # If buying intent was detected, add immediate lead collection
            if buying_intent_detected and answer:
                logger.info(f"[BUYING_INTENT] Adding immediate lead collection for buying intent")
                lead_message = self._generate_lead_transition_message(session, lang)
                if lead_message:
                    answer = f"{answer}\n\n{lead_message}"
            
            # ✅ ENHANCED: Check for high engagement that warrants immediate lead collection
            elif self._should_initiate_lead_collection_from_engagement(session) and answer:
                logger.info(f"[LEAD_TRANSITION] 🎯 High engagement detected - initiating natural lead collection")
                # ✅ GPT-FIRST: Generate natural lead collection transition via GPT
                lead_transition = self._generate_intelligent_response("high_engagement_lead_collection", question, session)
                if lead_transition:
                    answer = f"{answer}\n\n{lead_transition}"
                    session["interested_lead_pending"] = True
                else:
                    # Fallback to assistance offer if GPT generation fails
                    assistance_offer = self._generate_assistance_offer(question, session, lang)
                    if assistance_offer:
                        answer = f"{answer}\n\n{assistance_offer}"
                        session["interested_lead_pending"] = True
            # If product-market fit was detected (and no buying intent), add helpful offer to the answer
            elif product_market_fit_detected and answer:
                logger.info(f"[LEAD_TRANSITION] Adding helpful assistance offer to answer")
                assistance_offer = self._generate_assistance_offer(question, session, lang)
                if assistance_offer:
                    answer = f"{answer}\n\n{assistance_offer}"
                    session["interested_lead_pending"] = True  # Now it's appropriate to collect lead
            
            # 🎯 RESPONSE VARIATION: Add natural ending to avoid repetitive patterns
            # SKIP if this is a technical question, or goodbye/thank you to avoid lead collection triggers
            is_info_only = (self._is_technical_question(question) or
                           self._is_goodbye_or_thanks(question))
            
            if not is_info_only:
                session_id = self._get_session_id(session)
                lang = detect_language(question)
                
                # Only add ending if appropriate (not too long, not already ending with question)
                if (self.response_variation.should_add_ending(answer, session_id) and 
                    len(answer) < 350 and not answer.strip().endswith("?")):
                    
                    # Add varied ending based on context
                    answer = self.response_variation.generate_natural_ending(
                        base_response=answer,
                        context=question,
                        language=lang,
                        session_id=session_id
                    )
                    logger.info(f"[RESPONSE_VARIATION] Added natural ending to response")
            else:
                logger.info(f"[RESPONSE_VARIATION] Skipping response variation for info-only response")
            
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
            # Try to provide a helpful fallback response instead of immediately going to lead collection
            fallback_response = self._generate_fallback_response(question, session)
            if fallback_response:
                session["history"].append({"role": "assistant", "content": fallback_response})
                return fallback_response, session
            else:
                # Only if fallback fails, then offer assistance
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
        is_buying_intent = session.get("buying_intent_detected", False)
        
        # Check for exit phrases
        exit_phrases = ["היי", "עזוב", "לא עכשיו", "שכח מזה", "לא רוצה", "תודה לא", "די", "סגור"]
        question_lower = question.lower().strip()
        
        for phrase in exit_phrases:
            if phrase in question_lower:
                logger.info(f"[LEAD_FLOW] ✅ Exit phrase detected: '{phrase}' - resetting lead mode")
                session.pop("interested_lead_pending", None)
                session.pop("lead_request_count", None)
                session.pop("product_market_fit_detected", None)
                session.pop("buying_intent_detected", None)
                lang = detect_language(question)
                if lang == "he":
                    return "בסדר גמור! אם תרצה עזרה בעתיד, אני כאן. איך אפשר לעזור? 😊", session
                else:
                    return "No worries, let's continue. Feel free to ask me anything! 😊", session
        
        # Check for process questions during lead collection - answer them first
        process_questions = ["איך התהליך עובד", "איך זה עובד", "איך זה יעבוד", "מה התהליך", "how does the process work", "how does it work"]
        if any(pattern in question_lower for pattern in process_questions):
            logger.info(f"[LEAD_FLOW] Process question during lead collection - providing answer first")
            lang = detect_language(question)
            if lang == "he":
                process_answer = "התהליך פשוט: קודם נאסוף את הפרטים שלך, אז מישהו מהצוות יחזור אליך תוך 24 שעות להתחיל את ההקמה. בתהליך נגדיר יחד מה הבוט צריך לדעת ולענות, ובתוך 2-5 ימי עבודה תקבל את הבוט המותאם אישית לעסק שלך.\n\nאפשר שם מלא, טלפון ואימייל?"
            else:
                process_answer = "The process is simple: first we collect your details, then someone from our team will contact you within 24 hours to start the setup. During the process, we'll define together what the bot needs to know and answer, and within 2-5 working days you'll receive the bot customized for your business.\n\nCan you share your full name, phone, and email?"
            return process_answer, session
        
        # REMOVED: Duplicate lead detection logic
        # Lead detection is now handled ONLY in main flow (lines 98-141)
        # This prevents duplicate processing and double email notifications
        
        # If user is in lead collection mode but hasn't provided complete info yet:
        # Increment request count
        lead_request_count = session.get("lead_request_count", 0) + 1
        session["lead_request_count"] = lead_request_count
        logger.debug(f"[LEAD_FLOW] ❌ No lead info detected - request count now: {lead_request_count}")
        
        # For buying intent, provide context first then ask for details
        if is_buying_intent or session.get("conversion_critical_moment"):
            logger.info(f"[LEAD_FLOW] 🎯 Buying intent detected - providing contextual lead collection")
            lang = detect_language(question)
            
            # First, acknowledge their excitement and briefly explain the process
            if lang == "he":
                if lead_request_count == 1:  # First time asking after buying intent
                    context_message = "יופי! אני מתרגשת לעזור לך להקים את הבוט! 🤖\n\nהתהליך פשוט: קודם אנחנו אוספים את הפרטים שלך, אז מישהו מהצוות יחזור אליך תוך 24 שעות להתחיל את ההקמה.\n\nאפשר שם מלא, טלפון ואימייל?"
                else:
                    context_message = "כדי שנוכל להתחיל להקים את הבוט, אני צריכה את הפרטים שלך: שם מלא, טלפון ואימייל."
            else:
                if lead_request_count == 1:  # First time asking after buying intent
                    context_message = "Awesome! I'm excited to help you set up your bot! 🤖\n\nThe process is simple: first we collect your details, then someone from our team will contact you within 24 hours to start the setup.\n\nCan you share your full name, phone, and email?"
                else:
                    context_message = "To get started with your bot setup, I need your details: full name, phone, and email."
            return context_message, session
        
        # For product-market fit triggered lead collection, be more patient
        max_requests = 3 if is_pmf_triggered else 2
        
        # After max requests, reset and continue normal flow
        if lead_request_count >= max_requests:
            logger.info(f"[LEAD_FLOW] 🔄 Max requests reached - resetting lead mode and continuing")
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
            session.pop("product_market_fit_detected", None)
            session.pop("buying_intent_detected", None)
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
                    context_message = "כדי שנוכל להתחיל להקים את הבוט, אני צריכה את הפרטים שלך. אפשר שם מלא, טלפון ואימייל?"
                else:
                    context_message = "To start setting up the bot, I need your details. Can you share your full name, phone, and email?"
                
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
        
        # Rule 4: buying_intent_detected should not exist without interested_lead_pending (unless lead is collected)
        if session.get("buying_intent_detected") and not session.get("interested_lead_pending") and not session.get("lead_collected"):
            logger.warning("[SESSION_FIX] ⚠️ Conflict: buying_intent_detected exists without interested_lead_pending and no collected lead")
            logger.warning("[SESSION_FIX] 🔧 Fixing: Clearing buying_intent_detected")
            session.pop("buying_intent_detected", None)
        
        # Rule 5: Clean up conversion_critical_moment after lead is collected
        if session.get("lead_collected") and session.get("conversion_critical_moment"):
            logger.info("[SESSION_FIX] 🔧 Lead collected - clearing conversion_critical_moment flag")
            session.pop("conversion_critical_moment", None)
        
        # Rule 6: History should always be a list
        if "history" in session and not isinstance(session["history"], list):
            logger.warning("[SESSION_FIX] ⚠️ Invalid: history is not a list")
            logger.warning("[SESSION_FIX] 🔧 Fixing: Resetting history to empty list")
            session["history"] = []
        
        # Log current session state for debugging
        logger.debug(f"[SESSION_STATE] greeted={session.get('greeted', False)}, "
                    f"intro_given={session.get('intro_given', False)}, "
                    f"lead_pending={session.get('interested_lead_pending', False)}, "
                    f"lead_collected={session.get('lead_collected', False)}, "
                    f"buying_intent={session.get('buying_intent_detected', False)}, "
                    f"info_provided={session.get('information_provided', False)}, "
                    f"helpful_count={session.get('helpful_responses_count', 0)}, "
                    f"request_count={session.get('lead_request_count', 0)}, "
                    f"history_length={len(session.get('history', []))}")

    def _generate_intelligent_response(self, context_type, user_input, session, reason=""):
        """Generate contextually appropriate, language-aware responses using GPT"""
        from utils.text_utils import detect_language
        
        lang = detect_language(user_input)
        
        # Get context from Chroma for better responses
        context = self._get_context_from_chroma(user_input, context_type)
        
        # 🔧 UX FIX: Simplified cache for faster lookup
        cache_key = f"{context_type}:{user_input[:50]}"  # Shortened key for performance
        cached_response = self.cache_manager.get(cache_key, session)
        if cached_response:
            logger.info(f"[CACHE_HIT] Fast cached response for {context_type}")
            return cached_response
        
        # 🔧 QA FIX: Add explicit language consistency instruction
        lang_instruction = "ענה רק בעברית ולא בשפות אחרות." if lang == "he" else "Respond only in English and no other languages."
        
        # Build context-specific prompt
        if context_type == "vague_input":
            if lang == "he":
                context_prompt = f"המשתמש שלח הודעה קצרה או לא ברורה: '{user_input}'. תענה בחום ותבקש ממנו לפרט מה הוא מחפש. {lang_instruction} הקשר רלוונטי: {context}"
            else:
                context_prompt = f"User sent a vague or short message: '{user_input}'. Respond warmly and ask them to clarify what they're looking for. {lang_instruction} Relevant context: {context}"
        
        elif context_type == "vague_gpt_response":
            # 🔧 UX FIX: Shortened vague response prompts
            if lang == "he":
                context_prompt = f"תסביר קצר שאת רוצה לעזור אך צריך יותר פרטים על '{user_input}'. {lang_instruction}"
            else:
                context_prompt = f"Briefly explain you want to help but need more details about '{user_input}'. {lang_instruction}"
        
        elif context_type == "technical_error":
            # 🔧 UX FIX: Shortened error prompts
            if lang == "he":
                context_prompt = f"תתנצל קצר על שגיאה בעיבוד '{user_input}' ותציע עזרה. {lang_instruction}"
            else:
                context_prompt = f"Briefly apologize for error processing '{user_input}' and offer help. {lang_instruction}"
        
        elif context_type == "helpful_alternative":
            # 🔧 UX FIX: Shortened alternative prompts
            if lang == "he":
                context_prompt = f"תענה מועיל וקצר לשאלה '{user_input}'. {lang_instruction}"
            else:
                context_prompt = f"Answer '{user_input}' helpfully and briefly. {lang_instruction}"
        
        elif context_type == "lead_request":
            # 🔧 UX FIX: Shortened lead request prompts
            if lang == "he":
                context_prompt = f"תבקש בנימוס שם, טלפון ואימייל. {lang_instruction}"
            else:
                context_prompt = f"Politely ask for name, phone, and email. {lang_instruction}"
        
        elif context_type == "high_engagement_lead_collection":
            # 🔧 UX FIX: Shortened prompts for faster, more concise responses
            if lang == "he":
                context_prompt = f"המשתמש מתלהב מהשירות. תענה קצר לשאלה '{user_input}', ואז תבקש בטבעיות שם, טלפון ואימייל. {lang_instruction}"
            else:
                context_prompt = f"User is enthusiastic about the service. Answer '{user_input}' briefly, then naturally ask for name, phone, and email. {lang_instruction}"
        
        elif context_type == "speak_to_someone":
            # 🔧 UX FIX: Handle vague "speak to someone" requests without assumptions
            if lang == "he":
                context_prompt = f"המשתמש רוצה לדבר עם מישהו: '{user_input}'. תענה קצר ותשאל מה המטרה או איך אפשר לעזור, בלי להניח הנחות על העסק שלו. {lang_instruction}"
            else:
                context_prompt = f"User wants to speak to someone: '{user_input}'. Respond briefly and ask what they need help with, without making assumptions about their business. {lang_instruction}"
        
        elif context_type == "helpful_fallback":
            # 🔧 UX FIX: Shortened fallback prompts
            if lang == "he":
                context_prompt = f"תענה מועיל וקצר לשאלה '{user_input}', תציע עזרה. {lang_instruction}"
            else:
                context_prompt = f"Answer '{user_input}' helpfully and briefly, offer assistance. {lang_instruction}"
        
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
                max_tokens=400  # Increased to prevent truncation
            )
            
            response = completion.choices[0].message.content.strip()
            # Ensure complete sentences
            response = self._ensure_complete_sentence(response)
            logger.info(f"[INTELLIGENT_RESPONSE] Generated {context_type} response for '{user_input[:30]}...' (length: {len(response)} chars)")
            
            # 💾 PERFORMANCE: Cache response for future fast lookup
            self.cache_manager.set(f"{context_type}:{user_input}", response, session)
            
            return response
            
        except Exception as e:
            logger.error(f"[INTELLIGENT_RESPONSE] Failed to generate response: {e}")
            # Fallback to simple language-appropriate response
            if lang == "he":
                return "אני רוצה לעזור לך! אפשר שמישהו מהצוות יחזור אליך? אשמח לקבל שם, טלפון ואימייל."
            else:
                return "I'd love to help you! Would you like someone from our team to follow up? Please share your name, phone, and email."
    
    def _generate_assistance_offer(self, question, session, lang):
        """Generate a varied assistance offer using response variation service"""
        # Get session ID for tracking
        session_id = self._get_session_id(session)
        
        # Determine category based on question context
        question_lower = question.lower()
        if "pricing" in question_lower or "cost" in question_lower or "מחיר" in question_lower:
            category = "pricing_follow"
        elif "technical" in question_lower or "integration" in question_lower or "טכני" in question_lower:
            category = "technical_follow"
        elif "help" in question_lower or "assistance" in question_lower or "עזרה" in question_lower:
            category = "assistance_offer"
        else:
            category = "general_help"
        
        # Use response variation service for fast, varied response
        varied_offer = self.response_variation.select_varied_response(
            category=category,
            language=lang,
            session_id=session_id,
            context=question
        )
        
        logger.info(f"[ASSISTANCE_OFFER] ⚡ Fast varied offer (category: {category}): {varied_offer[:50]}...")
        return varied_offer
    
    def _generate_fallback_response(self, question, session):
        """Generate a helpful fallback response when technical errors occur"""
        try:
            lang = detect_language(question)
            context = self._get_context_from_chroma(question, "general")
            
            if lang == "he":
                fallback_prompt = f"""המשתמש שאל: '{question}'. 
                
                התרחשה שגיאה טכנית, אבל אני עדיין רוצה לעזור. 
                תנסה לספק תשובה מועילת בהתבסס על ההקשר הזה: {context}
                
                אם אין מספיק מידע, תכתב תשובה כללית ומועילת על השירות של Atarize."""
            else:
                fallback_prompt = f"""User asked: '{question}'.
                
                A technical error occurred, but I still want to help.
                Try to provide a useful answer based on this context: {context}
                
                If there's not enough information, write a general helpful response about Atarize's service."""
            
            # Add language enforcement to system prompt
            lang_instruction = "Respond in Hebrew" if lang == "he" else "Respond in English"
            enhanced_system_prompt = f"{self.system_prompt}\n\nCRITICAL: {lang_instruction} - match the user's language exactly."
            
            messages = [
                {"role": "system", "content": enhanced_system_prompt},
                {"role": "user", "content": fallback_prompt}
            ]
            
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            fallback = completion.choices[0].message.content.strip()
            logger.info(f"[FALLBACK] Generated fallback response: {fallback[:50]}...")
            return fallback
            
        except Exception as e:
            logger.error(f"[FALLBACK] Failed to generate fallback: {e}")
            return None

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

    def _generate_helpful_offer(self, context, user_input, lang="he", session=None):
        """Generate a varied, helpful offer based on context using response variation service"""
        # Get session ID for tracking
        session_id = self._get_session_id(session) if session else "default"
        
        # Determine category based on context
        context_lower = context.lower()
        if "pricing" in context_lower or "מחיר" in context_lower or "cost" in context_lower:
            category = "pricing_follow"
        elif "integration" in context_lower or "אינטגרציה" in context_lower or "technical" in context_lower:
            category = "technical_follow"
        else:
            category = "general_help"
        
        # Use response variation service to get varied response
        varied_offer = self.response_variation.select_varied_response(
            category=category,
            language=lang,
            session_id=session_id,
            context=context
        )
        
        logger.info(f"[RESPONSE_VARIATION] Generated varied offer (category: {category}, lang: {lang})")
        return varied_offer

    def _generate_ai_response(self, question, session):
        """Generate AI response using OpenAI"""
        try:
            # 🚀 PERFORMANCE: Check cache first for fast response
            cached_response = self.cache_manager.get(question, session)
            if cached_response:
                logger.info(f"[CACHE_HIT] Fast cached basic response for: '{question[:30]}...'")
                # Handle both string and dict cached responses
                if isinstance(cached_response, dict):
                    return cached_response.get("answer", "")
                return cached_response
            
            # Detect language and add language instruction
            lang = detect_language(question)
            lang_instruction = "Respond in Hebrew" if lang == "he" else "Respond in English"
            
            # Prepare messages for OpenAI with language enforcement
            enhanced_system_prompt = f"{self.system_prompt}\n\nIMPORTANT: {lang_instruction} - match the user's language exactly."
            messages = [{"role": "system", "content": enhanced_system_prompt}]
            
            # ⚡ OPTIMIZED: Minimal conversation history for speed
            history = session.get("history", [])
            if len(history) > 3:  # Keep only last 3 messages for faster processing
                history = history[-3:]
            
            messages.extend(history)
            
            # Log token usage
            log_token_usage(messages, "gpt-4-turbo")
            
            # ⚡ OPTIMIZED: Fast OpenAI call with reduced tokens
            logger.debug(f"[OPENAI] Fast GPT-4 Turbo call with {len(messages)} messages")
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=250  # Reduced for faster generation
            )
            
            answer = completion.choices[0].message.content.strip()
            
            # Ensure complete sentences - if response ends mid-sentence, truncate to last complete sentence
            answer = self._ensure_complete_sentence(answer)
            
            logger.info(f"[OPENAI] ✅ Response generated successfully (length: {len(answer)} chars)")
            
            # 💾 PERFORMANCE: Cache response for future fast lookup
            self.cache_manager.set(question, answer, session)
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI] Error calling GPT: {e}")
            raise e

    def _ensure_complete_sentence(self, text):
        """
        Ensure the response ends with a complete sentence.
        If it ends mid-sentence, truncate to the last complete sentence.
        """
        if not text or len(text) < 10:  # Very short responses are probably complete
            return text
            
        # Hebrew sentence endings
        hebrew_sentence_endings = ['!', '?', '.', ':', '।', '؟', '؛']
        
        # Check if the text already ends properly
        if text[-1] in hebrew_sentence_endings:
            return text
            
        # Find the last complete sentence
        last_good_pos = -1
        for i, char in enumerate(text):
            if char in hebrew_sentence_endings:
                # Look ahead to see if there's meaningful content after this
                remaining = text[i+1:].strip()
                if len(remaining) > 3:  # More than just a few characters left
                    last_good_pos = i + 1
                else:
                    # This might be the end, keep the ending punctuation
                    return text[:i+1]
        
        # If we found a good truncation point, use it
        if last_good_pos > 0:
            return text[:last_good_pos].strip()
            
        # If no good truncation point found, check for common incomplete patterns
        incomplete_patterns = [
            'נ', 'ה', 'ו', 'ב', 'מ', 'ל', 'כ', 'ש',  # Hebrew prefixes that suggest incomplete words
            'המ', 'העל', 'הת', 'את',  # Common Hebrew incomplete endings
            'אי', 'בי', 'על', 'מה'   # Other incomplete patterns
        ]
        
        # Look for word boundaries and avoid cutting mid-word
        words = text.split()
        if len(words) > 1:
            # Remove the last word if it looks incomplete
            last_word = words[-1]
            if (len(last_word) < 3 or 
                any(last_word.endswith(pattern) for pattern in incomplete_patterns) or
                not any(char in hebrew_sentence_endings for char in last_word)):
                return ' '.join(words[:-1]) + '.'
        
        # If all else fails, add a period if it doesn't end with punctuation
        if text and text[-1] not in hebrew_sentence_endings:
            return text + '.'
            
        return text

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
                max_tokens=450  # Reduced slightly but still allows complete sentences
            )
            
            answer = completion.choices[0].message.content.strip()
            # Ensure complete sentences
            answer = self._ensure_complete_sentence(answer)
            logger.info(f"[OPENAI_CONTEXT] ✅ Response generated with context successfully (length: {len(answer)} chars)")
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI_CONTEXT] Error calling GPT with context: {e}")
            # Fallback to regular response
            return self._generate_ai_response(question, session)

    def _generate_ai_response_with_enhanced_context(self, question, session, context, is_simple_question=False):
        """Generate AI response with enhanced context from multiple sources"""
        try:
            # 🚀 PERFORMANCE: Check cache first for fast enhanced response
            cached_response = self.cache_manager.get(question, session)
            if cached_response:
                logger.info(f"[CACHE_HIT] Fast cached enhanced response for: '{question[:30]}...'")
                # Handle both string and dict cached responses
                if isinstance(cached_response, dict):
                    return cached_response.get("answer", "")
                return cached_response
            
            # Check if we should offer help based on available context
            should_offer = self._should_offer_help(context, question)
            lang = detect_language(question)
            
            # Build enhanced prompt with context-aware management
            lang_instruction = "Respond in Hebrew" if lang == "he" else "Respond in English"
            
            if should_offer:
                helpful_offer = self._generate_helpful_offer(context, question, lang, session)
                base_prompt = f"""User question: {question}

Available context and signals:
{context}

Provide a helpful, accurate, and contextual response using all available information. 
Be conversational, professional, and address the user's specific needs based on the context provided.

IMPORTANT: End your response with a specific, helpful offer: "{helpful_offer}"
Only make this offer if you have substantial information to provide.

LANGUAGE: {lang_instruction} - match the user's language exactly."""
            else:
                base_prompt = f"""User question: {question}

Available context and signals:
{context}

Provide a helpful, accurate, and contextual response using all available information. 
Be conversational, professional, and address the user's specific needs based on the context provided.

IMPORTANT: Do NOT offer to provide more information unless you have substantial, specific details to share.

LANGUAGE: {lang_instruction} - match the user's language exactly."""
            
            # Use context manager to create context-aware prompt
            enhanced_prompt = context_manager.get_context_aware_prompt(session, question, base_prompt)
            
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": enhanced_prompt}
            ]
            
            # ⚡ ULTRA-OPTIMIZED: Minimal conversation history for maximum speed
            history = session.get("history", [])
            if len(history) > 2:  # Keep only last 2 messages for fastest processing
                history = history[-2:]
            
            # Add history as separate messages
            for msg in history:
                messages.append(msg)
            
            # Log token usage
            log_token_usage(messages, "gpt-4-turbo")
            
            # ⚡ PERFORMANCE: Use faster model for simple questions
            if is_simple_question:
                model = "gpt-3.5-turbo"
                max_tokens = 200
                logger.debug(f"[OPENAI_ENHANCED] ⚡ Fast GPT-3.5 call for simple question")
            else:
                model = "gpt-4-turbo"
                max_tokens = 300
                logger.debug(f"[OPENAI_ENHANCED] Standard GPT-4 Turbo call with enhanced context")
            
            completion = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens
            )
            
            answer = completion.choices[0].message.content.strip()
            # Ensure complete sentences
            answer = self._ensure_complete_sentence(answer)
            
            # 🔍 CONTEXT VALIDATION: Check if response respects user context
            if not context_manager.validate_response_context(answer, session):
                logger.warning(f"[CONTEXT_VALIDATION] Response violates user context, regenerating...")
                # Try to regenerate with stronger context awareness
                correction_prompt = f"""{base_prompt}

CRITICAL: The user has previously stated their business type. Do NOT ask about unrelated business types.
Current user business: {context_manager.get_context_summary(session).get('business_type', 'unknown')}

Provide a response that is appropriate for the user's actual business type."""
                
                completion = self.openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": correction_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=300
                )
                answer = completion.choices[0].message.content.strip()
                answer = self._ensure_complete_sentence(answer)
                logger.info(f"[CONTEXT_VALIDATION] ✅ Regenerated response with proper context awareness")
            
            logger.info(f"[OPENAI_ENHANCED] ✅ Response generated with enhanced context successfully (length: {len(answer)} chars)")
            
            # 💾 PERFORMANCE: Cache enhanced response for future fast lookup
            self.cache_manager.set(question, {"answer": answer, "cached": True, "enhanced_context": True}, session)
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPENAI_ENHANCED] Error calling GPT with enhanced context: {e}")
            # Fallback to regular response
            return self._generate_ai_response(question, session)

    def _get_context_from_chroma(self, question, context_type="general"):
        """🔧 ENHANCED: Combined intent + semantic context retrieval (called during vague response fallback)"""
        try:
            # 🚀 PERFORMANCE: Check database cache first for fast context retrieval
            query_key = f"{question}:{context_type}"
            cached_context = self.cache_manager.get_db_query(query_key)
            if cached_context:
                logger.info(f"[CACHE_HIT] Fast cached context for: '{question[:30]}...' ({context_type})")
                return cached_context
            
            # Get knowledge collection
            knowledge_collection = self.db_manager.get_knowledge_collection()
            if not knowledge_collection:
                logger.warning("[CONTEXT] No knowledge collection available")
                return ""
            
            # 🔧 COMBINED RETRIEVAL: Intent + Semantic approach for better context
            combined_context = ""
            
            # STEP 1: Try intent-based retrieval first (if we can detect intent)
            from services.intent_service import IntentService
            intent_service = IntentService(self.db_manager)
            intent_name = intent_service.detect_intent_chroma(question)
            
            if intent_name and intent_name != "unknown":
                logger.debug(f"[COMBINED_CONTEXT] Detected intent: {intent_name} - getting intent-based docs")
                intent_docs = self._get_knowledge_by_intent(intent_name)
                if intent_docs:
                    # Use the first (best) intent document
                    best_intent_doc = intent_docs[0][0] if intent_docs[0] else ""
                    if best_intent_doc and len(best_intent_doc.strip()) > 100:
                        combined_context = best_intent_doc[:500]  # Limit for performance
                        logger.info(f"[COMBINED_CONTEXT] ✅ Using intent-based context ({len(combined_context)} chars)")
            
            # STEP 2: If no good intent context, fall back to semantic search
            if not combined_context:
                logger.debug(f"[COMBINED_CONTEXT] No intent context found, using semantic search")
                results = knowledge_collection.query(
                    query_texts=[question[:100]],  # Limit query length for speed
                    n_results=1,  # Single best result for fastest retrieval
                    include=["documents", "metadatas"]  # Only include what we need
                )
                
                if results and results['documents']:
                    doc = results['documents'][0][0] if results['documents'][0] else ""
                    combined_context = doc[:500] if doc else ""  # Limit context length for speed
                    logger.info(f"[COMBINED_CONTEXT] ✅ Using semantic context ({len(combined_context)} chars)")
            
            # STEP 3: Final fallback if still no context
            if not combined_context:
                logger.debug("[COMBINED_CONTEXT] No relevant context found")
                return ""
            
            # 💾 PERFORMANCE: Cache context for future fast retrieval
            self.cache_manager.cache_db_query(query_key, combined_context, ttl=2400)  # 40 minutes TTL
            
            logger.info(f"[COMBINED_CONTEXT] ✅ Final context delivered ({len(combined_context)} chars)")
            return combined_context
            
        except Exception as e:
            logger.error(f"[COMBINED_CONTEXT] Error getting context from Chroma: {e}")
            return ""
    
    def get_cache_stats(self):
        """Get cache performance statistics"""
        return self.cache_manager.get_advanced_stats()
    
    def clear_cache(self, pattern=None):
        """Clear cache entries, optionally by pattern"""
        if pattern:
            self.cache_manager.invalidate_pattern(pattern)
            logger.info(f"[CACHE] Cleared cache entries matching pattern: {pattern}")
        else:
            self.cache_manager.clear()
            logger.info("[CACHE] Cleared all cache entries")
    
    def log_cache_performance(self):
        """Log cache performance statistics"""
        stats = self.get_cache_stats()
        logger.info(f"[CACHE_STATS] Entries: {stats['total_entries']}/{stats['max_size']}, "
                   f"Hit Rate: {stats['hit_rate_percent']}%, "
                   f"Total Queries: {stats['total_queries']}, "
                   f"Evictions: {stats['evictions']}")
    
    def get_performance_summary(self):
        """Get performance-focused summary including cache and variation metrics"""
        cache_stats = self.cache_manager.get_performance_summary()
        variation_stats = self.response_variation.get_variation_stats()
        
        return {
            "cache_performance": cache_stats,
            "response_variation": variation_stats,
            "optimization_status": "Caching + Response variation enabled for fast, natural responses"
        }
    
    def get_variation_stats(self):
        """Get response variation statistics"""
        return self.response_variation.get_variation_stats()
    
    def clear_conversation_state(self, session_id=None):
        """Clear conversation state for response variation tracking"""
        if session_id:
            self.response_variation.clean_session_state(session_id)
            logger.info(f"[RESPONSE_VARIATION] Cleared conversation state for session: {session_id}")
        else:
            # Clear all states
            self.response_variation.conversation_state.clear()
            logger.info("[RESPONSE_VARIATION] Cleared all conversation states")

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
        
        # ⚡ OPTIMIZED: Get recent conversation context (last 2 messages for speed)
        recent_context = history[-2:]
        
        # Simplified topic extraction
        context_text = " ".join([msg.get("content", "") for msg in recent_context]).lower()
        question_lower = question.lower()
        
        # Fast pattern matching
        contextual_intent = None
        context_info = {}
        
        # WhatsApp + Meta context
        if any(term in context_text for term in ["whatsapp", "וואטסאפ"]) and \
           any(term in question_lower for term in ["meta", "approval", "אישור", "verification", "מאומת", "operator"]):
            contextual_intent = "faq"
            context_info = {
                "topic": "whatsapp_meta_verification",
                "specific_question": "Meta business verification for WhatsApp integration"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected WhatsApp+Meta follow-up question")
        
        # CRM + Integration context
        elif any(term in context_text for term in ["crm", "integration", "אינטגרציה", "מערכות"]) and \
             any(term in question_lower for term in ["how", "איך", "possible", "אפשר", "requirements", "דרישות"]):
            contextual_intent = "faq" 
            context_info = {
                "topic": "crm_integration",
                "specific_question": "CRM and system integration capabilities"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected CRM integration follow-up question")
        
        # Pricing + Plans context
        elif any(term in context_text for term in ["price", "cost", "מחיר", "עלות", "שח"]) and \
             any(term in question_lower for term in ["what about", "מה לגבי", "other", "אחר", "more", "עוד"]):
            contextual_intent = "pricing"
            context_info = {
                "topic": "pricing_details", 
                "specific_question": "Additional pricing information or plan details"
            }
            logger.info(f"[CONTEXT_BRIDGE] Detected pricing follow-up question")
        
        # Business use cases context
        elif any(term in context_text for term in ["business", "עסק", "industry", "תחום"]) and \
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

    def _get_enhanced_context_retrieval(self, question, intent_name, lang="he", n_results=3):
        """⚡ OPTIMIZED context retrieval - fast single-query approach"""
        logger.debug(f"[ENHANCED_RETRIEVAL] ⚡ Starting fast retrieval for: '{question[:30]}...'")
        
        try:
            knowledge_collection = self.db_manager.get_knowledge_collection()
            if not knowledge_collection:
                logger.warning("[ENHANCED_RETRIEVAL] No knowledge collection available")
                return []
            
            # Single semantic search query (fastest approach)
            semantic_results = knowledge_collection.query(
                query_texts=[question],
                n_results=n_results,
                where={"language": lang} if lang else None,
                include=["documents", "metadatas"]
            )
            
            # Quick processing without complex deduplication
            if not semantic_results or not semantic_results.get("documents"):
                logger.debug(f"[ENHANCED_RETRIEVAL] No results found")
                return []
                
            semantic_docs = semantic_results["documents"][0]
            semantic_metas = semantic_results["metadatas"][0] if semantic_results.get("metadatas") else [{}] * len(semantic_docs)
            
            combined_docs = [(doc, meta) for doc, meta in zip(semantic_docs, semantic_metas)]
            
            logger.info(f"[ENHANCED_RETRIEVAL] ⚡ Fast retrieval: {len(combined_docs)} docs in single query")
            return combined_docs
                
        except Exception as e:
            logger.error(f"[ENHANCED_RETRIEVAL] Fast retrieval failed: {e}")
            return []

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

    def _should_initiate_lead_collection_from_engagement(self, session):
        """✅ ENHANCED: Determine if high engagement warrants immediate lead collection"""
        # Check for strong positive engagement signals
        positive_count = session.get("positive_engagement_count", 0)
        has_recent_positive = session.get("positive_engagement", False)
        info_provided = session.get("information_provided", False)
        helpful_count = session.get("helpful_responses_count", 0)
        
        # ✅ HIGH ENGAGEMENT CRITERIA:
        # 1. Multiple positive engagement signals OR
        # 2. Strong single engagement + information provided OR  
        # 3. High satisfaction after helpful responses
        high_engagement = (
            positive_count >= 2 or  # Multiple positive responses
            (has_recent_positive and info_provided and helpful_count >= 1) or  # Satisfied after getting info
            (has_recent_positive and helpful_count >= 2)  # Satisfied after multiple helpful responses
        )
        
        # Don't interrupt if already collecting leads
        already_collecting = session.get("interested_lead_pending", False) or session.get("lead_collected", False)
        
        if high_engagement and not already_collecting:
            logger.info(f"[HIGH_ENGAGEMENT] 🎯 Criteria met for lead collection - positive_count: {positive_count}, info_provided: {info_provided}, helpful_count: {helpful_count}")
            return True
        
        return False

    def _detect_positive_engagement(self, text):
        """Detect when user shows positive engagement or interest"""
        text_lower = text.strip().lower()
        
        # ✅ ENHANCED: Positive engagement patterns in Hebrew (including excitement expressions)
        positive_patterns_he = [
            "זה נשמע טוב", "זה מעניין", "אני מעוניין", "אני רוצה", "זה בדיוק מה שאני צריך",
            "זה יכול לעזור", "זה נראה טוב", "אני אוהב את זה", "זה נהדר", "זה מושלם",
            "כן", "בטח", "אפשר", "למה לא", "בואו ננסה", "אני רוצה לנסות",
            # ✅ NEW: High excitement and satisfaction expressions
            "אה וואו", "מהמם", "וואו", "איזה כיף", "זה מדהים", "פנטסטי", "מושלם",
            "בדיוק מה שחיפשתי", "זה נראה מדהים", "אני נרגש", "אני מתרגש", "זה בטח יעזור לי",
            "אני חייב את זה", "זה בדיוק מה שאני צריך", "זה יכול לשנות הכל", "זה גאוני"
        ]
        
        # ✅ ENHANCED: Positive engagement patterns in English (including excitement expressions)  
        positive_patterns_en = [
            "sounds good", "interesting", "i'm interested", "i want", "this is exactly what i need",
            "this could help", "this looks good", "i like this", "this is great", "this is perfect",
            "yes", "sure", "okay", "why not", "let's try", "i want to try",
            # ✅ NEW: High excitement and satisfaction expressions
            "oh wow", "amazing", "awesome", "fantastic", "incredible", "brilliant", "excellent",
            "that's exactly what I was looking for", "this looks amazing", "I'm excited", "I love it",
            "I need this", "this could change everything", "this is genius", "impressive",
            # 🔧 QA FIX: Missing business enthusiasm patterns
            "perfect for my business", "sounds perfect", "exactly what my business needs",
            "this is perfect for us", "perfect solution", "ideal for my company",
            "this fits perfectly", "exactly what we're looking for", "this would be great for us"
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

    # REMOVED: Automatic pricing detection functions - all responses now come from context only
    
    def _is_technical_question(self, question):
        """Check if the question is asking about technical details"""
        text_lower = question.lower().strip()
        technical_patterns = [
            "איך זה עובד", "איך הבוט עובד", "טכני", "אינטגרציה", "וואטסאפ", "טכנולוגיה",
            "how does it work", "how does the bot work", "technical", "integration", "whatsapp", "technology"
        ]
        return any(pattern in text_lower for pattern in technical_patterns)
    
    def _is_goodbye_or_thanks(self, question):
        """Check if the question is a goodbye or thank you message"""
        text_lower = question.lower().strip()
        goodbye_patterns = [
            "ביי", "להתראות", "תודה", "תודה רבה", "תודות", 
            "bye", "goodbye", "thank you", "thanks", "farewell"
        ]
        return any(pattern in text_lower for pattern in goodbye_patterns)

    def _detect_product_market_fit(self, question, session):
        """Detect when there's clear alignment between user needs and product capabilities"""
        question_lower = question.lower()
        history = session.get("history", [])
        
        # Check for strong conversion signals - require more specific commitment language
        conversion_signals = [
            # Direct buying/purchase intent (strongest signal)
            "אני רוצה לקנות", "רוצה לקנות", "רוצה לרכוש", "אני רוצה לרכוש",
            "i want to buy", "want to buy", "want to purchase", "i want to purchase",
            
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
            "how does it work for businesses", "how does it work in general",
            "איזה צבע", "איזה עיצוב", "איך זה יראה", "מה אפשר לעשות",
            "what color", "what design", "how will it look", "what can we do"
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
        
        # Check for direct buying intent first (strongest signal)
        buying_intent_patterns = [
            "אני רוצה לקנות", "רוצה לקנות", "רוצה לרכוש", "אני רוצה לרכוש",
            "i want to buy", "want to buy", "want to purchase", "i want to purchase"
        ]
        
        has_direct_buying_intent = any(pattern in question_lower for pattern in buying_intent_patterns)
        
        # Determine if there's clear product-market fit
        product_market_fit = (
            # Direct buying intent (immediate trigger)
            has_direct_buying_intent or
            # Strong conversion signal with context AND positive engagement
            (has_conversion_signal and recent_positive_engagement and (has_use_case or has_business_type)) or
            # Multiple positive indicators together with clear intent
            (recent_positive_engagement and has_use_case and has_business_type and has_conversion_signal)
        )
        
        if product_market_fit:
            logger.info(f"[PRODUCT_MARKET_FIT] ✅ Detected clear alignment - direct buying intent: {has_direct_buying_intent}, conversion signal: {has_conversion_signal}, positive engagement: {recent_positive_engagement}, use case: {has_use_case}, business type: {has_business_type}")
            return True
        
        return False

    def _mark_information_provided(self, session):
        """Mark that helpful information has been provided to the user"""
        session["information_provided"] = True
        session["helpful_responses_count"] = session.get("helpful_responses_count", 0) + 1
        logger.info(f"[INFO_PROVIDED] Marked information as provided. Count: {session['helpful_responses_count']}")
    
    def _should_trigger_lead_collection(self, question, session):
        """Determine if lead collection should be triggered"""
        # Always trigger for direct buying intent
        if detect_buying_intent(question):
            return True
        
        # Trigger if information has been provided and user shows interest
        if session.get("information_provided", False) and session.get("helpful_responses_count", 0) >= 1:
            # Check for interest signals
            interest_signals = [
                "זה נשמע", "זה מעניין", "זה טוב", "זה מושלם", "זה בדיוק",
                "sounds good", "interesting", "perfect", "exactly what"
            ]
            question_lower = question.lower()
            if any(signal in question_lower for signal in interest_signals):
                return True
        
        return False
    
    def _generate_lead_transition_message(self, session, lang="he"):
        """Generate a smooth transition message to lead collection based on context"""
        use_case = session.get("specific_use_case")
        business_type = session.get("business_type_detected", False)
        
        if lang == "he":
            if use_case == "education":
                return "נשמע שזה בדיוק מה שאתה צריך! רוצה שנתחיל להקים את הבוט לבית הספר שלך? אשמח לקבל את הפרטים שלך כדי שנוכל להתחיל."
            elif use_case == "restaurant":
                return "זה נשמע כמו פתרון מושלם למסעדה שלך! רוצה שנתחיל להקים את הבוט? אשמח לקבל את הפרטים שלך כדי שנוכל להתחיל."
            elif use_case == "recruitment":
                return "זה בדיוק מה שיעזור לך עם הגיוס! רוצה שנתחיל להקים את הבוט? אשמח לקבל את הפרטים שלך."
            elif business_type:
                return "נשמע שזה בדיוק מה שהעסק שלך צריך! רוצה שנתחיל להקים את הבוט? אשמח לקבל את הפרטים שלך."
            else:
                return "נשמע שזה בדיוק מה שאתה צריך! רוצה שנתחיל להקים את הבוט? אשמח לקבל את הפרטים שלך."
        else:
            if use_case == "education":
                return "This sounds exactly like what you need! Want to start setting up the bot for your school? I'd love to get your details so we can get started."
            elif use_case == "restaurant":
                return "This sounds like the perfect solution for your restaurant! Want to start setting up the bot? I'd love to get your details so we can get started."
            elif use_case == "recruitment":
                return "This is exactly what will help with your recruitment! Want to start setting up the bot? I'd love to get your details."
            elif business_type:
                return "This sounds exactly like what your business needs! Want to start setting up the bot? I'd love to get your details."
            else:
                return "This sounds exactly like what you need! Want to start setting up the bot? I'd love to get your details."

    # Note: Response variation and deduplication are handled by the existing
    # ResponseVariationService which is already working properly