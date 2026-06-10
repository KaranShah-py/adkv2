import asyncio
import logging
from pathlib import Path

from google.adk.tools import ToolContext
from google.genai import types

from ..models.agent_schemas import PdfResponse
from ..services.report_service import generate_pdf_report
from ..state_keys import (
    FINAL_RECORDS,
    PDF_REPORT_PATH,
    PDF_REPORT_NAME,
    PDF_GCS_URI,
    PDF_GENERATED_AT,
    PDF_LOCAL_FILE_PATH,
)

logger = logging.getLogger(__name__)


# FIX 3: Changed from `async def` to `def` so this tool is synchronous,
# consistent with all other tools in EntryAgent and AnalysisAgent.
# Mixing async tools in a sync agent graph on Vertex AI Agent Engine
# causes the stream to emit 0 bytes → "ADK agent returned no valid
# RunAgentResponse from stream data of size 0".
# save_artifact is an async coroutine, so we call it via asyncio.run()
# when we are inside a plain sync function.
def generate_distribution_pdf(
    tool_context: ToolContext,
    report_title: str = "Macleods Distribution Summary Report",
) -> PdfResponse:
    """
    Generate PDF report and save it as an ADK artifact.
    """

    try:

        final_records = tool_context.state.get(
            FINAL_RECORDS,
            [],
        )

        if not final_records:
            return PdfResponse(
                status="error",
                message=(
                    "No finalized dataset found. "
                    "Please load the dataset first."
                ),
                report_name="",
                report_path="",
                generated_at="",
                gcs_uri="",
                artifact_name="",
                artifact_version="",
                error="Dataset not available",
            )

        # --------------------------------------------------
        # Retry PDF Generation
        # --------------------------------------------------

        result = None

        for attempt in range(3):
            try:

                result = generate_pdf_report(
                    final_records=final_records,
                    report_title=report_title,
                )

                if (
                    result
                    and result.get("status") == "success"
                ):
                    break

            except Exception:
                if attempt == 2:
                    raise

        if not result or result.get("status") != "success":

            return PdfResponse(
                status="error",
                message=result.get(
                    "message",
                    "Failed to generate PDF report.",
                )
                if result
                else "Failed to generate PDF report.",
                report_name="",
                report_path="",
                generated_at="",
                gcs_uri="",
                artifact_name="",
                artifact_version="",
                error=(
                    result.get("error")
                    if result
                    else "PDF generation failed"
                ),
            )

        # --------------------------------------------------
        # Create Artifact
        # --------------------------------------------------

        artifact_version = ""

        try:

            pdf_path = Path(
                result["local_file_path"]
            )

            pdf_bytes = pdf_path.read_bytes()

            artifact = types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf",
            )

            # ------------------------------------------
            # Retry save_artifact
            # FIX 3: save_artifact is a coroutine. Since this function
            # is now sync, we drive it with asyncio.run(). This is safe
            # here because save_artifact does not need a running event
            # loop on the calling thread inside Vertex AI Agent Engine.
            # ------------------------------------------

            for attempt in range(3):

                try:

                    version = asyncio.run(
                        tool_context.save_artifact(
                            filename=result["report_name"],
                            artifact=artifact,
                        )
                    )

                    artifact_version = str(version)

                    tool_context.state[
                        "pdf_artifact_version"
                    ] = artifact_version

                    tool_context.state[
                        "pdf_artifact_name"
                    ] = result["report_name"]

                    break

                except Exception:

                    if attempt == 2:
                        raise

        except Exception:
            artifact_version = ""

        # --------------------------------------------------
        # Store Metadata
        # --------------------------------------------------

        tool_context.state[PDF_REPORT_PATH] = result.get(
            "report_path",
            "",
        )

        tool_context.state[PDF_LOCAL_FILE_PATH] = result.get(
            "local_file_path",
            "",
        )

        tool_context.state[PDF_REPORT_NAME] = result.get(
            "report_name",
            "",
        )

        tool_context.state[PDF_GCS_URI] = result.get(
            "gcs_uri",
            "",
        )

        tool_context.state[PDF_GENERATED_AT] = result.get(
            "generated_at",
            "",
        )

        return PdfResponse(
            status="success",
            message=result.get(
                "message",
                "PDF report generated successfully.",
            ),
            report_name=result.get(
                "report_name",
                "",
            ),
            report_path=result.get(
                "local_file_path",
                "",
            ),
            generated_at=result.get(
                "generated_at",
                "",
            ),
            gcs_uri=result.get(
                "gcs_uri",
                "",
            ),
            artifact_name=result.get(
                "report_name",
                "",
            ),
            artifact_version=artifact_version,
            error=None,
        )

    except Exception as exc:

        return PdfResponse(
            status="error",
            message="Failed to generate PDF report.",
            report_name="",
            report_path="",
            generated_at="",
            gcs_uri="",
            artifact_name="",
            artifact_version="",
            error=str(exc),
        )
