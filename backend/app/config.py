import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("RESEARCHMIND_DATA_DIR", str(BASE / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "researchmind.db"
MAX_UPLOAD_MB = int(os.environ.get("RESEARCHMIND_MAX_UPLOAD_MB", "50"))
LLM_PROVIDER = os.environ.get("RESEARCHMIND_LLM_PROVIDER", "none")  # none | openai
LLM_MODEL = os.environ.get("RESEARCHMIND_LLM_MODEL", "")
LLM_API_KEY = os.environ.get("RESEARCHMIND_LLM_API_KEY", "")
# Never send full documents to an external provider by default; only short
# evidence snippets, and only when a provider is explicitly configured.
LLM_SEND_SNIPPETS_ONLY = os.environ.get("RESEARCHMIND_LLM_SNIPPETS_ONLY", "true") == "true"
