from typing import Dict, Any
from app.services.parsing.pdf_parser import extract_text_from_pdf
from app.services.parsing.docx_parser import extract_text_from_docx

def parse_document_file(file_bytes: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
    """
    Parses PDF, DOCX, or plain text into normalized text and metadata.
    """
    lower_name = filename.lower()
    
    if lower_name.endswith(".pdf") or "pdf" in mime_type:
        return extract_text_from_pdf(file_bytes)
    elif lower_name.endswith(".docx") or "officedocument" in mime_type:
        return extract_text_from_docx(file_bytes)
    else:
        # Fallback to UTF-8 text decode
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="replace")
            
        return {
            "text": text.strip(),
            "char_count": len(text)
        }
