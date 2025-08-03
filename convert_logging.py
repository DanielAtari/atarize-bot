#!/usr/bin/env python3
"""
Script to convert all print() statements to logging in Python files.
"""

import re
import os
from pathlib import Path

def convert_print_to_logging(file_path):
    """Convert print statements to logging in a Python file"""
    print(f"Converting {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patterns for different types of print statements with their logging levels
    conversions = [
        # Error patterns
        (r'print\(f?"❌[^"]*"[^)]*\)', 'logger.error'),
        (r'print\(f?"ERROR[^"]*"[^)]*\)', 'logger.error'),
        (r'print\(f?"\[.*ERROR.*\][^"]*"[^)]*\)', 'logger.error'),
        
        # Warning patterns  
        (r'print\(f?"⚠️[^"]*"[^)]*\)', 'logger.warning'),
        (r'print\(f?"WARNING[^"]*"[^)]*\)', 'logger.warning'),
        (r'print\(f?"\[.*WARNING.*\][^"]*"[^)]*\)', 'logger.warning'),
        
        # Info patterns (success, main operations)
        (r'print\(f?"✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"🎉[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"📧[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"🟢[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"📄[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[HANDLE_QUESTION\][^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[INTENT_DETECTION\] Question:[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[GREETING\] First time[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[LEAD_FLOW\][^"]*✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[INTENT_RESOLUTION\][^"]*🎯[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[INTENT_FINAL\][^"]*✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[KNOWLEDGE_RETRIEVAL\][^"]*✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[CONTEXT_BUILDING\][^"]*✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[GPT_CALL\][^"]*✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[ANSWER_VALIDATION\][^"]*✅[^"]*"[^)]*\)', 'logger.info'),
        (r'print\(f?"\[FINAL_SUCCESS\][^"]*"[^)]*\)', 'logger.info'),
        
        # Debug patterns (detailed logs, traces)
        (r'print\(f?"\[DEBUG\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[SESSION_DEBUG\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[HISTORY\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[SMALL_TALK_CHECK\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[VAGUE_CHECK\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[CHROMA_DETECT\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[EXAMPLES\][^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[CONTEXT_BUILDING\](?![^"]*✅)[^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[GPT_CALL\](?![^"]*✅)[^"]*"[^)]*\)', 'logger.debug'),
        (r'print\(f?"\[TOKEN_USAGE\][^"]*"[^)]*\)', 'logger.debug'),
        
        # General catch-all patterns
        (r'print\(f?"([^"]*)"([^)]*)\)', lambda m: f'logger.info(f"{m.group(1)}"{m.group(2)})'),
        (r'print\(([^)]*)\)', lambda m: f'logger.info({m.group(1)})'),
    ]
    
    original_content = content
    
    # Apply conversions
    for pattern, replacement in conversions:
        if callable(replacement):
            content = re.sub(pattern, replacement, content)
        else:
            # Simple string replacement
            content = re.sub(pattern, lambda m: m.group(0).replace('print(', f'{replacement}('), content)
    
    # Write back if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Converted {file_path}")
        return True
    else:
        print(f"ℹ️  No changes needed for {file_path}")
        return False

def main():
    """Convert print statements in specified files"""
    files_to_convert = [
        'load_data.py',
        'load_intents.py', 
        'debug_intents.py'
    ]
    
    converted_count = 0
    for file_path in files_to_convert:
        if os.path.exists(file_path):
            if convert_print_to_logging(file_path):
                converted_count += 1
        else:
            print(f"⚠️  File not found: {file_path}")
    
    print(f"\n🎉 Conversion complete! {converted_count} files modified.")

if __name__ == "__main__":
    main()