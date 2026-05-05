import threading
from local.api_app.models.finding_models import FindingModel
KB_PATH = None
GLOBAL_KNOWLEDGE_BASE = None
GLOBAL_QA_CHAIN = None

FINDING_MODEL = FindingModel
MAX_TOKENS = 4096

DB_LOCK = threading.Lock()
PROGRESS_LOCK = threading.Lock()
SCAN_PROGRESS = {
    "total": 0,
    "scanned": 0,
    "status": "not_started"
}

def set_kb_path(path: str):
    global KB_PATH
    KB_PATH = path

def get_kb_path():
    return KB_PATH

def set_knowledge_base(kb):
    global GLOBAL_KNOWLEDGE_BASE
    GLOBAL_KNOWLEDGE_BASE = kb

def get_knowledge_base():
    return GLOBAL_KNOWLEDGE_BASE

def set_qa_chain(chain):
    global GLOBAL_QA_CHAIN
    GLOBAL_QA_CHAIN = chain

def get_qa_chain():
    return GLOBAL_QA_CHAIN
