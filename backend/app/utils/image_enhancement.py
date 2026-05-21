"""
Image quality analysis and optional enhancement helpers.

This module must stay import-safe even when optional native dependencies
such as numpy or OpenCV are not installed. In that case we gracefully
degrade to lightweight PIL-based checks so OCR/recognition still works.
"""
import io
import logging
from typing import Dict

from PIL import Image, ImageStat

logger = logging.getLogger(__name__)

try:
    import numpy as np
except ImportError:  # pragma: no cover - depends on runtime environment
    np = None

try:
    import cv2
except ImportError:  # pragma: no cover - depends on runtime environment
    cv2 = None


def _optional_deps_available() -> bool:
    """Whether advanced image analysis/enhancement dependencies are available."""
    return np is not None and cv2 is not None


def analyze_image_quality(image_bytes: bytes) -> Dict:
    """Analyze image quality and return safe defaults when deps are missing."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        gray = img.convert("L")

        stats = ImageStat.Stat(gray)
        mean_brightness = float(stats.mean[0]) if stats.mean else 0.0
        contrast = float(stats.stddev[0]) if stats.stddev else 0.0

        is_too_dark = mean_brightness < 80
        is_too_bright = mean_brightness > 200
        is_low_contrast = contrast < 40

        is_blurry = False
        blur_score = 0.0
        is_skewed = False
        avg_angle = 0.0

        if _optional_deps_available():
            np_img = np.array(gray)

            blur_score = float(cv2.Laplacian(np_img, cv2.CV_64F).var())
            is_blurry = blur_score < 100

            try:
                edges = cv2.Canny(np_img, 50, 150, apertureSize=3)
                lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

                if lines is not None and len(lines) > 0:
                    angles = []
                    for line in lines[:10]:
                        _, theta = line[0]
                        angle = np.degrees(theta) - 90
                        if abs(angle) < 45:
                            angles.append(angle)

                    if angles:
                        avg_angle = float(np.mean(angles))
                        is_skewed = abs(avg_angle) > 2
            except Exception as exc:
                logger.warning("Skew detection failed: %s", exc)
        else:
            logger.warning(
                "Advanced image enhancement dependencies are unavailable. "
                "Continuing with basic PIL-based quality checks only."
            )

        warnings = []
        if is_blurry:
            warnings.append("图片模糊，可能影响识别准确率")
        if is_too_dark:
            warnings.append("图片过暗，建议在光线充足的环境下拍摄")
        if is_too_bright:
            warnings.append("图片过亮，建议避免强光直射")
        if is_low_contrast:
            warnings.append("图片对比度低，建议使用深色笔迹")
        if is_skewed:
            warnings.append(f"图片倾斜约 {abs(avg_angle):.1f} 度")
        if not _optional_deps_available():
            warnings.append("当前环境未安装图像增强依赖，已自动使用兼容模式识别")

        return {
            "is_blurry": bool(is_blurry),
            "blur_score": float(blur_score),
            "is_too_dark": bool(is_too_dark),
            "is_too_bright": bool(is_too_bright),
            "brightness": float(mean_brightness),
            "is_low_contrast": bool(is_low_contrast),
            "contrast": float(contrast),
            "is_skewed": bool(is_skewed),
            "skew_angle": float(avg_angle),
            "warnings": warnings,
        }
    except Exception as exc:
        logger.error("Image quality analysis failed: %s", exc, exc_info=True)
        return {
            "is_blurry": False,
            "blur_score": 0.0,
            "is_too_dark": False,
            "is_too_bright": False,
            "brightness": 0.0,
            "is_low_contrast": False,
            "contrast": 0.0,
            "is_skewed": False,
            "skew_angle": 0.0,
            "warnings": ["图像质量分析失败"],
        }


def enhance_image(image_bytes: bytes, quality_info: Dict) -> bytes:
    """Enhance image when optional deps exist, otherwise return original bytes."""
    if not _optional_deps_available():
        logger.warning(
            "Skipping image enhancement because numpy/OpenCV are not installed."
        )
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        np_img = np.array(img)

        if len(np_img.shape) == 3:
            np_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

        logger.info(
            "Enhancing image with quality issues: %s",
            quality_info.get("warnings", []),
        )

        if quality_info.get("is_skewed"):
            angle = float(quality_info.get("skew_angle", 0.0))
            logger.info("Correcting skew: %.2f degrees", angle)
            height, width = np_img.shape[:2]
            center = (width // 2, height // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            np_img = cv2.warpAffine(
                np_img,
                matrix,
                (width, height),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

        if quality_info.get("is_low_contrast"):
            logger.info("Enhancing contrast using CLAHE")
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            np_img = clahe.apply(np_img)

        if quality_info.get("is_too_dark"):
            logger.info("Brightening dark image")
            np_img = cv2.convertScaleAbs(np_img, alpha=1.3, beta=30)
        elif quality_info.get("is_too_bright"):
            logger.info("Darkening bright image")
            np_img = cv2.convertScaleAbs(np_img, alpha=0.8, beta=-20)

        if quality_info.get("is_blurry"):
            logger.info("Applying denoising")
            np_img = cv2.fastNlMeansDenoising(np_img, h=10)

        logger.info("Applying sharpening")
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        np_img = cv2.filter2D(np_img, -1, kernel)

        enhanced_img = Image.fromarray(np_img)
        buffer = io.BytesIO()
        enhanced_img.save(buffer, format="JPEG", quality=95)

        logger.info("Image enhancement completed")
        return buffer.getvalue()
    except Exception as exc:
        logger.error("Image enhancement failed: %s", exc, exc_info=True)
        return image_bytes


def should_enhance(quality_info: Dict) -> bool:
    """Whether the image should be enhanced in the current runtime."""
    if not _optional_deps_available():
        return False

    return any(
        quality_info.get(flag, False)
        for flag in (
            "is_blurry",
            "is_too_dark",
            "is_too_bright",
            "is_low_contrast",
            "is_skewed",
        )
    )
