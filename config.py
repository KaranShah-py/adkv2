from pathlib import Path
import os

# Base Directory — the installed package location (read-only on Vertex AI Agent Engine)
BASE_DIR = Path(__file__).resolve().parents[1]

# FIX (PDF Permission Denied — query 8):
# On Vertex AI Agent Engine the installed package directory is read-only at runtime.
# BASE_DIR / "temp/..." resolves to somewhere inside the installed package directory,
# which causes "[Errno 13] Permission denied" when the PDF service tries to write files.
#
# The ONLY writable directory on Vertex AI Agent Engine containers is /tmp.
# All local temp paths must be rooted there instead.
#
# BEFORE (broken on Agent Engine):
#   LOCAL_TEMP_DIR = BASE_DIR / "temp"
#
# AFTER (writable on Agent Engine):
LOCAL_TEMP_DIR = Path("/tmp") / "macleods"

LOCAL_INPUT_DIR = LOCAL_TEMP_DIR / "input"
LOCAL_OUTPUT_DIR = LOCAL_TEMP_DIR / "output"
LOCAL_REPORTS_DIR = LOCAL_OUTPUT_DIR / "reports"
LOCAL_CHARTS_DIR = LOCAL_OUTPUT_DIR / "charts"
LOCAL_LOGO_DIR = LOCAL_OUTPUT_DIR / "logo"

# GCS bucket settings
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "macleods-poc")

GCS_INPUT_PREFIX = "input/"
GCS_REPORTS_PREFIX = "reports/"
GCS_CHARTS_PREFIX = "charts/"
GCS_LOGO_PREFIX = "logo/"

# Files
MODEL_NAME = "gemini-2.5-pro"
DATA_FILE_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}

# Compatibility placeholder used by older code
MASTER_DATASET_FILE = LOCAL_OUTPUT_DIR / "master_dataset.xlsx"

# Example logo file name in bucket
LOGO_FILE_NAME = "macleodsLogo.png"

# Create local temp folders at import time.
# /tmp is always writable so mkdir will never raise Permission denied.
for folder in (
    LOCAL_TEMP_DIR,
    LOCAL_INPUT_DIR,
    LOCAL_OUTPUT_DIR,
    LOCAL_REPORTS_DIR,
    LOCAL_CHARTS_DIR,
    LOCAL_LOGO_DIR,
):
    folder.mkdir(parents=True, exist_ok=True)
