"""Documents API — file upload endpoint for claim document submissions."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

UPLOADS_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"

# Allowed MIME types for uploaded documents
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile):
    """
    Upload a medical document (image or PDF) for use in a claim submission.

    Returns a file_id that can be referenced in the claim documents list.
    """
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: {content_type}. "
                "Please upload a JPEG, PNG, WEBP, HEIC image, or PDF."
            ),
        )

    # Read file content and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 20 MB.",
        )

    # Generate unique file ID
    file_id = str(uuid.uuid4())

    # Determine file extension
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower() or _mime_to_ext(content_type)

    # Ensure uploads directory exists
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Save file to disk
    dest_path = UPLOADS_DIR / f"{file_id}{suffix}"
    dest_path.write_bytes(file_bytes)

    return {
        "file_id": file_id,
        "file_name": original_name,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
        "saved_path": str(dest_path.name),
    }


def _mime_to_ext(content_type: str) -> str:
    """Map MIME type to a file extension."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "application/pdf": ".pdf",
    }
    return mapping.get(content_type, ".bin")
