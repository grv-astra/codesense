# config.py or init.py
import logging
import warnings
import os

# Suppress warnings globally
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Global logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

# Reduce noise from third-party libs
for logger_name in ["langchain", "langchain_community", "pymongo", "faiss", "urllib3", "requests"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)
