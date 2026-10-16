import pymupdf as fitz
from typing import Dict, Any

MAX_PDF_PAGES = 250
MAX_PDF_CHARS = 5_000_000

def extract_text_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extracts text, page count, and layout blocks from PDF using PyMuPDF.
    Enforces maximum page count and total character limits to prevent resource exhaustion.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_count = len(doc)
        if page_count > MAX_PDF_PAGES:
            raise ValueError(
                f"PDF exceeds maximum allowable limit of {MAX_PDF_PAGES} pages (document contains {page_count} pages)."
            )

        full_text_list = []
        total_chars = 0

        for page_num in range(page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                clean_text = text.strip()
                total_chars += len(clean_text)
                if total_chars > MAX_PDF_CHARS:
                    raise ValueError(
                        f"PDF text content exceeds maximum limit of {MAX_PDF_CHARS} characters."
                    )
                full_text_list.append(clean_text)

        combined_text = "\n\n".join(full_text_list)
        return {
            "text": combined_text,
            "page_count": page_count,
            "char_count": len(combined_text)
        }
    finally:
        doc.close()
