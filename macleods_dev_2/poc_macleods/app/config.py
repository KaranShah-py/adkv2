from pathlib import Path
import os

# Base Directory
BASE_DIR = Path(__file__).resolve().parents[1]

# Local temp directories used only during processing
LOCAL_TEMP_DIR = BASE_DIR / "temp"
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

# Create local temp folders
for folder in (
    LOCAL_TEMP_DIR,
    LOCAL_INPUT_DIR,
    LOCAL_OUTPUT_DIR,
    LOCAL_REPORTS_DIR,
    LOCAL_CHARTS_DIR,
    LOCAL_LOGO_DIR,
):
    folder.mkdir(parents=True, exist_ok=True)