"""Central configuration, read from environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()  # "openrouter" | "anthropic" | "mock"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
SUPERVISOR_MODEL = os.getenv("SUPERVISOR_MODEL", "nvidia/nemotron-3.5-lightning:free")
AGENT_MODEL = os.getenv("AGENT_MODEL", "nvidia/nemotron-3.5-lightning:free")

DB_PATH = Path(os.getenv("DB_PATH", ROOT / "bank.db"))
LOG_DIR = ROOT / "logs"
POLICY_DIR = ROOT / "app" / "data" / "policies"

MAX_AGENT_STEPS = 6          # safety cap on the tool-calling loop
MAX_TOOL_RESULT_CHARS = 6000  # truncate huge tool outputs before feeding the LLM
