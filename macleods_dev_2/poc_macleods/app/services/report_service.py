from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import (
    GCP_BUCKET_NAME,
    GCS_LOGO_PREFIX,
    GCS_REPORTS_PREFIX,
    LOCAL_LOGO_DIR,
    LOCAL_REPORTS_DIR,
    LOGO_FILE_NAME,
)
from ..services.validation_service import EXPECTED_BUSINESS_COLUMNS, normalize_column_names
from .gcs_helper import GCSHelper

import logging

logger = logging.getLogger(__name__)

NUMERIC_COLUMNS = [
    "Qty Dispatched",
    "Qty Acknowledged",
    "Qty Distributed",
    "Qty Balanced",
]

gcs_helper = GCSHelper(GCP_BUCKET_NAME)



def _prepare_dataframe(final_records: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert finalized records into a clean dataframe.
    """
    df = pd.DataFrame(final_records or [])

    if df.empty:
        return pd.DataFrame(columns=EXPECTED_BUSINESS_COLUMNS)

    df = normalize_column_names(df)

    for col in EXPECTED_BUSINESS_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[EXPECTED_BUSINESS_COLUMNS].copy()

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def _add_distribution_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add calculated distribution metrics to the dataframe.
    """
    df = df.copy()

    df["Distribution %"] = df.apply(
        lambda row: round((row["Qty Distributed"] / row["Qty Acknowledged"]) * 100, 1)
        if row["Qty Acknowledged"] > 0
        else 0.0,
        axis=1,
    )

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

    low_distribution_rows = int((df["Distribution %"] < 95).sum()) if not df.empty else 0
    zero_distribution_rows = int((df["Qty Distributed"] == 0).sum()) if not df.empty else 0
    high_pending_rows = int((df["Qty Balanced"] > 20).sum()) if not df.empty else 0

    return {
        "total_rows": int(len(df)),
        "total_qty_dispatched": total_dispatched,
        "total_qty_acknowledged": total_acknowledged,
        "total_qty_distributed": total_distributed,
        "total_qty_balanced": total_balanced,
        "distribution_percentage": distribution_pct,
        "low_distribution_rows": low_distribution_rows,
        "zero_distribution_rows": zero_distribution_rows,
        "high_pending_rows": high_pending_rows,
    }


def _build_summary_table(summary: dict[str, Any]) -> Table:
    """
    Build a compact KPI table for the PDF.
    """
    data = [
        ["Metric", "Value"],
        ["Total Records", f"{int(summary['total_rows'])}"],
        ["Qty Dispatched", f"{summary['total_qty_dispatched']:.0f}"],
        ["Qty Acknowledged", f"{summary['total_qty_acknowledged']:.0f}"],
        ["Qty Distributed", f"{summary['total_qty_distributed']:.0f}"],
        ["Qty Balanced", f"{summary['total_qty_balanced']:.0f}"],
        ["Distribution %", f"{summary['distribution_percentage']:.1f}%"],
        ["Low Distribution Rows", f"{summary['low_distribution_rows']}"],
        ["Zero Distribution Rows", f"{summary['zero_distribution_rows']}"],
        ["High Pending Rows", f"{summary['high_pending_rows']}"],
    ]

    table = Table(data, colWidths=[2.8 * inch, 2.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAF2F8")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C2CC")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def _make_table(df: pd.DataFrame, columns: list[str], max_rows: int = 10) -> Table:
    """
    Create a nice looking report table.
    """
    safe_columns = [c for c in columns if c in df.columns]
    data = [safe_columns]

    display_df = df[safe_columns].head(max_rows).copy()

    for _, row in display_df.iterrows():
        data.append([str(row[col]) for col in safe_columns])

    col_count = max(1, len(safe_columns))
    width = 10.8 * inch
    col_width = width / col_count

    table = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _figure_to_rlimage(fig, width: float = 4.6 * inch, height: float = 2.8 * inch) -> RLImage:
    """
    Convert a matplotlib figure to a ReportLab image.
    """
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return RLImage(buffer, width=width, height=height)


def _chart_placeholder(text: str) -> Paragraph:
    """
    Placeholder used when a chart cannot be created.
    """
    styles = getSampleStyleSheet()
    return Paragraph(text, styles["BodyText"])


def _overall_chart(df: pd.DataFrame) -> RLImage | None:
    if df.empty:
        return None

    total_distributed = float(df["Qty Distributed"].sum())
    total_balanced = float(df["Qty Balanced"].sum())

    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    ax.pie(
        [total_distributed, total_balanced],
        labels=["Distributed", "Balanced"],
        autopct="%1.1f%%",
        startangle=90,
        colors=["#2E86AB", "#F18F01"],
        textprops={"fontsize": 8},
    )
    ax.set_title("Overall Distribution", fontsize=11, fontweight="bold")
    return _figure_to_rlimage(fig)


def _pending_chart(df: pd.DataFrame) -> RLImage | None:
    if df.empty:
        return None

    agg = (
        df.groupby(["EMP NAME", "EMPID"], as_index=False)[["Qty Balanced"]]
        .sum()
        .sort_values("Qty Balanced", ascending=False)
        .head(8)
    )

    if agg.empty:
        return None

    labels = [f"{row['EMP NAME']}" for _, row in agg.iterrows()]
    values = agg["Qty Balanced"].astype(float).tolist()

    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    ax.barh(labels, values, color="#D1495B")
    ax.invert_yaxis()
    ax.set_title("Top Pending Stock", fontsize=11, fontweight="bold")
    ax.set_xlabel("Pending Qty")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=8)
    return _figure_to_rlimage(fig)


def _hq_chart(df: pd.DataFrame) -> RLImage | None:
    if df.empty:
        return None

    agg = (
        df.groupby("HQ", as_index=False)[["Qty Acknowledged", "Qty Distributed"]]
        .sum()
        .copy()
    )
    agg["Distribution %"] = agg.apply(
        lambda row: round((row["Qty Distributed"] / row["Qty Acknowledged"]) * 100, 1)
        if row["Qty Acknowledged"] > 0
        else 0.0,
        axis=1,
    )
    agg = agg.sort_values("Distribution %", ascending=False).head(8)

    if agg.empty:
        return None

    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    ax.bar(agg["HQ"], agg["Distribution %"], color="#4C78A8")
    ax.set_title("HQ-wise Distribution %", fontsize=11, fontweight="bold")
    ax.set_ylabel("Distribution %")
    ax.set_ylim(0, max(100, float(agg["Distribution %"].max()) + 10))
    ax.tick_params(axis="x", labelrotation=25, labelsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    return _figure_to_rlimage(fig)


def _distribution_donut_chart(
    df: pd.DataFrame,
    width: float,
    height: float,
) -> RLImage | None:
    """
    Build a clean donut chart comparing distributed vs pending quantity.
    """
    if df.empty:
        return None

    total_distributed = float(df["Qty Distributed"].sum())
    total_sold = float(df["Qty Acknowledged"].sum())

    if total_sold <= 0:
        return None

    total_distributed = min(total_distributed, total_sold)
    pending = max(total_sold - total_distributed, 0.0)

    values = [total_distributed, pending]
    labels = ["Distributed", "Pending"]
    colors_list = ["#2E86AB", "#F18F01"]

    def _autopct(pct: float) -> str:
        total = sum(values)
        absolute = pct / 100.0 * total
        return f"{pct:.1f}%\n({absolute:.0f})"

    fig, ax = plt.subplots(figsize=(4.0, 3.0))

    wedges, _, autotexts = ax.pie(
        values,
        labels=None,
        autopct=_autopct,
        startangle=90,
        counterclock=False,
        colors=colors_list,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        pctdistance=0.78,
        textprops={"fontsize": 8},
    )

    for autotext in autotexts:
        autotext.set_color("black")
        autotext.set_fontsize(8)

    ax.legend(
        wedges,
        labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=8,
        frameon=False,
    )
    ax.set_title("Distributed vs Pending", fontsize=10, fontweight="bold")
    ax.axis("equal")

    return _figure_to_rlimage(fig, width=width, height=height)


def _ensure_logo_local() -> Path | None:
    """
    Ensure the logo exists locally. If missing, download it from GCS.
    """
    local_logo_path = LOCAL_LOGO_DIR / LOGO_FILE_NAME

    if local_logo_path.exists():
        return local_logo_path

    blob_name = f"{GCS_LOGO_PREFIX}{LOGO_FILE_NAME}"

    try:
        gcs_helper.download_file(blob_name=blob_name, local_path=local_logo_path)
        return local_logo_path
    except Exception:
        return None


def _build_report_header(styles: dict[str, Any], report_title: str) -> Table:
    """
    Create report header with company logo and title.
    """
    logo_path = _ensure_logo_local()

    if logo_path and logo_path.exists():
        logo = RLImage(
            str(logo_path),
            width=2.8 * inch,
            height=0.97 * inch,
        )
    else:
        logo = Spacer(1, 0.1 * inch)

    title_block = Table(
        [[Paragraph(report_title, styles["CustomTitle"])]],
        colWidths=[8.0 * inch],
    )
    title_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    header = Table(
        [[logo, title_block]],
        colWidths=[3.1 * inch, 8.1 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return header


def _build_visual_summary_page(df: pd.DataFrame) -> list[Any]:
    """
    Build the dedicated visual page with:
    - top left chart
    - top right chart
    - centered donut chart
    """
    elements: list[Any] = []

    overall_chart = _overall_chart(df)
    hq_chart = _hq_chart(df)
    pending_chart = _pending_chart(df)

    left_chart = hq_chart if hq_chart else overall_chart
    right_chart = pending_chart if pending_chart else overall_chart

    if left_chart is None:
        left_chart = _chart_placeholder("No chart data available.")
    if right_chart is None:
        right_chart = _chart_placeholder("No chart data available.")

    top_row = Table(
        [[left_chart, right_chart]],
        colWidths=[5.0 * inch, 5.0 * inch],
    )
    top_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    donut_chart = _distribution_donut_chart(
        df,
        width=4.4 * inch,
        height=3.0 * inch,
    )

    if donut_chart is None:
        donut_chart = _chart_placeholder("No chart data available.")

    donut_row = Table(
        [[donut_chart]],
        colWidths=[10.0 * inch],
    )
    donut_row.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    elements.append(Spacer(1, 0.05 * inch))
    elements.append(top_row)
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(donut_row)

    return elements


def _page_decorator(canvas, doc):
    """
    Page header and footer.
    """
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(colors.HexColor("#1F4E79"))
    canvas.drawString(
        doc.leftMargin,
        doc.pagesize[1] - 0.4 * inch,
        "Macleods Pharmaceuticals - Distribution Report",
    )
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _build_summary_and_top_performers_page(
    df: pd.DataFrame,
    summary: dict[str, Any],
    styles: dict[str, Any],
) -> list[Any]:
    """
    Build the next page with:
    - summary matrix
    - top 10 employees based on Qty Distributed
    """
    elements: list[Any] = []

    matrix_data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Total Records", f"{int(summary['total_rows'])}", "Distribution %", f"{summary['distribution_percentage']:.1f}%"],
        ["Dispatched", f"{summary['total_qty_dispatched']:.0f}", "Acknowledged", f"{summary['total_qty_acknowledged']:.0f}"],
        ["Distributed", f"{summary['total_qty_distributed']:.0f}", "Balanced", f"{summary['total_qty_balanced']:.0f}"],
        ["Low Dist. Rows", f"{summary['low_distribution_rows']}", "Zero Dist. Rows", f"{summary['zero_distribution_rows']}"],
        ["High Pending Rows", f"{summary['high_pending_rows']}", "", ""],
    ]

    matrix = Table(
        matrix_data,
        colWidths=[1.7 * inch, 1.45 * inch, 1.7 * inch, 1.45 * inch],
    )
    matrix.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAF2F8")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    elements.append(_paragraph("Summary Matrix", styles["SectionHeading"]))
    elements.append(matrix)
    elements.append(Spacer(1, 0.18 * inch))

    elements.append(_paragraph("Top Performers (Top 10)", styles["SectionHeading"]))

    def _pick_hq(series: pd.Series) -> str:
        values = [str(v).strip() for v in series if str(v).strip() and str(v).strip().lower() != "nan"]
        if not values:
            return ""
        mode_values = pd.Series(values).mode()
        return str(mode_values.iloc[0]) if not mode_values.empty else values[0]

    performer_df = (
        df.groupby(["EMPID", "EMP NAME"], as_index=False)
        .agg(
            {
                "HQ": _pick_hq,
                "Qty Dispatched": "sum",
                "Qty Acknowledged": "sum",
                "Qty Distributed": "sum",
                "Qty Balanced": "sum",
            }
        )
        .copy()
    )

    performer_df["Distribution %"] = performer_df.apply(
        lambda row: round(
            (row["Qty Distributed"] / row["Qty Acknowledged"]) * 100,
            1,
        )
        if row["Qty Acknowledged"] > 0
        else 0.0,
        axis=1,
    )

    performer_df = performer_df.sort_values(
        by=["Distribution %", "Qty Dispatched", "Qty Distributed"],
        ascending=[False, False, False],
    ).head(10)

    if performer_df.empty:
        elements.append(_paragraph("No performer records available.", styles["BodySmall"]))
        return elements

    table_data = [[
        "EMPID",
        "EMP NAME",
        "HQ",
        "QTY Dispatched",
        "QTY Distributed",
        "QTY Balance",
        "Distribution %",
    ]]

    for _, row in performer_df.iterrows():
        table_data.append([
            str(row["EMPID"]),
            str(row["EMP NAME"]),
            str(row["HQ"]),
            f"{float(row['Qty Dispatched']):.0f}",
            f"{float(row['Qty Distributed']):.0f}",
            f"{float(row['Qty Balanced']):.0f}",
            f"{float(row['Distribution %']):.1f}%",
        ])

    top_table = Table(
        table_data,
        colWidths=[
            1.15 * inch,
            2.25 * inch,
            1.55 * inch,
            1.25 * inch,
            1.35 * inch,
            1.15 * inch,
            1.15 * inch,
        ],
        repeatRows=1,
    )
    top_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    elements.append(top_table)

    return elements


def generate_pdf_report(
    final_records: list[dict[str, Any]],
    report_title: str = "Macleods Distribution Summary Report",
) -> dict[str, Any]:

    logger.warning("[PDF REPORT] START")

    try:
        logger.warning("[PDF REPORT] Step 1 - Preparing dataframe")

        df = _prepare_dataframe(final_records)

        logger.warning(
            f"[PDF REPORT] Dataframe rows={len(df)}"
        )

        if df.empty:
            logger.warning(
                "[PDF REPORT] Dataframe is empty"
            )

            return {
                "status": "error",
                "message": "No finalized data available for PDF generation.",
                "file_path": "",
                "row_count": 0,
                "summary": {},
            }

        logger.warning(
            "[PDF REPORT] Step 2 - Adding distribution metrics"
        )

        df = _add_distribution_metrics(df)

        logger.warning(
            "[PDF REPORT] Step 3 - Calculating summary"
        )

        summary = _summary_metrics(df)

        logger.warning(
            "[PDF REPORT] Step 4 - Creating output directory"
        )

        LOCAL_REPORTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        output_file = (
            LOCAL_REPORTS_DIR
            / f"macleods_report_{timestamp}.pdf"
        )

        logger.warning(
            f"[PDF REPORT] Output file={output_file}"
        )

        logger.warning(
            "[PDF REPORT] Step 5 - Creating styles"
        )

        styles = getSampleStyleSheet()

        styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#1F4E79"),
                spaceAfter=10,
            )
        )

        styles.add(
            ParagraphStyle(
                name="SectionHeading",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=14,
                textColor=colors.HexColor("#1F4E79"),
                spaceBefore=8,
                spaceAfter=6,
            )
        )

        styles.add(
            ParagraphStyle(
                name="BodySmall",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=colors.black,
            )
        )

        logger.warning(
            "[PDF REPORT] Step 6 - Creating document"
        )

        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=landscape(A4),
            leftMargin=0.45 * inch,
            rightMargin=0.45 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.55 * inch,
        )

        story: list[Any] = []

        logger.warning(
            "[PDF REPORT] Step 7 - Building header"
        )

        story.append(
            _build_report_header(
                styles,
                report_title,
            )
        )

        story.append(
            Spacer(
                1,
                0.12 * inch,
            )
        )

        story.append(
            _paragraph(
                f"Prepared on {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
                styles["BodySmall"],
            )
        )

        story.append(
            Spacer(
                1,
                0.12 * inch,
            )
        )

        logger.warning(
            "[PDF REPORT] Step 8 - Executive summary"
        )

        story.append(
            _paragraph(
                "Executive Summary",
                styles["SectionHeading"],
            )
        )

        story.append(
            _paragraph(
                f"This report covers <b>{summary['total_rows']}</b> records. "
                f"The overall distribution percentage is "
                f"<b>{summary['distribution_percentage']:.1f}%</b>. "
                f"There are <b>{summary['low_distribution_rows']}</b> "
                f"low-distribution rows, "
                f"<b>{summary['zero_distribution_rows']}</b> "
                f"zero-distribution rows, and "
                f"<b>{summary['high_pending_rows']}</b> "
                f"high-pending rows.",
                styles["BodySmall"],
            )
        )

        story.append(
            Spacer(
                1,
                0.12 * inch,
            )
        )

        story.append(
            _build_summary_table(
                summary
            )
        )

        story.append(
            Spacer(
                1,
                0.18 * inch,
            )
        )

        logger.warning(
            "[PDF REPORT] Step 9 - BEFORE Visual Summary"
        )

        story.append(
            PageBreak()
        )

        story.append(
            _paragraph(
                "Visual Summary",
                styles["SectionHeading"],
            )
        )

        story.extend(
            _build_visual_summary_page(df)
        )

        logger.warning(
            "[PDF REPORT] Step 10 - AFTER Visual Summary"
        )

        story.append(
            PageBreak()
        )

        logger.warning(
            "[PDF REPORT] Step 11 - BEFORE Top Performers"
        )

        story.extend(
            _build_summary_and_top_performers_page(
                df,
                summary,
                styles,
            )
        )

        logger.warning(
            "[PDF REPORT] Step 12 - AFTER Top Performers"
        )

        story.append(
            PageBreak()
        )

        logger.warning(
            "[PDF REPORT] Step 13 - Detailed Insights"
        )

        story.append(
            _paragraph(
                "Detailed Insights",
                styles["SectionHeading"],
            )
        )

        story.append(
            Spacer(
                1,
                0.08 * inch,
            )
        )

        logger.warning(
            "[PDF REPORT] Step 14 - BEFORE doc.build()"
        )

        doc.build(
            story,
            onFirstPage=_page_decorator,
            onLaterPages=_page_decorator,
        )

        logger.warning(
            "[PDF REPORT] Step 15 - AFTER doc.build()"
        )

        # -----------------------------------------------------
        # Artifact Only Mode (POC)
        # -----------------------------------------------------

        logger.warning(
            "[PDF REPORT] Step 16 - Skipping GCS Upload"
        )

        gcs_uri = ""

        logger.warning(
            "[PDF REPORT] Step 17 - SUCCESS RETURN"
        )

        return {
            "status": "success",
            "message": "PDF report generated successfully.",
            "report_name": output_file.name,
            "report_path": str(output_file),
            "local_file_path": str(output_file),
            "gcs_uri": gcs_uri,
            "row_count": int(len(df)),
            "generated_at": timestamp,
            "summary": summary,
        }

    except Exception as exc:

        logger.exception(
            f"[PDF REPORT] FATAL ERROR: {exc}"
        )

        return {
            "status": "error",
            "message": f"Failed to generate PDF report: {exc}",
            "report_name": "",
            "report_path": "",
            "local_file_path": "",
            "gcs_uri": "",
            "row_count": 0,
            "generated_at": "",
            "summary": {},
            "error": str(exc),
        }