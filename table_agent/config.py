import os

# --- API Configurations ---
API_URL = "https://finixdocapi.alipay.com/api/finix_doc/call_with_file"
API_KEY = "F935A5503983FB19F26FA3F00A94EBF9"
USER_IDS = ["finixA1001", "finixB2002", "finixC3003", "finixD4004", "finixE5005"]

# --- Path Configurations ---
WORKSPACE_DIR = r"F:\ProgramProject\AFAC2026\Track2"
CACHE_DIR = os.path.join(WORKSPACE_DIR, "Cache")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "Output")
DATASET_DIR = os.path.join(WORKSPACE_DIR, "AFAC_DataSet", "finixdocbench_huge_table_100")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
LEDGER_PATH = os.path.join(CACHE_DIR, "task_ledger_table_analysis.json")
SUBMISSION_PATH = os.path.join(OUTPUT_DIR, "submission_table_analysis.csv")

# --- Slicing Parameters ---
DEFAULT_CHUNK_HEIGHT = 400
DEFAULT_OVERLAP_PCT = 0.15

# --- Hallucination Mitigations ---
MAX_ALLOWED_COLS = 110
ROW_SIMILARITY_THRESHOLD = 0.95

# --- General Run Settings ---
MAX_WORKERS = 4
