# 🔄 OFFICIAL ATARIZE CHATBOT SERVICE LOGIC REFERENCE
## Date: 2025-08-07 09:25:00
## Status: OFFICIAL REFERENCE - Use for all bot-related improvements

---

## **🎯 CORE PRINCIPLE**
**GPT-FIRST → CONTEXT-FALLBACK → ENHANCED-RESPONSE**

The Atarize bot prioritizes natural, fast responses by trying GPT first without context, only retrieving from Chroma when the initial response is insufficient.

---

## **🔄 STEP-BY-STEP SERVICE LOOP**

### **1. User Input**
- New question arrives (via API or Web)
- **SAVED** to `session["history"]` as `{"role": "user"}`

### **2. Intent Detection**
- Bot tries to detect intent
- If detected → used to guide targeted retrieval later
- **NO immediate context retrieval**

### **3. ⚡ Immediate GPT Response (NO context)**
- Tries to respond using **ONLY**:
  - `system_prompt`
  - `session["history"]`
- **❌ NO Chroma context used yet**
- **🎯 GOAL:** Fast, natural responses when possible

### **4. 🔍 Evaluate Response Quality**
- **If response is good** → send it to the user ✅
- **If vague or insufficient** → move to next step ⬇️

### **5. 📚 Context Retrieval from Chroma**
- **ONLY triggered when GPT response is vague**
- Based on detected intent (if any)
- If not enough → fallback to semantic search
- **🔧 FUTURE:** Combine both strategies (intent + semantic)

### **6. 🔧 Build New Context**
- Extract relevant docs
- Combine with session history
- Prepare enhanced context

### **7. ⚡ Second GPT Call (with full context)**
- Now includes:
  - Context from Chroma
  - Session history
  - System prompt
- **More complete response generated**

### **8. 💾 Save Assistant Reply**
- Final answer is saved to `session["history"]`

### **9. 🎯 Lead Detection**
- If user shows interest → ask for name, email, phone
- Lead details sent to business owner

### **10. 📊 Metrics & Monitoring**
- Token usage tracking
- Conversation logs stored in DB
- Lead alerts sent via email/webhook

---

## **🚫 CRITICAL VIOLATIONS TO AVOID**

### **❌ Auto-Generated/Templated Replies**
- **NO hardcoded pricing explanations**
- **NO templated feature lists**
- **NO automatic responses that skip GPT**

### **❌ Context Retrieval Too Early**
- **NEVER** retrieve Chroma context before trying GPT first
- **NEVER** auto-trigger context on every message

### **❌ Breaking Natural Flow**
- **NO** responses that feel robotic or templated
- **NO** immediate jumps to lead collection
- **NO** skipping the vague response evaluation

---

## **✅ COMPLIANCE CHECKLIST**

### **For chat_service.py:**
- [ ] GPT called first without context
- [ ] Context retrieval only after vague response detection
- [ ] No hardcoded responses for pricing/features
- [ ] Proper session history management

### **For response_variation_service.py:**
- [ ] No auto-generated templated content
- [ ] Variations preserve natural flow
- [ ] No hardcoded business information

### **For intent_service.py:**
- [ ] Intent detection doesn't trigger immediate responses
- [ ] Intent used only for guiding context retrieval

### **For email_service.py:**
- [ ] Lead collection follows natural conversation flow
- [ ] No automatic triggers that bypass user engagement

---

## **🎯 IMPLEMENTATION PRIORITIES**

1. **PRESERVE GPT-FIRST APPROACH**
   - Always try GPT without context first
   - Only use Chroma when needed

2. **MAINTAIN NATURAL FLOW**
   - Responses should feel conversational
   - Avoid robotic or templated language

3. **OPTIMIZE CONTEXT RETRIEVAL**
   - Intent + semantic combination
   - Only when GPT response is insufficient

4. **ENHANCE USER EXPERIENCE**
   - Fast responses when possible
   - Rich context when needed
   - Natural lead collection flow

---

## **📋 REFERENCE FOR FUTURE DEVELOPMENT**

**This document should be referenced for:**
- All chat_service.py modifications
- Response generation logic updates
- Context retrieval implementations
- Lead collection flow improvements
- Any bot behavior changes

**❗ CRITICAL:** Any deviation from this flow must be explicitly justified and documented.

---

**🔄 This is the OFFICIAL service logic - maintain this flow for optimal user experience!**