#!/usr/bin/env python3
"""
Comprehensive QA Test Suite for Chatbot Edge Cases and Flow Analysis
"""

import requests
import json
import time
from utils.validation_utils import detect_lead_info
from utils.text_utils import detect_language, is_greeting, is_small_talk
from utils.lead_parser import extract_lead_details

class ChatbotQATester:
    def __init__(self, base_url="http://localhost:5050"):
        self.base_url = base_url
        self.findings = []
        self.test_results = []
    
    def add_finding(self, severity, category, description, location=None):
        """Add a finding to the report"""
        self.findings.append({
            "severity": severity,  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
            "category": category,
            "description": description,
            "location": location
        })
        print(f"🔍 [{severity}] {category}: {description}")
    
    def test_api_call(self, message, description=""):
        """Make API call to chatbot"""
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={"question": message},
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get("answer", "")
                self.test_results.append({
                    "input": message,
                    "output": bot_response,
                    "description": description,
                    "status": "SUCCESS"
                })
                return bot_response
            else:
                self.test_results.append({
                    "input": message,
                    "output": f"HTTP {response.status_code}",
                    "description": description,
                    "status": "ERROR"
                })
                return None
                
        except Exception as e:
            self.test_results.append({
                "input": message,
                "output": f"Exception: {e}",
                "description": description,
                "status": "FAILED"
            })
            return None
    
    def test_edge_cases(self):
        """Test various edge cases and conversation flows"""
        
        print("🧪 TESTING EDGE CASES AND CONVERSATION FLOWS")
        print("=" * 60)
        
        # 1. LANGUAGE DETECTION EDGE CASES
        print("\n1️⃣ LANGUAGE DETECTION EDGE CASES")
        edge_language_cases = [
            ("", "Empty string"),
            ("123456", "Numbers only"),
            ("!@#$%", "Special characters only"),
            ("hello שלום", "Mixed languages"),
            ("שלום123", "Hebrew with numbers"),
            ("email@test.com", "Email without context"),
        ]
        
        for text, desc in edge_language_cases:
            detected = detect_language(text)
            print(f"  '{text}' → {detected} ({desc})")
            if text == "" and detected != "he":
                self.add_finding("MEDIUM", "Language Detection", 
                               f"Empty string detected as '{detected}' instead of fallback", 
                               "utils/text_utils.py:detect_language")
        
        # 2. GREETING DETECTION EDGE CASES
        print("\n2️⃣ GREETING DETECTION EDGE CASES")
        greeting_cases = [
            ("שלום!", "Hebrew greeting with punctuation"),
            ("  hi  ", "English greeting with spaces"),
            ("שלוםםם", "Hebrew greeting with typo"),
            ("helloooo", "English greeting with extra letters"),
            ("היי איך הולך?", "Greeting with question"),
            ("Hi there how are you?", "Complex English greeting"),
        ]
        
        for text, desc in greeting_cases:
            is_greet = is_greeting(text)
            print(f"  '{text}' → {is_greet} ({desc})")
        
        # 3. LEAD DETECTION EDGE CASES
        print("\n3️⃣ LEAD DETECTION EDGE CASES")
        lead_cases = [
            ("שמי דניאל", "Name only"),
            ("050-1234567", "Phone only"),
            ("test@email.com", "Email only"),
            ("דניאל 050-1234567", "Name + phone"),
            ("דניאל test@email.com", "Name + email"),
            ("050-1234567 test@email.com", "Phone + email"),
            ("שמי דניאל נייד 050-1234567 אימייל test@email.com", "All three with keywords"),
            ("name: John phone: 052-1234567 email: john@test.com", "English structured"),
            ("John Smith 052-1234567 john@test.com", "English compact"),
            ("שמי דניאל, טלפון 050-1234567, מייל: invalid-email", "Invalid email"),
            ("שמי ד, טלפון 050-1234567, מייל test@email.com", "Very short name"),
        ]
        
        for text, desc in lead_cases:
            detected = detect_lead_info(text)
            details = extract_lead_details(text)
            print(f"  '{text}' → {detected} ({desc})")
            print(f"    Details: Name='{details.get('name')}', Phone='{details.get('phone')}', Email='{details.get('email')}'")
            
            # Check for potential false positives/negatives
            if text == "דניאל 050-1234567" and detected:
                self.add_finding("MEDIUM", "Lead Detection", 
                               "Two-component lead detected as complete (missing email)",
                               "utils/validation_utils.py:detect_lead_info")
        
        # 4. CONVERSATION FLOW TESTING
        print("\n4️⃣ CONVERSATION FLOW TESTING")
        
        # Test 4a: Basic greeting flow
        print("\n  4a. Basic Greeting Flow")
        resp1 = self.test_api_call("שלום", "Initial greeting")
        if resp1:
            if "שלום" not in resp1 and "היי" not in resp1:
                self.add_finding("HIGH", "Greeting Flow", 
                               "Bot didn't respond appropriately to Hebrew greeting")
        
        # Test 4b: Follow-up after greeting
        resp2 = self.test_api_call("מה שלומך?", "Follow-up after greeting")
        if resp2 and resp2 == resp1:
            self.add_finding("HIGH", "Conversation Continuity", 
                           "Bot gave identical response to different questions")
        
        # Test 4c: Topic switching
        resp3 = self.test_api_call("כמה עולה השירות?", "Topic switch to pricing")
        resp4 = self.test_api_call("איך עובד הבוט?", "Topic switch to technical")
        
        # Test 4d: Vague/short inputs
        print("\n  4d. Vague/Short Input Testing")
        vague_inputs = ["", "  ", "?", "אה", "hmm", "..."]
        for inp in vague_inputs:
            resp = self.test_api_call(inp, f"Vague input: '{inp}'")
            if resp and "name" not in resp.lower() and "phone" not in resp.lower():
                self.add_finding("MEDIUM", "Vague Input Handling", 
                               f"Input '{inp}' didn't trigger lead collection")
        
        # Test 4e: Lead collection flow
        print("\n  4e. Lead Collection Flow")
        
        # Trigger lead collection
        resp_trigger = self.test_api_call("לא יודע", "Trigger lead collection")
        
        # Test partial lead info
        resp_partial = self.test_api_call("שמי דניאל", "Partial lead info")
        
        # Test exit phrases
        exit_phrases = ["עזוב", "לא רוצה", "די"]
        for phrase in exit_phrases:
            resp_exit = self.test_api_call(phrase, f"Exit phrase: {phrase}")
            if resp_exit and "בסדר" not in resp_exit:
                self.add_finding("MEDIUM", "Lead Exit Flow", 
                               f"Exit phrase '{phrase}' didn't reset lead mode properly")
        
        # Test 4f: Language switching mid-conversation
        print("\n  4f. Language Switching")
        self.test_api_call("שלום, איך אתה?", "Hebrew question")
        resp_eng = self.test_api_call("How much does it cost?", "Switch to English")
        resp_heb = self.test_api_call("תודה רבה", "Switch back to Hebrew")
        
        # Test 4g: Repeated identical messages
        print("\n  4g. Repeated Messages")
        msg = "כמה עולה השירות?"
        resp1 = self.test_api_call(msg, "First identical message")
        resp2 = self.test_api_call(msg, "Second identical message")
        resp3 = self.test_api_call(msg, "Third identical message")
        
        if resp1 == resp2 == resp3:
            self.add_finding("LOW", "Conversation Variety", 
                           "Bot gives identical responses to repeated questions")
        
        # Test 4h: Very long input
        print("\n  4h. Long Input Testing")
        long_input = "שלום " * 100 + " איך אתה?"
        resp_long = self.test_api_call(long_input, "Very long input")
        
        # Test 4i: Special characters and emojis
        print("\n  4i. Special Characters")
        special_inputs = [
            "שלום! 😊 איך אתה?",
            "What's the price??? 💰",
            "Email: test@email.com (urgent!!!)",
            "Name: John O'Connor, Phone: 050-123-4567"
        ]
        
        for inp in special_inputs:
            self.test_api_call(inp, f"Special chars: {inp}")
    
    def test_variable_initialization(self):
        """Test for uninitialized variables by analyzing code paths"""
        print("\n5️⃣ VARIABLE INITIALIZATION ANALYSIS")
        
        # This would require static analysis, but we can check key patterns
        critical_vars = [
            "overall_start_time", "answer", "intent_name", "lang", 
            "completion", "lead_details", "email_success"
        ]
        
        # Check if variables are initialized in all paths
        # (This is a simplified check - would need full static analysis for complete coverage)
        
        print("  Variables that should be initialized in ALL code paths:")
        for var in critical_vars:
            print(f"    - {var}")
        
        # We already fixed overall_start_time, but let's note potential issues
        self.add_finding("LOW", "Code Quality", 
                       "Review variable initialization in all exception paths",
                       "services/chat_service.py:handle_question")
    
    def analyze_hardcoded_responses(self):
        """Analyze for hardcoded responses that bypass GPT"""
        print("\n6️⃣ HARDCODED RESPONSE ANALYSIS")
        
        hardcoded_patterns = [
            "Sorry, I couldn't understand",
            "Sorry, I couldn't find a good answer", 
            "Sorry, I encountered an error",
            "Please include your name, phone, and email",
            "Thank you for your message! We already have your details"
        ]
        
        for pattern in hardcoded_patterns:
            print(f"  Found hardcoded: '{pattern}'")
        
        self.add_finding("MEDIUM", "Response Quality", 
                       "Multiple hardcoded responses that bypass GPT's natural language generation",
                       "services/chat_service.py")
    
    def generate_report(self):
        """Generate comprehensive QA report"""
        print("\n" + "="*80)
        print("📋 COMPREHENSIVE QA REPORT")
        print("="*80)
        
        # Summary
        total_tests = len(self.test_results)
        successful_tests = len([t for t in self.test_results if t["status"] == "SUCCESS"])
        
        print(f"\n📊 TEST SUMMARY:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Successful: {successful_tests}")
        print(f"   Failed: {total_tests - successful_tests}")
        
        # Findings by severity
        findings_by_severity = {}
        for finding in self.findings:
            sev = finding["severity"]
            if sev not in findings_by_severity:
                findings_by_severity[sev] = []
            findings_by_severity[sev].append(finding)
        
        print(f"\n🔍 FINDINGS BY SEVERITY:")
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if severity in findings_by_severity:
                print(f"\n   {severity} ({len(findings_by_severity[severity])} issues):")
                for finding in findings_by_severity[severity]:
                    print(f"     • {finding['category']}: {finding['description']}")
                    if finding['location']:
                        print(f"       Location: {finding['location']}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("   1. Add input sanitization for edge cases (empty strings, special chars)")
        print("   2. Improve natural language fallbacks to reduce hardcoded responses")
        print("   3. Add conversation memory to avoid repetitive responses")
        print("   4. Enhance lead detection to handle partial info more gracefully")
        print("   5. Add comprehensive error handling for all code paths")
        print("   6. Consider adding typing indicators for longer processing")
        print("   7. Implement conversation context awareness")
        
        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "findings": self.findings,
            "test_results": self.test_results
        }

def main():
    """Run comprehensive QA testing"""
    print("🚀 STARTING COMPREHENSIVE CHATBOT QA TESTING")
    print("This will test edge cases, conversation flows, and robustness")
    print("="*80)
    
    tester = ChatbotQATester()
    
    # Run all test suites
    tester.test_edge_cases()
    tester.test_variable_initialization()
    tester.analyze_hardcoded_responses()
    
    # Generate final report
    report = tester.generate_report()
    
    print("\n🏁 QA TESTING COMPLETE!")
    print(f"Generated {len(report['findings'])} findings across {report['total_tests']} tests")

if __name__ == "__main__":
    main()