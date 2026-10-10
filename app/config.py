import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN is not set")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set")