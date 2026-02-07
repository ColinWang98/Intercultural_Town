import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("Azure OpenAI Configuration Check")
print("=" * 60)

use_azure = os.getenv('USE_AZURE')
endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
api_key = os.getenv('AZURE_OPENAI_API_KEY')
api_version = os.getenv('AZURE_OPENAI_API_VERSION')

print(f"\nUSE_AZURE: {use_azure}")
print(f"ENDPOINT: {endpoint}")
print(f"API_VERSION: {api_version}")

if api_key and api_key != "your-api-key-here":
    print(f"API_KEY: Set (length: {len(api_key)} chars)")
else:
    print("API_KEY: Not set")

print("\n" + "=" * 60)

# Validate configuration
if use_azure == "true":
    if endpoint and api_key:
        print("OK - Configuration complete, ready to start backend")
    else:
        print("ERROR - Configuration incomplete")
        if not endpoint:
            print("  - Missing AZURE_OPENAI_ENDPOINT")
        if not api_key:
            print("  - Missing AZURE_OPENAI_API_KEY")
else:
    print("WARNING - USE_AZURE=false, will use local Ollama")

print("=" * 60)
