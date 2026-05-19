"""
Image preprocessing for corrected-paper recognition.

Provides:
- Red correction mark removal via HSV detection + inpainting
- Auto-rotation and perspective correction
- Shadow removal and contrast enhancement
- Correction mark detection
"""

import os
import cv2
import numpy as np
import logging
from io import BytesIO
from typing import Tuple, Optional
from ..config import UPLOAD_DIR

logger = logging.getLogger(__name__)

# Subdirectories for recognition pipeline
CLEAN_DIR = os.path.join(UPLOAD_DIR, "clean")
CROP_DIR = os.path.join(UPLOAD_DIR, "crops")


def ensure_dirs():
    """Create required subdirectories."""
    for d in [CLEAN_DIR, CROP_DIR]:
        os.makedirs(d, exist_ok=True)


def _bytes_to_cv2(image_bytes: bytes):
    """Convert image bytes to OpenCV BGR array."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片")
    return img


def _cv2_to_bytes(img, ext: str = ".jpg", quality: int = 90) -> bytes:
    """Convert OpenCV image to bytes."""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, buf = cv2.imencode(ext, img, encode_param)
    if not success:
        raise RuntimeError("图片编码失败")
    return buf.tobytes()


def remove_red_marks(image_bytes: bytes, inpaint_radius: int = 3) -> bytes:
    """Detect and remove/weaken red correction marks using HSV + inpainting.

    Steps:
    1. Convert BGR -> HSV
    2. Detect red pixels (red wraps around HSV hue 0 and 180)
    3. Dilate mask slightly to cover edges
    4. Inpaint over detected regions

    Returns cleaned image bytes.
    """
    img = _bytes_to_cv2(image_bytes)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Red has two ranges in HSV: around 0 and around 180
    lower_red_1 = np.array([0, 60, 40])
    upper_red_1 = np.array([10, 255, 255])
    lower_red_2 = np.array([170, 60, 40])
    upper_red_2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red_1, upper_red_1)
    mask2 = cv2.inRange(hsv, lower_red_2, upper_red_2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # Dilate mask to catch edges of marks
    kernel = np.ones((3, 3), np.uint8)
    red_mask = cv2.dilate(red_mask, kernel, iterations=1)

    # Inpaint to remove red marks (fill with surrounding texture)
    cleaned = cv2.inpaint(img, red_mask, inpaint_radius, cv2.INPAINT_TELEA)

    logger.info(f"Red marks removed — mask covered {cv2.countNonZero(red_mask)} pixels")
    return _cv2_to_bytes(cleaned)


def preprocess_for_ocr(image_bytes: bytes) -> bytes:
    """Apply preprocessing to improve OCR/AI recognition quality.

    Steps:
    1. Auto-rotation (deskew)
    2. Shadow removal (if needed)
    3. Contrast enhancement (CLAHE)
    4. Sharpen
    """
    img = _bytes_to_cv2(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Auto deskew
    coords = np.column_stack(np.where(gray < 128))
    if len(coords) > 100:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 1.0:
            h, w = img.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, matrix, (w, h),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
            logger.info(f"Deskewed by {angle:.1f} degrees")

    # 2. Shadow removal (convert to grayscale, apply morphological closing)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    light_bg = cv2.morphologyEx(l_channel, cv2.MORPH_CLOSE, kernel)
    light_bg = cv2.GaussianBlur(light_bg, (31, 31), 0)
    l_corrected = cv2.addWeighted(l_channel, 1.2, light_bg, -0.8, 50)
    corrected_lab = cv2.merge([l_corrected, a_channel, b_channel])
    img = cv2.cvtColor(corrected_lab, cv2.COLOR_LAB2BGR)

    # 3. CLAHE contrast enhancement on luminance
    lab2 = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l2, a2, b2 = cv2.split(lab2)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l2_eq = clahe.apply(l2)
    enhanced_lab = cv2.merge([l2_eq, a2, b2])
    img = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # 4. Light sharpen
    sharpen_kernel = np.array([
        [0, -0.5, 0],
        [-0.5, 3, -0.5],
        [0, -0.5, 0]
    ])
    img = cv2.filter2D(img, -1, sharpen_kernel)

    return _cv2_to_bytes(img)


def detect_correction_marks(image_bytes: bytes) -> dict:
    """Detect whether the image contains correction marks.

    Returns dict with:
    - has_correction_marks: bool
    - red_pixel_ratio: float (0-1)
    - has_handwriting: bool (rough heuristic)
    """
    img = _bytes_to_cv2(image_bytes)
    h, w = img.shape[:2]
    total_pixels = h * w

    # Check red pixels
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 50, 40])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([170, 50, 40])
    upper2 = np.array([180, 255, 255])
    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, lower1, upper1),
        cv2.inRange(hsv, lower2, upper2),
    )
    red_pixel_count = cv2.countNonZero(red_mask)
    red_ratio = red_pixel_count / total_pixels if total_pixels > 0 else 0

    # Check for handwriting-like content
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Count connected components (rough text/ink density heuristic)
    num_labels, _, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    ink_density = cv2.countNonZero(binary) / total_pixels if total_pixels > 0 else 0

    # Convert numpy types to Python native types for JSON serialization
    return {
        "has_correction_marks": bool(red_ratio > 0.003),
        "red_pixel_ratio": float(round(red_ratio, 5)),
        "has_handwriting": bool(ink_density > 0.12 or num_labels > 50),
        "ink_density": float(round(ink_density, 4)),
        "num_components": int(num_labels),
    }


def save_image(image_bytes: bytes, subdir: str, prefix: str = "img") -> str:
    """Save image bytes to the uploads subdirectory.

    Returns the URL path (e.g. /uploads/images/img_abc123.jpg)
    """
    import uuid
    ensure_dirs()
    target_dir = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(target_dir, exist_ok=True)
    name = f"{prefix}_{uuid.uuid4().hex[:12]}.jpg"
    path = os.path.join(target_dir, name)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return f"/uploads/{subdir}/{name}"


def crop_bbox(image_bytes: bytes, bbox: Tuple[int, int, int, int]) -> bytes:
    """Crop a region from the image given (x1, y1, x2, y2) in original coords."""
    img = _bytes_to_cv2(image_bytes)
    x1, y1, x2, y2 = bbox
    h, w = img.shape[:2]
    x1 = max(0, min(x1, w))
    x2 = max(x1 + 1, min(x2, w))
    y1 = max(0, min(y1, h))
    y2 = max(y1 + 1, min(y2, h))
    cropped = img[y1:y2, x1:x2]
    return _cv2_to_bytes(cropped)
