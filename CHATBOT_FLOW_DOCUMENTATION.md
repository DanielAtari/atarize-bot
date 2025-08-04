# 🤖 Atarize Chatbot: Complete Flow Documentation

## 📋 Overview
This document explains how the Atarize chatbot processes user messages from start to finish, including all logic paths, data sources, and decision points.

---

## 🔄 Main Flow: From User Message to GPT Response

### **Step 1: Initialization & Session Management**
**Location:** `handle_question()` - Lines 1293-1343

```python
def handle_question(question, session, collection, system_prompt, client, intents):
```

**What happens:**
1. **Initialize session keys** if they don't exist:
   - `session["history"]` - Conversation history
   - `session["greeted"]` - First-time greeting flag
   - `session["intro_given"]` - Introduction given flag

2. **Debug session state** - Log current session status for troubleshooting

3. **Context enrichment detection** (NO early returns):
   - Detect if this is a first greeting or repeat greeting
   - Store greeting context for later GPT enrichment
   - **Key change:** No longer returns hardcoded responses

4. **Update conversation history:**
   - Add user message to `session["history"]`
   - Filter history to ensure valid message format
   - History provides conversation context to GPT

---

### **Step 2: Lead Collection Flow** 
**Location:** Lines 1344-1442

**Priority:** This runs BEFORE intent detection

**Logic:**
- **If `session["interested_lead_pending"]` is True:**
  1. Check for greetings → Reset lead mode, provide intro
  2. Check for exit phrases (e.g., "די", "עזוב") → Reset lead mode  
  3. Check if user provided contact details → Send email, reset lead mode
  4. **NEW:** If conversation history exists → Continue to GPT instead of demanding contact details
  5. After 2 failed attempts → Reset lead mode automatically

**Data Sources:**
- Session state: `interested_lead_pending`, `lead_request_count`
- Detection functions: `is_greeting()`, `detect_lead_info()`
- Exit phrase patterns with regex word boundaries

---

### **Step 3: Context Detection for Follow-ups**
**Location:** Lines 1490-1525

**Purpose:** Handle follow-up questions based on conversation history

**Logic:**
1. **Call `detect_follow_up_context()`** to analyze if this is a follow-up
2. **If contextual intent found:**
   - Override normal intent detection
   - Use context-based intent (e.g., "whatsapp_meta_verification")
   - Store context info for prompt enhancement

**Data Sources:**
- Session history analysis
- Pre-defined topic patterns
- Context bridge logic

---

### **Step 4: Intent Detection System**
**Location:** Lines 1526-1590

**Multi-layered approach with priority resolution:**

#### **4a. Chroma Intent Detection (Semantic)**
```python
chroma_intent_result = chroma_detect_intent(question, threshold=Config.CHROMA_THRESHOLD)
```
- **Input:** User question text
- **Process:** Generate embedding → Query `atarize_intents` collection
- **Threshold:** 1.4 (lower = more similar)
- **Output:** `(intent_name, metadata)` or `None`

#### **4b. Fuzzy Intent Detection (Text Matching)**
```python
fuzzy_intent_result = detect_intent(question, intents, threshold=Config.FUZZY_THRESHOLD)
```
- **Input:** User question text  
- **Process:** Compare against trigger phrases using `rapidfuzz`
- **Threshold:** 70% similarity
- **Output:** `{'intent': name, 'confidence': score}` or `None`

#### **4c. Priority Resolution Logic:**
1. **Priority 1:** Strong fuzzy match (not "faq") → Use fuzzy
2. **Priority 2:** Chroma match found → Use Chroma  
3. **Priority 3:** Any fuzzy match (including "faq") → Use fuzzy
4. **Priority 4:** Hybrid Chroma with relaxed threshold (1.8) → Try again

#### **4d. Fallback for No Intent:**
- If no intent detected → Call `handle_intent_failure()`
- Uses smart fallback system with multiple retrieval layers

---

### **Step 5: Knowledge Retrieval**
**Location:** Lines 1600-1627

**Multi-layered retrieval system:**

