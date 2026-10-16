import io
from docx import Document
from typing import Dict, Any

MAX_DOCX_PARAGRAPHS = 20_000
MAX_DOCX_CHARS = 5_000_000

def extract_text_from_docx(docx_bytes: bytes) -> Dict[str, Any]:
    """
    Extracts text paragraphs and table contents from DOCX file bytes.
    Enforces maximum paragraph and character limits to prevent memory exhaustion.
    """
    doc_stream = io.BytesIO(docx_bytes)
    doc = Document(doc_stream)
    
    full_paragraphs = []
    total_chars = 0

    for para in doc.paragraphs:
        clean = para.text.strip()
        if clean:
            total_chars += len(clean)
            if len(full_paragraphs) >= MAX_DOCX_PARAGRAPHS:
                raise ValueError(f"DOCX exceeds maximum allowable limit of {MAX_DOCX_PARAGRAPHS} paragraphs.")
            if total_chars > MAX_DOCX_CHARS:
                raise ValueError(f"DOCX text content exceeds maximum limit of {MAX_DOCX_CHARS} characters.")
            full_paragraphs.append(clean)
            
    # Also extract table text
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                total_chars += len(row_text)
                if len(full_paragraphs) >= MAX_DOCX_PARAGRAPHS:
                    raise ValueError(f"DOCX exceeds maximum allowable limit of {MAX_DOCX_PARAGRAPHS} paragraphs.")
                if total_chars > MAX_DOCX_CHARS:
                    raise ValueError(f"DOCX text content exceeds maximum limit of {MAX_DOCX_CHARS} characters.")
                full_paragraphs.append(row_text)
                
    combined_text = "\n\n".join(full_paragraphs)
    return {
        "text": combined_text,
        "paragraph_count": len(full_paragraphs),
        "char_count": len(combined_text)
    }
