import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

ROUTING_SERVER_URL = os.environ.get("ROUTING_SERVER_URL", "http://routing-server:8080")
ROUTING_API_KEY = os.environ.get("ROUTING_API_KEY")

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_ROUNDS = 5
