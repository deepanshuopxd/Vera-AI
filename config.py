# config.py — Central configuration for your Vera bot

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────
# LLM Configuration
# ──────────────────────────────────────────
LLM_PROVIDER = "openai"                               
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # DO NOT HARDCODE IN GITHUB
LLM_MODEL = "gpt-4o"                                # OpenAI model to use
LLM_TEMPERATURE = 0.2                               # Low temp for deterministic output
LLM_MAX_TOKENS = 1500                               # Max response length

# ──────────────────────────────────────────
# Bot Configuration
# ──────────────────────────────────────────
BOT_PORT = 8080
TEAM_NAME = "Magicpin AI Challengers"
TEAM_MEMBERS = ["Deepanshu"]
CONTACT_EMAIL = "deepanshu@example.com"
BOT_VERSION = "1.0.0"

# ──────────────────────────────────────────
# Timeouts & Limits
# ──────────────────────────────────────────
COMPOSE_TIMEOUT_SECONDS = 25          # Leave 5s buffer under 30s judge timeout
MAX_ACTIONS_PER_TICK = 20
AUTO_REPLY_WAIT_SECONDS = 86400       # 24h wait after repeated auto-replies
