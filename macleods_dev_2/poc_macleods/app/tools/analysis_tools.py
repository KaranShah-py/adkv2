# app/tools/analysis_tools.py
from __future__ import annotations
from typing import Any
import pandas as pd
from google.adk.tools import ToolContext
from ..models.agent_schemas import AnalysisResponse
from ..services.validation_service import (
    EXPECTED_BUSINESS_COLUMNS,
    normalize_column_names,
)

from ..state_keys import (FINAL_RECORDS, DATASET_METADATA)

NUMERIC_COLUMNS = [
    "Qty Dispatched",
    "Qty Acknowledged",
    "Qty Distributed",
    "Qty Balanced",
]

TEXT_COLUMNS = [
    "DIVISION",
    "REGION",
    "EMPID",
    "EMP NAME",
    "DESIGNATION",
    "HQ",
    "ITEM CODE",
    "Promo Name",
]


def _get_dataset_from_state(
    tool_context: ToolContext,
) -> list[dict[str, Any]]:
    return tool_context.state.get(FINAL_RECORDS, [])


def _prepare_dataframe(dataset_records: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert dataset records into a clean dataframe.
    """
    df = pd.DataFrame(dataset_records or [])

    if df.empty:
        return pd.DataFrame(columns=EXPECTED_BUSINESS_COLUMNS)

    df = normalize_column_names(df)

    for col in EXPECTED_BUSINESS_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[EXPECTED_BUSINESS_COLUMNS].copy()

    for col in TEXT_COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def _add_distribution_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add calculated distribution metrics.
    """
    df = df.copy()

    df["Distribution %"] = (
        (df["Qty Distributed"].div(df["Qty Acknowledged"].replace(0,pd.NA,)).fillna(0) * 100).round(1))

    df["Distribution Status"] = df["Distribution %"].apply(
        lambda x: "Exception" if x < 95 else "OK"
    )

    df["Pending Status"] = df["Qty Balanced"].apply(
        lambda x: "High Pending" if x > 20 else "Normal"
    )

    return df


def _summary_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Generate overall summary metrics.
    """
    total_dispatched = float(df["Qty Dispatched"].sum()) if not df.empty else 0.0
    total_acknowledged = float(df["Qty Acknowledged"].sum()) if not df.empty else 0.0
    total_distributed = float(df["Qty Distributed"].sum()) if not df.empty else 0.0
    total_balanced = float(df["Qty Balanced"].sum()) if not df.empty else 0.0

    distribution_pct = (
        round((total_distributed / total_acknowledged) * 100, 1)
        if total_acknowledged > 0
        else 0.0
    )

    return {
        "total_rows": int(len(df)),
        "total_qty_dispatched": total_dispatched,
        "total_qty_acknowledged": total_acknowledged,
        "total_qty_distributed": total_distributed,
        "total_qty_balanced": total_balanced,
        "distribution_percentage": distribution_pct,
        "low_distribution_flag": distribution_pct < 95,
    }

def meta_data_capture(
    tool_context: ToolContext,
) -> AnalysisResponse:
    """
    Capture dataset metadata and store it in session state.
    """

    try:

        dataset_records = _get_dataset_from_state(
            tool_context
        )

        df = _prepare_dataframe(
            dataset_records
        )

        if df.empty:
            return AnalysisResponse(
                status="error",
                query_type="metadata_capture",
                message="Dataset not available.",
                error="Dataset not loaded",
            )

        metadata = {
            "total_rows": int(len(df)),
            "columns": list(df.columns),
            "unique_values": {},
        }

        metadata_columns = [
            "DIVISION",
            "REGION",
            "EMPID",
            "EMP NAME",
            "DESIGNATION",
            "HQ",
            "ITEM CODE",
            "Promo Name",
        ]

        for column in metadata_columns:

            if column not in df.columns:
                continue

            values = (
                df[column]
                .dropna()
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )

            metadata["unique_values"][column] = sorted(
                values
            )

        tool_context.state[
            DATASET_METADATA
        ] = metadata

        return AnalysisResponse(
            status="success",
            query_type="metadata_capture",
            message="Dataset metadata captured successfully.",
            row_count=len(df),
            summary=metadata,
            business_summary=(
                f"Metadata generated for "
                f"{len(df)} records."
            ),
        )

    except Exception as exc:

        return AnalysisResponse(
            status="error",
            query_type="metadata_capture",
            message="Failed to capture metadata.",
            error=str(exc),
        )
    
def distribution_analysis(
    tool_context: ToolContext,
    analysis_type: str = "",
    filters_json: str = "",
    group_by_csv: str = "",
    sort_by: str = "",
    sort_order: str = "desc",
    limit: int = 10,
) -> AnalysisResponse:
    """
    Universal distribution analysis engine.

    Supports:

    - Overall summary
    - Employee analysis
    - HQ analysis
    - Designation analysis
    - Item code analysis
    - Promo analysis
    - Ranking analysis
    - Exception analysis
    - Pending stock analysis
    - Zero distribution analysis
    """

    try:

        import json

        dataset_records = _get_dataset_from_state(
            tool_context
        )

        df = _prepare_dataframe(
            dataset_records
        )

        if df.empty:

            return AnalysisResponse(
                status="error",
                query_type="distribution_analysis",
                message=(
                    "No finalized dataset found. "
                    "Please load or finalize the dataset first."
                ),
                business_summary="",
                row_count=0,
                summary={},
                table=[],
                error="Dataset not loaded",
            )

        df = _add_distribution_metrics(df)

        # --------------------------------------------------
        # Parse Filters
        # --------------------------------------------------

        filters = {}

        if filters_json.strip():

            try:
                filters = json.loads(
                    filters_json
                )

            except Exception:
                filters = {}

        # --------------------------------------------------
        # WHERE
        # --------------------------------------------------

        for column, values in filters.items():

            if column not in df.columns:
                continue

            if not isinstance(values, list):
                values = [values]

            values = [
                str(v).strip().lower()
                for v in values
            ]

            df = df[
                df[column]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(values)
            ]

        # --------------------------------------------------
        # BUSINESS RULES
        # --------------------------------------------------

        analysis_type = (
            analysis_type
            .strip()
            .lower()
        )

        if analysis_type == "exception":

            df = df[
                (
                    df["Distribution %"]
                    < 95
                )
                |
                (
                    df["Qty Distributed"]
                    == 0
                )
                |
                (
                    df["Qty Balanced"]
                    > 20
                )
            ]

        elif analysis_type == "pending_stock":

            df = df[
                df["Qty Balanced"] > 0
            ]

        elif analysis_type == "zero_distribution":

            df = df[
                df["Qty Distributed"] == 0
            ]

        elif analysis_type == "ranking":

            group_by_csv = (
                "EMPID,"
                "EMP NAME,"
                "HQ"
            )

            sort_by = "Distribution %"

        # --------------------------------------------------
        # GROUP BY
        # --------------------------------------------------

        group_by_columns = []

        if group_by_csv.strip():

            group_by_columns = [
                col.strip()
                for col in group_by_csv.split(",")
                if col.strip()
            ]

        if group_by_columns:

            numeric_columns = [
                "Qty Dispatched",
                "Qty Acknowledged",
                "Qty Distributed",
                "Qty Balanced",
            ]

            df = (
                df.groupby(
                    group_by_columns,
                    as_index=False,
                )[numeric_columns]
                .sum()
                .copy()
            )

            df["Distribution %"] = (
                (
                    df["Qty Distributed"]
                    .div(
                        df[
                            "Qty Acknowledged"
                        ].replace(
                            0,
                            pd.NA,
                        )
                    )
                    .fillna(0)
                    * 100
                )
                .round(1)
            )

        # --------------------------------------------------
        # ORDER BY
        # --------------------------------------------------

        if (
            sort_by
            and sort_by in df.columns
        ):

            df = df.sort_values(
                by=sort_by,
                ascending=(
                    sort_order.lower()
                    == "asc"
                ),
            )

        # --------------------------------------------------
        # LIMIT
        # --------------------------------------------------

        try:
            limit = max(
                1,
                int(limit),
            )

        except Exception:
            limit = 10

        result_df = (
            df.head(limit)
            .copy()
        )

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        summary = _summary_metrics(df)

        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        table = (
            result_df.to_dict(
                orient="records"
            )
            if not result_df.empty
            else []
        )

        business_summary = (
            f"{len(df)} records matched "
            f"the requested criteria."
        )

        return AnalysisResponse(
            status="success",
            query_type="distribution_analysis",
            message=(
                "Analysis completed successfully."
            ),
            business_summary=business_summary,
            row_count=int(len(df)),
            summary=summary,
            table=table,
            error=None,
        )

    except Exception as exc:

        return AnalysisResponse(
            status="error",
            query_type="distribution_analysis",
            message="Failed to perform analysis.",
            business_summary="",
            row_count=0,
            summary={},
            table=[],
            error=str(exc),
        )