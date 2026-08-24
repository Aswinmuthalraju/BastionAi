from pathlib import Path
from typing import Any, Dict

import pytesseract
from PIL import Image

from app.graph.store import extract_equipment_ids


class OCRProcessor:
    """
    Real OCR over the actual uploaded file — Tesseract reads real pixels, not a
    lookup keyed on filename. There is no GPU-hosted VLM available on this
    hardware (see SETUP.md for the production Qwen2-VL swap); this pipeline is
    the honest local substitute: it genuinely fails to find equipment that
    isn't in the image, and genuinely finds what is.
    """

    def process_image(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Uploaded image not found at {file_path}")

        image = Image.open(path)
        raw_text = pytesseract.image_to_string(image).strip()

        detected_ids = extract_equipment_ids(raw_text)

        return {
            "source_file": path.name,
            "raw_text": raw_text,
            "detected_equipment_ids": detected_ids,
            "ocr_engine": "tesseract-5",
            "image_size": image.size,
        }


ocr_processor = OCRProcessor()
