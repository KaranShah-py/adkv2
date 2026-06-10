from __future__ import annotations

from typing import Any

import pandas as pd

from ..services.validation_service import EXPECTED_BUSINESS_COLUMNS, OUTPUT_COLUMNS

IGNORE_FOR_DUPLICATE_CHECK = {"SR. No."}


def _canonical_value(value: Any) -> str:
    """
    Convert cell values into a stable text form for duplicate comparison.
    """
    if pd.isna(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value)).strip()

    return str(value).strip()


def _row_key(row: dict[str, Any]) -> str:
    """
    Build a comparison key from all business columns only.
    """
    return "||".join(_canonical_value(row.get(col, "")) for col in EXPECTED_BUSINESS_COLUMNS)


def merge_and_deduplicate(
    existing_df: pd.DataFrame,
    incoming_dfs: list[pd.DataFrame],
) -> dict[str, Any]:
    """
    Merge the existing master dataset with multiple incoming datasets,
    skip exact duplicate rows, and regenerate SR. No. from 1.

    Duplicate comparison ignores SR. No. and uses all other fixed columns.
    """
    try:
        existing_df = existing_df.copy() if existing_df is not None else pd.DataFrame(columns=OUTPUT_COLUMNS)
        incoming_dfs = incoming_dfs or []

        existing_records = []
        if not existing_df.empty:
            for _, row in existing_df.iterrows():
                row_dict = row.to_dict()
                row_dict.pop("SR. No.", None)
                existing_records.append({col: row_dict.get(col, "") for col in EXPECTED_BUSINESS_COLUMNS})

        seen_keys = set()
        final_records: list[dict[str, Any]] = []

        for row in existing_records:
            key = _row_key(row)
            if key not in seen_keys:
                seen_keys.add(key)
                final_records.append(row)

        total_incoming_rows = 0
        duplicate_rows_skipped = 0
        rows_added = 0
        file_row_counts = []

        for df in incoming_dfs:
            if df is None or df.empty:
                file_row_counts.append(0)
                continue

            file_row_counts.append(int(len(df)))
            total_incoming_rows += int(len(df))

            for _, row in df.iterrows():
                row_dict = row.to_dict()
                row_dict.pop("SR. No.", None)
                business_row = {col: row_dict.get(col, "") for col in EXPECTED_BUSINESS_COLUMNS}
                key = _row_key(business_row)

                if key in seen_keys:
                    duplicate_rows_skipped += 1
                    continue

                seen_keys.add(key)
                rows_added += 1
                final_records.append(business_row)

        for idx, row in enumerate(final_records, start=1):
            row["SR. No."] = idx

        ordered_records = []
        for row in final_records:
            ordered_records.append(
                {
                    "SR. No.": row.get("SR. No.", ""),
                    "DIVISION": row.get("DIVISION", ""),
                    "REGION": row.get("REGION", ""),
                    "EMPID": row.get("EMPID", ""),
                    "EMP NAME": row.get("EMP NAME", ""),
                    "DESIGNATION": row.get("DESIGNATION", ""),
                    "HQ": row.get("HQ", ""),
                    "ITEM CODE": row.get("ITEM CODE", ""),
                    "Promo Name": row.get("Promo Name", ""),
                    "Qty Dispatched": row.get("Qty Dispatched", ""),
                    "Qty Acknowledged": row.get("Qty Acknowledged", ""),
                    "Qty Distributed": row.get("Qty Distributed", ""),
                    "Qty Balanced": row.get("Qty Balanced", ""),
                }
            )

        return {
            "status": "success",
            "message": "Datasets merged successfully with duplicates removed.",
            "existing_row_count": int(len(existing_df)),
            "incoming_row_count": int(total_incoming_rows),
            "duplicate_rows_skipped": int(duplicate_rows_skipped),
            "rows_added": int(rows_added),
            "final_row_count": int(len(ordered_records)),
            "final_records": ordered_records,
            "file_row_counts": file_row_counts,
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to merge datasets: {exc}",
            "existing_row_count": 0,
            "incoming_row_count": 0,
            "duplicate_rows_skipped": 0,
            "rows_added": 0,
            "final_row_count": 0,
            "final_records": [],
            "file_row_counts": [],
        }