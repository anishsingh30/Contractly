import io
import docx
from docx.shared import Inches, Pt, RGBColor
from datetime import datetime, timezone
from typing import Optional
from app.models.contract import Contract
from app.models.user import User


def generate_contract_revisions_docx(
    contract: Contract,
    exported_by_user: Optional[User] = None
) -> bytes:
    """
    Generates a genuine Microsoft Word (.docx) document containing:
    1. Contract title & metadata header table.
    2. Educational plain-language disclaimer regarding proposed revisions.
    3. Formatted comparison of each proposed redline:
       - Original Provision: visual strikethrough with crimson color.
       - Proposed Language: bold, underline, forest green color.
       - Metadata: author, rationale, internal discussion comment, and approval status.
    4. Baseline contract document text appendix (if available).

    Important Word-format transparency:
    python-docx does not create Microsoft Word Track Changes XML revisions.
    Revisions are rendered as formatted comparison blocks for universal Word compatibility.

    Returns raw binary bytes of the .docx file.
    Does NOT modify the database or any contract models.
    """
    doc = docx.Document()

    # Configure 1-inch margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Document Title
    title_p = doc.add_paragraph()
    title_run = title_p.add_run(f"{contract.title} — Proposed Revisions")
    title_run.font.size = Pt(18)
    title_run.bold = True
    title_run.font.color.rgb = RGBColor(36, 35, 33)  # Warm charcoal

    # Subtitle
    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run(
        f"Contract Reference: {contract.contract_id}  |  Version: {contract.version}  |  Status: {contract.status}"
    )
    sub_run.font.size = Pt(10)
    sub_run.font.color.rgb = RGBColor(111, 106, 97)  # Muted olive

    # Metadata Table
    table = doc.add_table(rows=4, cols=2)
    table.style = 'Table Grid'

    export_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    exporter_name = exported_by_user.full_name if exported_by_user else (contract.owner or "Contractly System")

    meta_rows = [
        ("Counterparty:", contract.counterparty or "Not specified", "Department:", contract.department or "Legal"),
        ("Effective / Start Date:", contract.start_date or "Not specified", "Expiry / Renewal Date:", contract.expiry_date or "Not specified"),
        ("Governing Law:", contract.governing_law or "Laws of India", "Exported At (UTC):", export_time_str),
        ("Exported By:", exporter_name, "Total Redlines Recorded:", str(len(contract.redlines or [])))
    ]

    for row_idx, (k1, v1, k2, v2) in enumerate(meta_rows):
        row_cells = table.rows[row_idx].cells
        p0 = row_cells[0].paragraphs[0]
        p0.add_run(f"{k1} ").bold = True
        p0.add_run(str(v1))

        p1 = row_cells[1].paragraphs[0]
        p1.add_run(f"{k2} ").bold = True
        p1.add_run(str(v2))

    doc.add_paragraph()  # Spacing

    # Notice & Disclaimer
    notice_p = doc.add_paragraph()
    notice_run = notice_p.add_run(
        "Notice on Proposed Revisions: This document was compiled by Contractly. Proposed revisions are formatted "
        "as visual comparative blocks with strike-through for deleted/original text and underlined bold for proposed additions. "
        "Universal Microsoft Word (.docx) compatibility is preserved. Note: Native Microsoft Word Track Changes XML revisions "
        "are not enabled in this document."
    )
    notice_run.italic = True
    notice_run.font.size = Pt(9.5)
    notice_run.font.color.rgb = RGBColor(111, 106, 97)

    # 1. Proposed Redlines Section
    h1 = doc.add_heading(level=1)
    h1_run = h1.add_run("1. Proposed Contract Revisions & Redlines")
    h1_run.font.color.rgb = RGBColor(63, 70, 52)  # Deep Olive

    redlines = sorted(contract.redlines or [], key=lambda r: r.created_at or datetime.min)
    if not redlines:
        empty_p = doc.add_paragraph()
        empty_p.add_run("No proposed revisions (redlines) are currently recorded for this contract.").italic = True
    else:
        for idx, r in enumerate(redlines, 1):
            sec_p = doc.add_paragraph()
            sec_title_run = sec_p.add_run(f"1.{idx} Section: {r.section_title} ")
            sec_title_run.bold = True
            sec_title_run.font.size = Pt(11)

            status_run = sec_p.add_run(f"[{r.status}]")
            status_run.bold = True
            if r.status == "ACCEPTED":
                status_run.font.color.rgb = RGBColor(40, 100, 40)
            elif r.status == "REJECTED":
                status_run.font.color.rgb = RGBColor(160, 50, 50)
            else:
                status_run.font.color.rgb = RGBColor(180, 110, 20)

            info_p = doc.add_paragraph()
            info_p.add_run(f"Proposed by: {r.author}  |  Rationale: {r.rationale or 'Standard organizational alignment'}")
            info_p.runs[0].font.size = Pt(9.5)
            info_p.runs[0].font.color.rgb = RGBColor(111, 106, 97)

            # Original text
            orig_p = doc.add_paragraph()
            orig_lbl = orig_p.add_run("Original Provision:\n")
            orig_lbl.bold = True
            orig_lbl.font.size = Pt(10)
            orig_txt = orig_p.add_run(r.original_text or "")
            orig_txt.font.strike = True
            orig_txt.font.color.rgb = RGBColor(160, 50, 50)
            orig_txt.font.size = Pt(10)

            # Suggested text
            prop_p = doc.add_paragraph()
            prop_lbl = prop_p.add_run("Proposed Language:\n")
            prop_lbl.bold = True
            prop_lbl.font.size = Pt(10)
            prop_txt = prop_p.add_run(r.suggested_text or "")
            prop_txt.bold = True
            prop_txt.font.underline = True
            prop_txt.font.color.rgb = RGBColor(40, 100, 40)
            prop_txt.font.size = Pt(10)

            if r.comment:
                comm_p = doc.add_paragraph()
                comm_run = comm_p.add_run(f"Discussion Comment: {r.comment}")
                comm_run.italic = True
                comm_run.font.size = Pt(9.5)
                comm_run.font.color.rgb = RGBColor(80, 80, 80)

            doc.add_paragraph()  # Spacing between redlines

    # 2. Baseline Document Text Appendix
    h2 = doc.add_heading(level=1)
    h2_run = h2.add_run("2. Baseline Document Text")
    h2_run.font.color.rgb = RGBColor(63, 70, 52)

    baseline_text = None
    if contract.versions:
        # Latest or primary version
        v = contract.versions[0]
        baseline_text = v.normalized_text or v.raw_text

    if baseline_text:
        doc.add_paragraph(f"Extracted from version {contract.versions[0].version_number} ({contract.versions[0].filename or 'document'}):")
        doc.paragraphs[-1].runs[0].italic = True
        doc.paragraphs[-1].runs[0].font.size = Pt(9.5)

        # Add paragraphs of raw text
        for para in baseline_text.split("\n\n"):
            clean_para = para.strip()
            if clean_para:
                doc.add_paragraph(clean_para)
    else:
        doc.add_paragraph("Baseline contract text is not available for this record.").italic = True

    output_stream = io.BytesIO()
    doc.save(output_stream)
    return output_stream.getvalue()


def sanitize_filename(name: Optional[str], default_name: str = "document", max_len: int = 80) -> str:
    """
    Sanitizes string for safe filename usage in Content-Disposition headers.
    Removes path traversal, control characters, quotes, and punctuation reserved on Windows/POSIX.
    """
    import re
    if not name or not name.strip():
        return default_name
    # Strip illegal filename characters
    cleaned = re.sub(r'[\/\\:\*\?"<>|#%&\{\}\\\$\!\'\"@\+`=\n\r\t]', '_', name.strip())
    # Collapse multiple underscores/spaces
    cleaned = re.sub(r'[\s_]+', '_', cleaned).strip(' ._')
    if not cleaned:
        return default_name
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(' ._')
    return cleaned
