import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Server Config
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", 8000))

# Security & JWT Config
JWT_SECRET: str = os.getenv("JWT_SECRET", "clinic_royal_jwt_secret_key_uae_2026_super_secure")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS: int = 7

# OpenAI & AI Config
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
