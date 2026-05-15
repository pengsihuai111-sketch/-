"""
Image quality analysis and enhancement for better OCR/recognition accuracy.
"""
import io
import logging
from typing import Dict, List
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)


def analyze_image_quality(image_bytes: bytes) -> Dict:
    """分析图像质量，给出改进建议

    Args:
        image_bytes: 图像字节数据

    Returns:
        质量分析结果字典，包含：
        - is_blurry: 是否模糊
        - blur_score: 模糊度分数（越高越清晰）
        - is_too_dark: 是否过暗
        - is_too_bright: 是否过亮
        - brightness: 亮度值
        - is_low_contrast: 是否低对比度
        - contrast: 对比度值
        - is_skewed: 是否倾斜
        - skew_angle: 倾斜角度
        - warnings: 警告信息列表
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # 转换为灰度图进行分析
        if img.mode != 'L':
            gray = img.convert('L')
        else:
            gray = img

        np_img = np.array(gray)

        # 检测模糊度（使用拉普拉斯方差）
        laplacian_var = cv2.Laplacian(np_img, cv2.CV_64F).var()
        is_blurry = laplacian_var < 100

        # 检测亮度
        mean_brightness = float(np_img.mean())
        is_too_dark = mean_brightness < 80
        is_too_bright = mean_brightness > 200

        # 检测对比度
        contrast = float(np_img.std())
        is_low_contrast = contrast < 40

        # 检测倾斜（使用霍夫变换检测直线）
        is_skewed = False
        avg_angle = 0.0
        try:
            edges = cv2.Canny(np_img, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, 100)

            if lines is not None and len(lines) > 0:
                angles = []
                for line in lines[:10]:  # 只检查前10条线
                    rho, theta = line[0]
                    angle = np.degrees(theta) - 90
                    if abs(angle) < 45:  # 只考虑接近水平的线
                        angles.append(angle)

                if angles:
                    avg_angle = float(np.mean(angles))
                    is_skewed = abs(avg_angle) > 2  # 倾斜超过2度
        except Exception as e:
            logger.warning(f"Skew detection failed: {e}")

        # 生成警告信息
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
            warnings.append(f"图片倾斜约{abs(avg_angle):.1f}度")

        return {
            "is_blurry": bool(is_blurry),
            "blur_score": float(laplacian_var),
            "is_too_dark": bool(is_too_dark),
            "is_too_bright": bool(is_too_bright),
            "brightness": float(mean_brightness),
            "is_low_contrast": bool(is_low_contrast),
            "contrast": float(contrast),
            "is_skewed": bool(is_skewed),
            "skew_angle": float(avg_angle),
            "warnings": warnings,
        }
    except Exception as e:
        logger.error(f"Image quality analysis failed: {e}", exc_info=True)
        return {
            "is_blurry": False,
            "blur_score": 0,
            "is_too_dark": False,
            "is_too_bright": False,
            "brightness": 0,
            "is_low_contrast": False,
            "contrast": 0,
            "is_skewed": False,
            "skew_angle": 0,
            "warnings": ["图像质量分析失败"],
        }


def enhance_image(image_bytes: bytes, quality_info: Dict) -> bytes:
    """根据质量分析结果自动增强图像

    Args:
        image_bytes: 原始图像字节数据
        quality_info: 质量分析结果

    Returns:
        增强后的图像字节数据
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        np_img = np.array(img)

        # 如果是彩色图，转换为灰度图（数学题通常不需要颜色）
        if len(np_img.shape) == 3:
            np_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

        logger.info(f"Enhancing image with quality issues: {quality_info['warnings']}")

        # 矫正倾斜
        if quality_info["is_skewed"]:
            angle = quality_info["skew_angle"]
            logger.info(f"Correcting skew: {angle:.2f} degrees")
            (h, w) = np_img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            np_img = cv2.warpAffine(
                np_img, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )

        # 增强对比度（使用CLAHE - 自适应直方图均衡化）
        if quality_info["is_low_contrast"]:
            logger.info("Enhancing contrast using CLAHE")
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            np_img = clahe.apply(np_img)

        # 调整亮度
        if quality_info["is_too_dark"]:
            logger.info("Brightening dark image")
            np_img = cv2.convertScaleAbs(np_img, alpha=1.3, beta=30)
        elif quality_info["is_too_bright"]:
            logger.info("Darkening bright image")
            np_img = cv2.convertScaleAbs(np_img, alpha=0.8, beta=-20)

        # 去噪（如果图像模糊）
        if quality_info["is_blurry"]:
            logger.info("Applying denoising")
            np_img = cv2.fastNlMeansDenoising(np_img, h=10)

        # 锐化
        logger.info("Applying sharpening")
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        np_img = cv2.filter2D(np_img, -1, kernel)

        # 转回PIL Image
        enhanced_img = Image.fromarray(np_img)

        # 保存为JPEG
        buf = io.BytesIO()
        enhanced_img.save(buf, format="JPEG", quality=95)

        logger.info("Image enhancement completed")
        return buf.getvalue()

    except Exception as e:
        logger.error(f"Image enhancement failed: {e}", exc_info=True)
        # 如果增强失败，返回原图
        return image_bytes


def should_enhance(quality_info: Dict) -> bool:
    """判断是否需要增强图像

    Args:
        quality_info: 质量分析结果

    Returns:
        是否需要增强
    """
    return (
        quality_info["is_blurry"] or
        quality_info["is_too_dark"] or
        quality_info["is_too_bright"] or
        quality_info["is_low_contrast"] or
        quality_info["is_skewed"]
    )
