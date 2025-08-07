# 🛠️ CURSOR DEBUG INSTRUCTION: CHATBOT LOGIC REGRESSION

## Context:
After recent modifications, the chatbot lost logical consistency, resulting in vague or incorrect replies. It seems GPT is being used even when a direct Chroma result is preferred, session logic is messy, and lead detection gets overridden.

---

## 🚨 Issues Identified:

### 1. Over-reliance on GPT for known intents
- Questions like "how much does it cost" or "what are the features" are routed to GPT with enhanced context.
- But these answers **already exist** in Chroma and should be retrieved **directly**.

#### 🔧 Fix:
If the intent is one of these:
```python
HIGH_CONFIDENCE_INTENTS = ["pricing", "how_it_works", "features", "faq"]
```
Then retrieve directly from Chroma:
```python
context_docs = self._get_knowledge_by_intent(intent_name)
if context_docs:
    return context_docs[0][0], session
```
And **skip** GPT unless the context is missing.

---

### 2. Intent detection logic is inconsistent
- Some questions go through `detect_intent()`
- Others rely on hand-written `if` blocks like `_detect_specific_use_case()`

#### 🔧 Fix:
Call `detect_intent(question)` at the top of `handle_question` and store it as `intent_name`.
Use this to guide both:
- Retrieval from Chroma
- Lead logic or fallback

---

### 3. Session flags aren't cleaned properly
- `interested_lead_pending` may remain `True` across turns
- "Yes" from the user may trigger old logic and confuse context

#### 🔧 Fix:
After handling a lead or when a new intent is triggered:
```python
session.pop("interested_lead_pending", None)
session.pop("lead_request_count", None)
```

---

### 4. GPT is used even when vague or unstable
- If GPT replies with generic content, user gets no value

#### 🔧 Fix:
Use `is_vague_gpt_answer(answer)`
If True → fallback to Chroma + retry

---

## ✅ Desired Flow in `handle_question()`
1. Detect intent using `detect_intent(question)`
2. If intent is high-confidence → get Chroma
3. Else → use GPT
4. If vague → try fallback
5. After that → lead collection, variation, or default reply

Let me know if you want me to rewire the function myself.
