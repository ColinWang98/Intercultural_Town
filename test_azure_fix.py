#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Azure OpenAI connection with correct endpoint
"""
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv

# Set correct endpoint (override if needed)
CORRECT_ENDPOINT = "https://yao2wang-0342-resource.cognitiveservices.azure.com/"

print("=" * 50)
print("Azure Configuration Fix")
print("=" * 50)

load_dotenv()

current_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '')
api_key = os.getenv('AZURE_OPENAI_API_KEY', '')
api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-05-01-preview')

print(f"\nCurrent endpoint: {current_endpoint}")
print(f"Correct endpoint:  {CORRECT_ENDPOINT}")

if current_endpoint != CORRECT_ENDPOINT:
    print("\n[!] Endpoint needs to be updated!")
    print("\nTo fix, add this to your .env file or system environment:")
    print(f"AZURE_OPENAI_ENDPOINT={CORRECT_ENDPOINT}")
    print(f"AZURE_OPENAI_API_VERSION={api_version}")
else:
    print("\n[OK] Endpoint is correct!")

# Test connection with manual override
print("\n" + "=" * 50)
print("Testing connection with correct endpoint...")
print("=" * 50)

try:
    from litellm import completion

    # Test with correct endpoint
    response = completion(
        model="azure/gpt-5.2-chat",
        messages=[{"role": "user", "content": "Hello"}],
        api_base=CORRECT_ENDPOINT,
        api_key=api_key,
        api_version=api_version,
        timeout=15
    )
    print("[SUCCESS] Azure connection works!")
    print(f"Response: {response.choices[0].message.content[:80]}...")
    print("\n[OK] Configuration is correct!")

except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {str(e)[:200]}")

print("\n" + "=" * 50)
