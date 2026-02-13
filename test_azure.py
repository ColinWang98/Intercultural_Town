#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Azure OpenAI deployment

Verify that the deployment names match what's actually on Azure.
"""
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv

load_dotenv()

# Get Azure config
endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '')
api_key = os.getenv('AZURE_OPENAI_API_KEY', '')
api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-01')

print("=" * 50)
print("Azure OpenAI Configuration Test")
print("=" * 50)

print(f"\nEndpoint: {endpoint}")
print(f"API Key: {'SET' if api_key else 'NOT SET'}")
print(f"API Version: {api_version}")

# Test deployment names
print("\n" + "=" * 50)
print("Common Azure OpenAI deployment names:")
print("=" * 50)
print("- gpt-4o                - GPT-4o model")
print("- gpt-4o-mini           - GPT-4o Mini (faster, cheaper)")
print("- gpt-35-turbo          - GPT-3.5 Turbo")
print("- gpt-4                 - GPT-4")

print("\n" + "=" * 50)
print("Your current model names in personas.py:")
print("=" * 50)
print("- Mikko:      azure/gpt-4o-mini")
print("- Aino:       azure/gpt-4o-mini")
print("- Observer:   azure/gpt-4o-mini")
print("- Analyser:   azure/gpt-4o")
print("- Dynamic:    azure/gpt-4o-mini")

print("\n" + "=" * 50)
print("Troubleshooting:")
print("=" * 50)
print("If you see 'NotFoundError':")
print("1. Go to Azure Portal -> OpenAI resource")
print("2. Check 'Deployments' tab")
print("3. Find the exact deployment name (case-sensitive!)")
print("4. Update personas.py with the correct deployment name")
print("\nAlternative: Disable Azure to use local Ollama:")
print("- Set environment variable: USE_AZURE=false")
print("- Or create .env file with: USE_AZURE=false")

# Test actual connection
print("\n" + "=" * 50)
print("Testing connection...")
print("=" * 50)

try:
    from litellm import completion

    # Try to call with a test deployment
    response = completion(
        model="azure/gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        api_base=endpoint,
        api_key=api_key,
        api_version=api_version,
        timeout=10
    )
    print("SUCCESS: Azure connection works!")
    print(f"Response: {response.choices[0].message.content[:50]}...")

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    print("\nThis means:")
    print("- The deployment 'gpt-4o-mini' doesn't exist on your Azure resource")
    print("- OR your endpoint/API key is incorrect")
    print("\nSolution: Update the deployment name in personas.py to match your Azure deployment")

print("\n" + "=" * 50)
