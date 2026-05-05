import logging

from .config import get_qa_chain, set_qa_chain
from .llm import VLLMConnectionError, get_llm

logger = logging.getLogger(__name__)


def load_knowledge_base(kb_path: str = None):
    """
    Keep the old initialization contract, but switch the implementation to a
    direct vLLM client instead of FAISS + RetrievalQA.
    """
    existing_client = get_qa_chain()
    if existing_client:
        return None, existing_client

    client = get_llm()
    try:
        client.healthcheck()
    except VLLMConnectionError:
        raise
    set_qa_chain(client)
    logger.info("vLLM client initialized successfully.")
    return None, client
