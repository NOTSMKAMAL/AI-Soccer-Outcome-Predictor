import os
from dotenv import load_dotenv

load_dotenv()

APIFOOTBALL_API_KEY: str = os.getenv("APIFOOTBALL_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "./serviceAccountKey.json")

APIFOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
BACKEND_HOST = os.getenv("BACKEND_HOST", "http://localhost:8000")