#### **5a. Enhanced Context Retrieval**
```python
knowledge_docs = get_enhanced_context_with_fallbacks(question, intent_name, lang, collection)
```

**Fallback Layers:**
1. **Layer 1:** Intent-specific retrieval (filtered by intent + language)
2. **Layer 2:** Language-filtered retrieval (no intent filter)
3. **Layer 3:** Broad search with post-filtering by language

#### **5b. Few-shot Examples Retrieval**
```python
examples = get_examples_by_intent(intent_name, n_examples=3)
```
- Retrieves 3 example responses for the detected intent
- Used to guide GPT's tone and structure
- Falls back gracefully if examples unavailable

**Data Sources:**
- **ChromaDB `atarize_knowledge` collection** - Main business knowledge
- **ChromaDB `atarize_intents` collection** - Intent definitions  
- **Language detection** - Hebrew/English routing
- **Intent metadata** - Category, confidence, source

---

### **Step 6: Context Building & Enrichment**
**Location:** Lines 1628-1690

**Creates rich context for GPT:**

#### **6a. Base Context Assembly**
```python
context = "\n---\n".join(doc for doc, meta in knowledge_docs if doc)
```

#### **6b. Enriched Context Signals**
```python
enriched_signals = build_enriched_context(question, session, greeting_context)
```

**Enrichment Sources:**
- **Greeting context:** First greeting vs. repeat greeting
- **Use case context:** `session["specific_use_case"]` (e.g., "restaurant")
- **Follow-up context:** `session["follow_up_context"]` (e.g., "technology")
- **Engagement signals:** `session["positive_engagement"]`
- **Conversion opportunities:** `session["conversion_opportunity"]`
- **Lead collection state:** `session["interested_lead_pending"]`

#### **6c. Conversational Enhancement**
```python
conversational_enhancement = get_conversational_enhancement(question, intent_name)
```
- Intent-specific instructions for GPT
- Guides response style and follow-up questions

#### **6d. Contextual Bridge** 
- Links follow-up questions to previous conversation context
- Adds topic-specific guidance for complex multi-turn conversations

---

### **Step 7: Token Management & Prompt Building**
**Location:** Lines 1651-1690

**Smart token management to prevent API errors:**

#### **7a. Token Counting**
```python
base_tokens = count_tokens(base_messages)
```
- Uses `tiktoken` to count tokens accurately
- Monitors against model limits (GPT-4 Turbo: 128K tokens)

#### **7b. Dynamic Prompt Construction**
- **If tokens allow:** Include examples + context + enriched signals
- **If approaching limit:** Skip examples, keep core context
- **If still too long:** Truncate context intelligently

#### **7c. Final Prompt Structure**
```
{system_prompt}

{examples_block}  // If space allows

הקשר רלוונטי מתוך מסמכי העסק:
{enhanced_context}

{conversational_enhancement}

{enriched_signals}  // NEW: Context enrichment

שאלה של המשתמש:
{question}

ענה בצורה טבעית וידידותית...
```

---

### **Step 8: GPT Call & Response Generation**
**Location:** Lines 1691-1730

#### **8a. GPT-4 Turbo Call**
```python
completion = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[{"role": "system", "content": context_prompt}] + filtered_history
)
```

**Input to GPT:**
- **System prompt** with business knowledge and context
- **Conversation history** (filtered for valid messages)
- **Current user question** (already in history)

#### **8b. Response Processing**
- Extract response from GPT completion
- Log response time and token usage
- Store actual token consumption for monitoring

#### **8c. Error Handling**
- Graceful fallback if GPT fails
- Different handling for greetings vs. regular questions
- Prevents lead collection for social interactions

---

### **Step 9: Answer Validation & Final Processing**
**Location:** Lines 1761-1812

#### **9a. Vagueness Detection**
```python
if is_vague_gpt_answer(answer):
```

**NEW GPT-First Approach:**
- **Old:** Vague answer → Return hardcoded response
- **New:** Vague answer → Collect more context signals, continue to success

#### **9b. Context Signal Collection** 
When answer is vague, collect additional signals for future conversations:
- Use case detection → Update session
- Follow-up context → Update session  
- Positive engagement → Update session

