import io
import os
import zipfile
from typing import Set, Tuple, Optional
from fastapi import UploadFile, HTTPException, status
from app.config import settings

CONTRACT_ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}
EVIDENCE_ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}

CANONICAL_MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg"
}

# Known dangerous executable headers to reject regardless of extension
DANGEROUS_MAGIC_HEADERS = [
    (b"MZ", "Windows PE executable"),
    (b"\x7fELF", "Linux ELF binary"),
    (b"\xca\xfe\xba\xbe", "Java class or Mach-O fat binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O 32-bit binary"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit binary"),
]


def sanitize_filename(filename: Optional[str], default_name: str = "document.pdf") -> str:
    """Sanitizes an uploaded filename preventing directory traversal or illegal characters."""
    if not filename:
        return default_name

    # Strip any directory path components
    base = os.path.basename(filename.replace("\\", "/"))
    # Replace whitespace with underscore
    clean = base.replace(" ", "_")
    # Retain only safe characters
    safe = "".join(c for c in clean if c.isalnum() or c in "._-")
    return safe if safe else default_name


def validate_file_signature(content: bytes, ext: str, strict: bool = True) -> None:
    """
    Validates binary header magic bytes against the claimed file extension.
    Throws HTTPException(415) if signatures mismatch or indicate an executable.
    When strict=False, permits clean text content for compliance evidence.
    """
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # Reject dangerous executable signatures immediately
    for magic, desc in DANGEROUS_MAGIC_HEADERS:
        if content.startswith(magic):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Rejected file containing executable signature ({desc})."
            )

    ext = ext.lower()

    if ext == ".pdf":
        if not (content.startswith(b"%PDF") or b"%PDF" in content[:1024]):
            if strict:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="File content signature does not match PDF format (missing %PDF header)."
                )
            else:
                # In non-strict evidence mode, ensure it is at least clean text without binary null bytes
                if b"\x00" in content[:8192]:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="File content signature does not match PDF format."
                    )

    elif ext == ".docx":
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content signature does not match DOCX format (missing PK zip header)."
            )
        # Deep inspect DOCX archive structure and defend against zip bombs / zip slip
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = zf.namelist()
                has_content_types = "[Content_Types].xml" in namelist
                has_word_dir = any(name.startswith("word/") for name in namelist)
                if not (has_content_types or has_word_dir):
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="Corrupted or invalid DOCX file: missing internal Word XML structures."
                    )

                # Check for zip slip path traversal in entry names
                for name in namelist:
                    parts = name.replace("\\", "/").split("/")
                    if ".." in parts or name.startswith("/") or name.startswith("\\"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Dangerous archive: path traversal detected inside document archive."
                        )

                # Check uncompressed size and compression ratio (Zip Bomb defense)
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                max_uncompressed = 60 * 1024 * 1024  # 60 MB limit for DOCX contents
                if total_uncompressed > max_uncompressed:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Decompression bomb rejected: uncompressed document size ({total_uncompressed // (1024 * 1024)} MB) exceeds 60 MB limit."
                    )
                if len(content) > 0 and (total_uncompressed / len(content)) > 100.0 and total_uncompressed > 5 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Decompression bomb rejected: excessive compression ratio detected."
                    )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Invalid DOCX document: corrupted archive structure."
            )

    elif ext == ".txt":
        # Check first 8 KB for binary null bytes
        sample = content[:8192]
        if b"\x00" in sample:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File contains binary null bytes and cannot be accepted as plain text."
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Text file encoding cannot be decoded as UTF-8 or Latin-1."
                )

    elif ext == ".png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content signature does not match PNG format."
            )

    elif ext in (".jpg", ".jpeg"):
        if not content.startswith(b"\xff\xd8\xff"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content signature does not match JPEG format."
            )


async def read_and_validate_upload(
    file: UploadFile,
    max_bytes: int = settings.MAX_UPLOAD_SIZE_BYTES,
    allowed_extensions: Set[str] = CONTRACT_ALLOWED_EXTENSIONS,
    strict_signature: bool = True
) -> Tuple[bytes, str, str]:
    """
    Safely reads an uploaded file in bounded chunks, enforcing:
    1. Maximum size limit (HTTP 413) without loading oversized files into RAM.
    2. Extension allowlist (HTTP 415).
    3. Magic bytes / file signature integrity (HTTP 415).
    4. Non-empty file requirement (HTTP 400).
    5. Filename sanitization.

    Returns:
        (file_bytes, safe_filename, canonical_mime_type)
    """
    raw_filename = file.filename or "contract.pdf"
    safe_filename = sanitize_filename(raw_filename)
    _, ext = os.path.splitext(safe_filename.lower())

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed formats: {', '.join(sorted(allowed_extensions))}."
            )
        )

    # Stream chunks up to max_bytes + 1
    chunk_size = 64 * 1024  # 64 KB
    chunks = []
    total_bytes = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Uploaded file exceeds maximum permitted size of {max_bytes // (1024 * 1024)} MB."
            )
        chunks.append(chunk)

    content = b"".join(chunks)

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # Validate signature against extension
    validate_file_signature(content, ext, strict=strict_signature)

    canonical_mime = CANONICAL_MIME_MAP.get(ext, file.content_type or "application/octet-stream")
    return content, safe_filename, canonical_mime
