from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

from ..config import DATA_FILE_EXTENSIONS, GCP_BUCKET_NAME, GCS_INPUT_PREFIX, LOCAL_INPUT_DIR
from ..tools.excel_tools import load_master_dataset
from .gcs_helper import GCSHelper

from ..models.agent_schemas import DatasetResponse

# Session state keys used by the workflow
WORKFLOW_STAGE = "workflow_stage"
DATASET_FINALIZED = "dataset_finalized"
WAITING_FOR_FOLDER_CONFIRMATION = "waiting_for_folder_confirmation"
LAST_SCAN_STATUS = "last_scan_status"
FINAL_RECORDS = "final_records"
DATASET_SUMMARY = "dataset_summary"
FILES_PROCESSED = "files_processed"

gcs_helper = GCSHelper(GCP_BUCKET_NAME)

from google.adk.tools import ToolContext
from ..models.agent_schemas import DatasetResponse
from pathlib import Path

def _cache_dataset_state(
    tool_context: ToolContext,
    result: DatasetResponse,
    final_records: list[dict],
) -> None:
    """
    Cache finalized dataset information in session state.

    Args:
        tool_context (ToolContext):
            ADK session context.

        result (DatasetResponse):
            Dataset load/finalization result.

        final_records (list[dict]):
            Final dataset records used by downstream agents.

    Returns:
        None
    """

    tool_context.state[WORKFLOW_STAGE] = "analysis_ready"

    tool_context.state[DATASET_FINALIZED] = (
        result.dataset_finalized
    )

    tool_context.state[LAST_SCAN_STATUS] = (
        result.model_dump()
    )

    tool_context.state[FINAL_RECORDS] = (
        final_records
    )

    tool_context.state[DATASET_SUMMARY] = {
        "row_count": result.row_count,
        "column_count": result.column_count,
        "columns": result.columns,
        "files_processed": result.files_processed,
        "message": result.message,
    }

    tool_context.state[FILES_PROCESSED] = (
        result.files_processed
    )


def _discover_input_files() -> list[Path]:
    """
    Discover all valid Excel files from the configured GCS input location
    and download them to the local input directory.

    Rules:
    - Ignore temporary Excel files (~$)
    - Ignore unsupported file types
    - Download valid files locally

    Args:
        None

    Returns:
        list[Path]:
            List of downloaded local file paths.
    """

    files: list[Path] = []

    try:
        blob_names = gcs_helper.list_blobs(
            prefix=GCS_INPUT_PREFIX
        )

        for blob_name in blob_names:

            blob_path = Path(blob_name)
            file_name = blob_path.name

            # Ignore Excel lock files
            if file_name.startswith("~$"):
                continue

            # Ignore unsupported files
            if blob_path.suffix.lower() not in DATA_FILE_EXTENSIONS:
                continue

            local_path = LOCAL_INPUT_DIR / file_name

            gcs_helper.download_file(
                blob_name=blob_name,
                local_path=local_path,
            )

            files.append(local_path)

        return files

    except Exception as exc:
        raise RuntimeError(
            f"Failed to discover input files: {exc}"
        ) from exc

def _load_and_cache_master_dataset(
    tool_context: ToolContext,
    input_files: list[Path],
    success_message: str,
) -> DatasetResponse:
    """
    Load the combined dataset, cache it in session state,
    and return a standardized DatasetResponse.

    Args:
        tool_context (ToolContext):
            ADK session context.

        input_files (list[Path]):
            Excel files to process.

        success_message (str):
            Success message shown to the user.

    Returns:
        DatasetResponse:
            Dataset load result.
    """

    try:

        all_data = load_master_dataset(
            excel_files=input_files
        )

        if all_data.get("status") != "success":

            return DatasetResponse(
                status="error",
                message="Failed to load master dataset.",
                error=all_data.get(
                    "message",
                    "Unknown error occurred."
                ),
            )

        final_records = all_data.get(
            "data",
            [],
        )

        result = DatasetResponse(
            status="success",
            message=success_message,
            dataset_loaded=True,
            dataset_finalized=True,
            row_count=all_data.get(
                "row_count",
                0,
            ),
            column_count=len(
                all_data.get(
                    "columns",
                    [],
                )
            ),
            columns=all_data.get(
                "columns",
                [],
            ),
            files_processed=all_data.get(
                "files_processed",
                [],
            ),
            data=final_records,
        )

        _cache_dataset_state(
            tool_context=tool_context,
            result=result,
            final_records=final_records,
        )

        return result

    except Exception as exc:

        return DatasetResponse(
            status="error",
            message="Failed to load and cache master dataset.",
            error=str(exc),
        )


def continue_with_existing_dataset(
    tool_context: ToolContext,
) -> DatasetResponse:
    """
    Load all existing Excel files from the configured GCS bucket
    and prepare the dataset for analysis.

    Args:
        tool_context (ToolContext):
            ADK session context used to store dataset state.

    Returns:
        DatasetResponse:
            Dataset loading result including row count,
            columns, files processed and status.
    """

    try:

        input_files = _discover_input_files()

        if not input_files:

            result = DatasetResponse(
                status="success",
                message="No Excel files found in the bucket input folder.",
                dataset_loaded=False,
                dataset_finalized=False,
                row_count=0,
                column_count=0,
                columns=[],
                files_processed=[],
                data=[],
            )

            _cache_dataset_state(
                tool_context=tool_context,
                result=result,
                final_records=[],
            )

            import json

            state_size = len(
                json.dumps(
                    tool_context.state,
                    default=str
                )
            )

            print(
                f"STATE SIZE = {state_size} bytes"
            )

            return result

        return _load_and_cache_master_dataset(
            tool_context=tool_context,
            input_files=input_files,
            success_message=(
                "Loaded all Excel files from the bucket input folder successfully."
            ),
        )

    except Exception as exc:

        return DatasetResponse(
            status="error",
            message="Failed to load existing dataset.",
            error=str(exc),
            dataset_loaded=False,
            dataset_finalized=False,
            row_count=0,
            column_count=0,
            columns=[],
            files_processed=[],
            data=[],
        )


def refresh_dataset(
    tool_context: ToolContext,
) -> DatasetResponse:
    """
    Reload the latest dataset from the configured bucket
    and refresh the cached dataset state.

    Args:
        tool_context (ToolContext):
            ADK session context used to store dataset state.

    Returns:
        DatasetResponse:
            Refreshed dataset information including
            status, row count, columns and processed files.
    """

    try:

        input_files = _discover_input_files()

        if not input_files:

            result = DatasetResponse(
                status="success",
                message="No Excel files found in the bucket input folder.",
                dataset_loaded=False,
                dataset_finalized=False,
                row_count=0,
                column_count=0,
                columns=[],
                files_processed=[],
                data=[],
            )

            _cache_dataset_state(
                tool_context=tool_context,
                result=result,
                final_records=[],
            )

            return result

        return _load_and_cache_master_dataset(
            tool_context=tool_context,
            input_files=input_files,
            success_message=(
                "The dataset has been refreshed successfully using the latest files in the bucket input folder."
            ),
        )

    except Exception as exc:

        return DatasetResponse(
            status="error",
            message="Failed to refresh dataset.",
            error=str(exc),
            dataset_loaded=False,
            dataset_finalized=False,
            row_count=0,
            column_count=0,
            columns=[],
            files_processed=[],
            data=[],
        )