from typing import Any

from pydantic import BaseModel, Field


# ==========================================================
# Generic Tool Response
# ==========================================================

class ToolResponse(BaseModel):
    """
    Standard response model for all ADK tools.
    """

    status: str = Field(
        description="success or error"
    )

    message: str = Field(
        description="User friendly message"
    )

    error: str | None = Field(
        default=None,
        description="Error details if any"
    )


# ==========================================================
# Dataset / Entry Agent Response
# ==========================================================

from typing import Any

from pydantic import BaseModel, Field


class DatasetResponse(BaseModel):
    """
    Standard response for dataset operations.
    """

    status: str = Field(
        description="success or error"
    )

    message: str = Field(
        description="User friendly status message"
    )

    dataset_loaded: bool = Field(
        default=False
    )

    dataset_finalized: bool = Field(
        default=False
    )

    row_count: int = Field(
        default=0
    )

    column_count: int = Field(
        default=0
    )

    columns: list[str] = Field(
        default_factory=list
    )

    files_processed: list[str] = Field(
        default_factory=list
    )

    data: list[dict[str, Any]] = Field(
        default_factory=list
    )

    next_step: str | None = Field(
        default=None
    )

    error: str | None = Field(
        default=None
    )


# ==========================================================
# Analysis Agent Response
# ==========================================================

class AnalysisResponse(BaseModel):
    """
    Standard response returned by the analysis engine.
    """

    status: str = Field(
        description="success or error"
    )

    analysis_type: str = Field(
        default="",
        description="Detected analysis type"
    )

    message: str = Field(
        description="User friendly response"
    )

    business_summary: str = Field(
        default="",
        description="Business summary"
    )

    row_count: int = Field(
        default=0,
        description="Number of records after filtering"
    )

    filters_applied: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters used during analysis"
    )

    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary metrics"
    )

    records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Analysis records"
    )

    chart: dict[str, Any] = Field(
        default_factory=dict,
        description="Chart information"
    )

    error: str | None = Field(
        default=None,
        description="Error details"
    )


# ==========================================================
# Dataset Metadata Response
# ==========================================================

class DatasetMetadataResponse(BaseModel):

    status: str

    message: str

    row_count: int = 0

    column_count: int = 0

    columns: list[str] = Field(
        default_factory=list
    )

    searchable_columns: list[str] = Field(
        default_factory=list
    )

    unique_values: dict[str, list[str]] = Field(
        default_factory=dict
    )

    numeric_columns: list[str] = Field(
        default_factory=list
    )

    error: str | None = None

    

class PdfResponse(BaseModel):
    """
    Response returned by PDF generation.
    """

    status: str = Field(
        description="success or error"
    )

    message: str = Field(
        description="PDF generation status"
    )

    report_name: str = Field(
        default="",
        description="Generated report name"
    )

    report_path: str = Field(
        default="",
        description="Location of generated report"
    )

    generated_at: str = Field(
        default="",
        description="Timestamp when report was generated"
    )

    gcs_uri: str = Field(
        default="",
        description="Google Cloud Storage URI of the report"
    )

    artifact_name: str = Field(
        default="",
        description="Artifact file name"
    )

    artifact_version: str = Field(
        default="",
        description="Artifact version"
    )
    
    error: str | None = Field(
        default=None,
        description="Error details"
    )