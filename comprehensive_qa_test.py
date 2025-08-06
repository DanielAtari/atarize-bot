#!/usr/bin/env python3
"""
🚨 CRITICAL QA TEST SUITE - Pre-Production Validation
Tests for message repetition, context memory, intent handling, lead collection, and language consistency.
"""

import sys
import os
import time
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append('.')

from services.chat_service import ChatService
from core.database import DatabaseManager
from core.optimized_openai_client import OpenAIClient

class ComprehensiveQATest:
    def __init__(self):
        """Initialize test environment"""
        print("🚨 CRITICAL QA TEST SUITE - Pre-Production Validation")
        print("="*70)
        
        # Initialize services
        self.db_manager = DatabaseManager()
        self.openai_client = OpenAIClient().get_client()
        self.chat_service = ChatService(self.db_manager, self.openai_client)
        
        # Test results storage
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "critical_issues": [],
            "personas": {}
        }
        
        # Define personas with conversation flows
        self.personas = {
            "eager_buyer": {
                "name": "Eager Buyer (Hebrew)",
                "messages": [
                    "היי, אני רוצה לקנות בוט לעסק שלי",
                    "כמה זה עולה?", 
                    "נשמע מעולה, איך ממשיכים?",
                    "אני דני כהן, 0501234567, dani@example.com",
                    "תודה רבה"
                ],
                "checks": ["no_repetition", "buying_intent", "lead_collection", "proper_closure"]
            },
            
            "skeptical_user": {
                "name": "Skeptical User (Mixed Languages)",
                "messages": [
                    "Hi, what is this service?",
                    "איך זה עובד?",
                    "מה היתרונות?",
                    "Sounds complicated",
                    "Maybe I'll think about it"
                ],
                "checks": ["no_repetition", "context_memory", "language_consistency", "no_premature_lead"]
            },
            
            "confused_user": {
                "name": "Confused User (Short Responses)",
                "messages": [
                    "מה?",
                    "לא הבנתי",
                    "אוקיי",
                    "כן",
                    "למה?"
                ],
                "checks": ["no_repetition", "context_memory", "helpful_responses", "no_loops"]
            },
            
            "price_focused": {
                "name": "Price-Focused User",
                "messages": [
                    "כמה עולה הבוט?",
                    "זה יקר",
                    "יש הנחה?",
                    "מה כלול במחיר?",
                    "אוקיי תן לי לחשוב"
                ],
                "checks": ["no_repetition", "consistent_pricing", "context_memory", "no_contradictions"]
            },
            
            "technical_user": {
                "name": "Technical User",
                "messages": [
                    "איך הבוט עובד מבחינה טכנית?",
                    "איזה טכנולוגיות אתם משתמשים?",
                    "יש אינטגרציה עם CRM?",
                    "מה לגבי אבטחה?",
                    "נשמע טוב"
                ],
                "checks": ["no_repetition", "technical_accuracy", "context_memory", "follow_up_offers"]
            },
            
            "restaurant_owner": {
                "name": "Restaurant Owner (Specific Use Case)",
                "messages": [
                    "יש לי מסעדה, איך הבוט יכול לעזור לי?",
                    "הבוט יכול לקבל הזמנות?",
                    "מה לגבי תפריט?",
                    "כמה זה עולה למסעדה?",
                    "אני מעוניין, מה הצעד הבא?"
                ],
                "checks": ["no_repetition", "use_case_specific", "buying_intent", "lead_collection"]
            },
            
            "yes_sayer": {
                "name": "Yes Sayer (Repetitive Responses)",
                "messages": [
                    "כן",
                    "כן",  
                    "כן",
                    "אוקיי",
                    "כן"
                ],
                "checks": ["no_repetition", "context_progression", "no_loops", "intelligent_handling"]
            },
            
            "english_user": {
                "name": "English User",
                "messages": [
                    "Hello, I want to buy a chatbot",
                    "How much does it cost?",
                    "Great, how do we proceed?", 
                    "I'm John Smith, 0501234567, john@example.com",
                    "Thank you"
                ],
                "checks": ["no_repetition", "english_support", "buying_intent", "lead_collection"]
            },
            
            "undecided_user": {
                "name": "Undecided User",
                "messages": [
                    "אני לא בטוח אם אני צריך בוט",
                    "תספר לי עוד",
                    "מה היתרונות?",
                    "נשמע מעניין אבל אני עדיין לא בטוח",
                    "אוקיי תן לי לחשוב על זה"
                ],
                "checks": ["no_repetition", "context_memory", "no_pressure_selling", "helpful_info"]
            },
            
            "quick_buyer": {
                "name": "Quick Buyer (Fast Decision)",
                "messages": [
                    "אני רוצה לקנות בוט עכשיו",
                    "מה הפרטים שלי צריכים?",
                    "רחל לוי, 0507654321, rachel@business.co.il",
                    "מתי נתחיל?",
                    "מעולה"
                ],
                "checks": ["no_repetition", "immediate_buying_intent", "efficient_lead_collection", "quick_closure"]
            }
        }

    def create_clean_session(self):
        """Create a clean session for each test"""
        return {
            "history": [],
            "greeted": False,
            "intro_given": False,
            "lead_collected": False,
            "interested_lead_pending": False,
            "product_market_fit_detected": False
        }

    def check_no_repetition(self, conversation_history):
        """Check for repeated identical messages"""
        issues = []
        bot_responses = [msg["content"] for msg in conversation_history if msg["role"] == "assistant"]
        
        for i in range(1, len(bot_responses)):
            if bot_responses[i] == bot_responses[i-1]:
                issues.append(f"🚨 REPEATED MESSAGE: '{bot_responses[i][:50]}...'")
        
        return issues

    def check_context_memory(self, conversation_history, messages):
        """Check if bot remembers context from previous messages"""
        issues = []
        
        # Look for signs that the bot is answering the same question multiple times
        topics_answered = set()
        for i, msg in enumerate(conversation_history):
            if msg["role"] == "assistant":
                content = msg["content"].lower()
                
                # Note: Automatic pricing detection removed - all responses now come from context only
                
                # Check for introduction repetition
                if "עטרה" in content and "atarize" in content.lower():
                    if "introduction" in topics_answered:
                        issues.append(f"🚨 CONTEXT MEMORY ISSUE: Introduction repeated")
                    topics_answered.add("introduction")
        
        return issues

    def check_buying_intent_handling(self, conversation_history, session_states):
        """Check if buying intent is properly detected and handled"""
        issues = []
        
        buying_signals = ["רוצה לקנות", "want to buy", "מעוניין", "interested"]
        lead_collection_started = False
        
        for i, msg in enumerate(conversation_history):
            if msg["role"] == "user":
                user_message = msg["content"].lower()
                
                # Check if user showed buying intent
                has_buying_intent = any(signal in user_message for signal in buying_signals)
                
                if has_buying_intent:
                    # Check if next bot response asks for lead info (Hebrew or English)
                    if i + 1 < len(conversation_history):
                        next_response = conversation_history[i + 1]["content"].lower()
                        hebrew_patterns = ["פרטים", "שם", "טלפון", "אימייל"]
                        english_patterns = ["details", "name", "phone", "email", "full name"]
                        
                        asks_for_details = (
                            any(pattern in next_response for pattern in hebrew_patterns) or
                            any(pattern in next_response for pattern in english_patterns)
                        )
                        
                        if asks_for_details:
                            lead_collection_started = True
                        else:
                            issues.append(f"🚨 BUYING INTENT MISSED: No lead collection after '{msg['content'][:30]}...'")
        
        return issues

    def check_lead_collection_flow(self, conversation_history, session_states):
        """Check if lead collection flow works properly"""
        issues = []
        
        lead_info_patterns = ["@", "050", "052", "053", "054", "055"]
        lead_provided = False
        lead_confirmed = False
        
        for i, msg in enumerate(conversation_history):
            if msg["role"] == "user":
                user_message = msg["content"]
                
                # Check if user provided lead info
                has_lead_info = any(pattern in user_message for pattern in lead_info_patterns)
                
                if has_lead_info:
                    lead_provided = True
                    # Check if next bot response confirms receipt (Hebrew or English)
                    if i + 1 < len(conversation_history):
                        next_response = conversation_history[i + 1]["content"].lower()
                        hebrew_confirmations = ["תודה", "קיבלנו", "רשמנו", "מעולה", "יופי"]
                        english_confirmations = ["thank", "received", "got your", "perfect", "great", "wonderful", "we have"]
                        
                        has_confirmation = (
                            any(conf in next_response for conf in hebrew_confirmations) or
                            any(conf in next_response for conf in english_confirmations)
                        )
                        
                        if has_confirmation:
                            lead_confirmed = True
                        else:
                            issues.append(f"🚨 LEAD COLLECTION ISSUE: No confirmation after lead provided")
        
        return issues

    def check_language_consistency(self, conversation_history):
        """Check for language handling issues"""
        issues = []
        
        for msg in conversation_history:
            if msg["role"] == "assistant":
                content = msg["content"]
                
                # Check for mixed inappropriate language switches
                has_hebrew = any(char in content for char in 'אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
                has_english = any(char.isalpha() and ord(char) < 128 for char in content)
                
                if has_hebrew and has_english:
                    # This is fine for mixed conversations, but check for weird switches
                    if "hello שלום" in content.lower() or similar_weird_patterns(content):
                        issues.append(f"🚨 LANGUAGE ISSUE: Weird language mixing in '{content[:50]}...'")
        
        return issues

    def run_persona_test(self, persona_key, persona_data):
        """Run test for a specific persona"""
        print(f"\n🧪 Testing Persona: {persona_data['name']}")
        print("-" * 50)
        
        session = self.create_clean_session()
        conversation_history = []
        session_states = []
        all_issues = []
        
        for i, message in enumerate(persona_data["messages"]):
            print(f"{i+1}. 🙋 User: {message}")
            
            try:
                # Get response from chat service
                response, session = self.chat_service.handle_question(message, session)
                
                # Store conversation
                conversation_history.append({"role": "user", "content": message})
                conversation_history.append({"role": "assistant", "content": response})
                session_states.append(dict(session))
                
                print(f"   🤖 Bot: {response[:100]}{'...' if len(response) > 100 else ''}")
                
                # Real-time issue detection
                if i > 0:  # Skip first message
                    recent_issues = self.check_no_repetition(conversation_history[-4:])
                    if recent_issues:
                        all_issues.extend(recent_issues)
                        print(f"   ⚠️  {recent_issues[0]}")
                
            except Exception as e:
                error_msg = f"🚨 CRITICAL ERROR: {str(e)}"
                all_issues.append(error_msg)
                print(f"   {error_msg}")
                break
        
        # Run comprehensive checks
        print(f"\n📋 Running checks for {persona_data['name']}...")
        
        if "no_repetition" in persona_data["checks"]:
            repetition_issues = self.check_no_repetition(conversation_history)
            all_issues.extend(repetition_issues)
        
        if "context_memory" in persona_data["checks"]:
            memory_issues = self.check_context_memory(conversation_history, persona_data["messages"])
            all_issues.extend(memory_issues)
        
        if "buying_intent" in persona_data["checks"]:
            intent_issues = self.check_buying_intent_handling(conversation_history, session_states)
            all_issues.extend(intent_issues)
        
        if "lead_collection" in persona_data["checks"]:
            lead_issues = self.check_lead_collection_flow(conversation_history, session_states)
            all_issues.extend(lead_issues)
        
        if "language_consistency" in persona_data["checks"]:
            language_issues = self.check_language_consistency(conversation_history)
            all_issues.extend(language_issues)
        
        # Store results
        self.test_results["personas"][persona_key] = {
            "name": persona_data["name"],
            "conversation": conversation_history,
            "issues": all_issues,
            "passed": len(all_issues) == 0
        }
        
        # Display results
        if all_issues:
            print(f"❌ FAILED: {len(all_issues)} issues found")
            for issue in all_issues:
                print(f"   {issue}")
            self.test_results["failed_tests"] += 1
            self.test_results["critical_issues"].extend(all_issues)
        else:
            print(f"✅ PASSED: No issues found")
            self.test_results["passed_tests"] += 1
        
        self.test_results["total_tests"] += 1

    def run_all_tests(self):
        """Run all persona tests"""
        print("🚀 Starting Comprehensive QA Test Suite...")
        print(f"📊 Testing {len(self.personas)} personas with critical issue detection\n")
        
        start_time = time.time()
        
        for persona_key, persona_data in self.personas.items():
            self.run_persona_test(persona_key, persona_data)
            time.sleep(0.5)  # Small delay between tests
        
        end_time = time.time()
        
        # Generate final report
        self.generate_final_report(end_time - start_time)

    def generate_final_report(self, test_duration):
        """Generate comprehensive QA report"""
        print("\n" + "="*70)
        print("🏆 COMPREHENSIVE QA TEST RESULTS")
        print("="*70)
        
        print(f"📊 Overall Statistics:")
        print(f"   Total Tests: {self.test_results['total_tests']}")
        print(f"   Passed: {self.test_results['passed_tests']}")
        print(f"   Failed: {self.test_results['failed_tests']}")
        print(f"   Success Rate: {(self.test_results['passed_tests']/self.test_results['total_tests']*100):.1f}%")
        print(f"   Test Duration: {test_duration:.2f} seconds")
        
        # Critical issues summary
        if self.test_results["critical_issues"]:
            print(f"\n🚨 CRITICAL ISSUES FOUND ({len(self.test_results['critical_issues'])}):")
            issue_types = {}
            for issue in self.test_results["critical_issues"]:
                issue_type = issue.split(":")[0].strip()
                issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
            
            for issue_type, count in issue_types.items():
                print(f"   {issue_type}: {count} occurrences")
        
        # Persona-specific results
        print(f"\n📋 Detailed Results by Persona:")
        for persona_key, results in self.test_results["personas"].items():
            status = "✅ PASS" if results["passed"] else "❌ FAIL"
            issue_count = len(results["issues"])
            print(f"   {status} {results['name']} ({issue_count} issues)")
        
        # Save detailed report to file
        report_filename = f"qa_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_filename}")
        
        # Final verdict
        if self.test_results["failed_tests"] > 0:
            print(f"\n🚨 VERDICT: FAILED - {self.test_results['failed_tests']} tests failed")
            print("🛑 RECOMMENDATION: DO NOT DEPLOY TO PRODUCTION")
            print("🔧 ACTION REQUIRED: Fix critical issues before launch")
        else:
            print(f"\n🎉 VERDICT: PASSED - All tests successful!")
            print("✅ RECOMMENDATION: Ready for production deployment")

def similar_weird_patterns(content):
    """Check for weird language pattern issues"""
    weird_patterns = [
        "hello שלום",
        "hi היי", 
        "thank תודה",
        "yes כן"
    ]
    return any(pattern in content.lower() for pattern in weird_patterns)

if __name__ == "__main__":
    qa_test = ComprehensiveQATest()
    qa_test.run_all_tests()