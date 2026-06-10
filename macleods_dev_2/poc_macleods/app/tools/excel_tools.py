from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import DATA_FILE_EXTENSIONS, LOCAL_INPUT_DIR, MASTER_DATASET_FILE
from ..services.validation_service import OUTPUT_COLUMNS, normalize_column_names


def _discover_local_excel_files() -> list[Path]:
    """
    Discover Excel files from the local temp input directory.
    This is kept as a fallback for local runs.
    """
    excel_files: list[Path] = []

    if not LOCAL_INPUT_DIR.exists():
        return excel_files

    for file_path in LOCAL_INPUT_DIR.iterdir():
        if not file_path.is_file():
            continue

        if file_path.name.startswith("~$"):
            continue

        if file_path.suffix.lower() not in DATA_FILE_EXTENSIONS:
            continue

        excel_files.append(file_path)

    excel_files.sort(key=lambda p: p.name.lower())
    return excel_files


def load_master_dataset(excel_files: list[Path] | None = None) -> dict[str, Any]:
    """
    Load and combine all Excel files.

    If excel_files is provided, those local files are used.
    Otherwise, files are discovered from the local temp input directory.

    Returns:
        dict[str, Any]:
            status: success/error
            message: readable explanation
            row_count: total combined rows
            columns: final columns
            data: combined dataset as records
            files_processed: list of processed file names
    """
    try:
        if excel_files is None:
            excel_files = _discover_local_excel_files()

        if not excel_files:
            return {
                "status": "success",
                "message": "No Excel files found in the input folder.",
                "row_count": 0,
                "columns": [],
                "data": [],
                "files_processed": [],
            }

        all_dataframes = []
        processed_files = []

        for excel_file in excel_files:
            if not excel_file.exists():
                continue

            excel_data = pd.read_excel(excel_file, sheet_name=None)

            if not excel_data:
                continue

            first_sheet_name = list(excel_data.keys())[0]
            df = excel_data[first_sheet_name]

            df = normalize_column_names(df)

            all_dataframes.append(df)
            processed_files.append(excel_file.name)

        if not all_dataframes:
            return {
                "status": "success",
                "message": "No valid Excel data found in the input folder.",
                "row_count": 0,
                "columns": [],
                "data": [],
                "files_processed": [],
            }

        final_df = pd.concat(all_dataframes, ignore_index=True)

        return {
            "status": "success",
            "message": "All Excel files loaded successfully.",
            "row_count": int(len(final_df)),
            "columns": final_df.columns.tolist(),
            "data": final_df.to_dict(orient="records"),
            "files_processed": processed_files,
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to load Excel files: {exc}",
            "row_count": 0,
            "columns": [],
            "data": [],
            "files_processed": [],
        }


def load_excel_file(file_path: str) -> dict[str, Any]:
    """
    Load a single Excel file from disk and return it as records.
    The first sheet is used automatically.
    """
    try:
        path = Path(file_path)

        if not path.exists():
            return {
                "status": "error",
                "message": f"File not found: {file_path}",
                "row_count": 0,
                "columns": [],
                "data": [],
            }

        excel_data = pd.read_excel(path, sheet_name=None)

        if not excel_data:
            return {
                "status": "error",
                "message": f"No sheets found in file: {path.name}",
                "row_count": 0,
                "columns": [],
                "data": [],
            }

        first_sheet_name = list(excel_data.keys())[0]
        df = excel_data[first_sheet_name]

        df = normalize_column_names(df)

        return {
            "status": "success",
            "message": f"Loaded file successfully: {path.name}",
            "row_count": int(len(df)),
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records"),
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to load file {file_path}: {exc}",
            "row_count": 0,
            "columns": [],
            "data": [],
        }


def save_master_dataset(dataset_records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Save the finalized dataset back to the master workbook.

    Note:
        This function needs a file path, not a folder path.
        If MASTER_DATASET_FILE is a directory, do not use it here.
        Add a separate output file path when you are ready for the save step.
    """
    try:
        if not dataset_records:
            return {
                "status": "error",
                "message": "No dataset records were provided for saving.",
                "row_count": 0,
                "file_path": str(MASTER_DATASET_FILE),
            }

        df = pd.DataFrame(dataset_records)

        if not df.empty:
            df = df[OUTPUT_COLUMNS]

        return {
            "status": "success",
            "message": "Dataset prepared successfully. Save step is not active yet.",
            "row_count": int(len(df)),
            "file_path": str(MASTER_DATASET_FILE),
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to prepare master dataset: {exc}",
            "row_count": 0,
            "file_path": str(MASTER_DATASET_FILE),
        }