from __future__ import annotations
from pathlib import Path
import cv2 as cv
import numpy as np

def list_images(folder: Path, recursive: bool) -> list[Path]:
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tif", "*.tiff", "*.webp"]
    iterator = folder.rglob if recursive else folder.glob
    files: list[Path] = []
    for pattern in patterns:
        files.extend(iterator(pattern))
    return sorted(set(files))

def load_bgr(path: Path, max_side: int) -> np.ndarray:
    image = cv.imread(str(path), cv.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to read image: {path}")

    if max(image.shape[:2]) > max_side:
        h, w = image.shape[:2]
        scale = max_side / float(max(h, w))
        image = cv.resize(image, (int(w * scale), int(h * scale)), interpolation=cv.INTER_AREA)
    return image

def compose_compare(original: np.ndarray, rendered: np.ndarray) -> np.ndarray:
    if original.shape[:2] != rendered.shape[:2]:
        rendered = cv.resize(rendered, (original.shape[1], original.shape[0]), interpolation=cv.INTER_AREA)
    label_h = max(26, original.shape[0] // 18)
    panel = np.full((label_h, original.shape[1] * 2, 3), 245, dtype=np.uint8)
    cv.putText(panel, "Original", (10, int(label_h * 0.75)), cv.FONT_HERSHEY_SIMPLEX, 0.6, (15, 15, 15), 2)
    cv.putText(
        panel,
        "Anigine",
        (original.shape[1] + 10, int(label_h * 0.75)),
        cv.FONT_HERSHEY_SIMPLEX,
        0.6,
        (15, 15, 15),
        2,
    )
    body = np.hstack([original, rendered])
    return np.vstack([panel, body])

def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv.imwrite(str(path), image):
        raise RuntimeError(f"Failed to write image: {path}")

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def _odd_ksize(value: int, minimum: int = 3) -> int:
    value = max(minimum, value)
    return value if value % 2 == 1 else value + 1
