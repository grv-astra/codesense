import threading
from local.api_app.models.finding_models import FindingModel
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

def set_qa_chain(chain):
    global GLOBAL_QA_CHAIN
    GLOBAL_QA_CHAIN = chain

def get_qa_chain():
    return GLOBAL_QA_CHAIN
