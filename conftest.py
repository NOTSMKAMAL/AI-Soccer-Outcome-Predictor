import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Provide a placeholder key so that the google-genai SDK does not raise
# ValueError("No API key was provided") at module-import time during test collection.
# The real key is only needed when tests actually call the Gemini API;
# prediction-engine tests mock all external calls, so this placeholder is safe.
if not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "test-placeholder-key"
