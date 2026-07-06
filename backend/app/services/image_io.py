from io import BytesIO
from pathlib import Path

import cv2
import fitz
import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from app.config import MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS


def validate_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Use one of: {allowed}.")
    return suffix


async def read_upload_bytes(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{file.filename} is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{file.filename} exceeds the 25 MB upload limit.")
    return data


def upload_to_bgr(data: bytes, suffix: str) -> np.ndarray:
    if suffix == ".pdf":
        return _pdf_first_page_to_bgr(data)
    return _image_bytes_to_bgr(data)


def _image_bytes_to_bgr(data: bytes) -> np.ndarray:
    try:
        image = Image.open(BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read image file.") from exc

    rgb = np.array(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _pdf_first_page_to_bgr(data: bytes) -> np.ndarray:
    try:
        document = fitz.open(stream=data, filetype="pdf")
        if document.page_count == 0:
            raise ValueError("empty PDF")
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not render the first page of the PDF.") from exc
    finally:
        try:
            document.close()
        except Exception:
            pass

    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
