from __future__ import annotations

from typing import Any

import pandas as pd

EXPECTED_BUSINESS_COLUMNS = [
    "DIVISION",
    "REGION",
    "EMPID",
    "EMP NAME",
    "DESIGNATION",
    "HQ",
    "ITEM CODE",
    "Promo Name",
    "Qty Dispatched",
    "Qty Acknowledged",
    "Qty Distributed",
    "Qty Balanced",
]

OUTPUT_COLUMNS = ["SR. No."] + EXPECTED_BUSINESS_COLUMNS


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trim whitespace from all column names and normalize them for comparison.
    """
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def validate_input_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """
    Validate an incoming Excel dataframe against the fixed Macleods template.

    The incoming file may contain 'SR. No.'; that column is ignored for validation.
    """
    df = normalize_column_names(df)

    current_columns = [c for c in df.columns.tolist() if c != "SR. No."]
    missing_columns = [c for c in EXPECTED_BUSINESS_COLUMNS if c not in current_columns]
    extra_columns = [c for c in current_columns if c not in EXPECTED_BUSINESS_COLUMNS]

    if missing_columns:
        return {
            "status": "error",
            "message": "Uploaded file is missing required columns.",
            "missing_columns": missing_columns,
            "extra_columns": extra_columns,
        }

    if extra_columns:
        return {
            "status": "error",
            "message": "Uploaded file contains extra columns that are not part of the fixed template.",
            "missing_columns": [],
            "extra_columns": extra_columns,
        }

    return {
        "status": "success",
        "message": "Uploaded file matches the expected template.",
        "missing_columns": [],
        "extra_columns": [],
    }