#### **9c. Success Path Decision**
- **If conversation history exists:** Treat as successful (continue conversation)
- **If greeting/small talk:** Treat as successful
- **Only new conversations with no context:** Activate lead collection

---

### **Step 10: Response Delivery**
**Location:** Lines 1796-1812

#### **10a. Session Updates**
```python
session["history"].append({"role": "assistant", "content": answer})
```

#### **10b. Performance Monitoring**
- Log total request time
- Warn if response > 3 seconds
- Track slow requests for optimization

#### **10c. Return to Frontend**
```python
return answer, session
```

---

## 🎯 Decision Path Priority Order

### **1. Lead Collection (Highest Priority)**
- Overrides everything if `interested_lead_pending = True`
- **Exception:** Now continues to GPT if conversation history exists

### **2. Context-Based Intent (High Priority)**  
- Follow-up questions get contextual intent
- Skips normal intent detection

### **3. Intent Detection (Normal Priority)**
- Chroma (semantic) + Fuzzy (text) with priority resolution
- Multiple fallback layers

### **4. Knowledge Retrieval (Normal Priority)**
- Multi-layer fallback system
- Language-aware filtering

### **5. GPT Processing (Always Executed)**
- **NEW:** All paths lead to GPT with enriched context
- No more hardcoded response hijacking

---

## 📊 Data Sources & Their Usage

### **ChromaDB Collections:**
1. **`atarize_knowledge`** - Business content for answers
2. **`atarize_intents`** - Intent definitions for classification

### **Session State:**
- **`history`** - Full conversation context
- **`greeted`** - Welcome state
- **`interested_lead_pending`** - Lead collection mode
- **`specific_use_case`** - Business context (restaurant, retail, etc.)
- **`follow_up_context`** - Topic being discussed
- **`conversion_opportunity`** - Sales opportunity flag

### **Configuration:**
- **`Config.CHROMA_THRESHOLD`** - 1.4 (semantic similarity)
- **`Config.FUZZY_THRESHOLD`** - 70 (text similarity percentage)
- **`Config.MAX_PROMPT_TOKENS`** - 100,000 (token management)

### **External APIs:**
- **OpenAI GPT-4 Turbo** - Main response generation
- **OpenAI Embeddings** - `text-embedding-3-large` for semantic search
- **Email SMTP** - Lead notification system

---

## 🔄 How GPT "Drives" the Conversation

### **Context Awareness:**
GPT receives full conversation context including:
- Previous messages (history)
- Business knowledge (ChromaDB docs)
- User context signals (greeting, use case, engagement)
- Intent-specific guidance (conversational enhancement)

### **Dynamic Response Generation:**
- **Personalized:** Based on business type, use case
- **Contextual:** Considers conversation flow and follow-ups  
- **Guided:** Intent-specific instructions shape response style
- **Informed:** Real business knowledge prevents hallucination

### **Conversation Navigation:**
- **Follow-up questions:** GPT generates relevant next questions
- **Topic transitions:** Smoothly moves between subjects based on context
- **Lead qualification:** Naturally guides toward business opportunities
- **Fallback handling:** Gracefully handles unknowns without breaking flow

---

## ✅ Key Improvements in Current Flow

### **1. GPT-First Approach**
- **Before:** Early exits with hardcoded responses
- **After:** All inputs processed by GPT with enriched context

### **2. Context Enrichment System**
- **Before:** Binary detection → Hardcoded response
- **After:** Soft signals → GPT context enhancement

### **3. Intelligent Fallbacks**
- **Before:** Single retrieval attempt
- **After:** Multi-layer retrieval with graceful degradation

### **4. Conversation Continuity**
- **Before:** Lead mode hijacked ongoing conversations
- **After:** Lead collection only for new, contextless conversations

### **5. Smart Token Management**
- **Before:** No token monitoring
- **After:** Dynamic prompt optimization to prevent API errors

---

This flow ensures the bot handles conversations naturally while maintaining business intelligence and conversion opportunities through the GPT-first approach with rich context enrichment.