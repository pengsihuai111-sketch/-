"""Recognition configuration and strategy settings."""
import os
from enum import Enum


class RecognitionStrategy(str, Enum):
    """Recognition strategy options."""
    TWO_STAGE = "two_stage"  # Detect then recognize (recommended for PDFs)
    SINGLE_STAGE = "single_stage"  # Direct full-image recognition (faster)
    AUTO = "auto"  # Automatically choose based on image characteristics


# Default strategy
DEFAULT_STRATEGY = RecognitionStrategy.AUTO

# Cropping behavior for two-stage recognition
# When False, uses full image with question number hints (recommended for PDFs)
# When True, crops to detected bbox (may cause incomplete questions)
USE_BBOX_CROPPING = False

# Strategy selection based on image characteristics
def select_strategy(image_width: int, image_height: int, filename: str = "") -> RecognitionStrategy:
    """Automatically select recognition strategy based on image characteristics.

    Two-stage is better for:
    - Large images (likely full pages with multiple questions)
    - PDF pages
    - Images with high resolution

    Single-stage is better for:
    - Small images (likely single questions or screenshots)
    - Low resolution images
    - Quick recognition needs
    """
    # Force two-stage for PDF pages
    if filename and "page_" in filename.lower():
        return RecognitionStrategy.TWO_STAGE

    # Use image dimensions to decide
    max_dim = max(image_width, image_height)
    min_dim = min(image_width, image_height)

    # Large, high-resolution images likely contain multiple questions
    if max_dim > 2000 or (max_dim > 1500 and min_dim > 1000):
        return RecognitionStrategy.TWO_STAGE

    # Small images likely contain single questions
    if max_dim < 1200:
        return RecognitionStrategy.SINGLE_STAGE

    # Medium-sized images: use two-stage for better accuracy
    return RecognitionStrategy.TWO_STAGE


# Quality thresholds
MIN_CONFIDENCE_THRESHOLD = 0.7  # Questions below this need review
MIN_QUESTION_TEXT_LENGTH = 5  # Minimum chars for valid question
MIN_ANSWER_LENGTH = 1  # Minimum chars for valid answer
MIN_SOLUTION_LENGTH = 10  # Minimum chars for valid solution

# Image quality requirements
MIN_IMAGE_WIDTH = 600  # Warn if smaller
MIN_IMAGE_HEIGHT = 600  # Warn if smaller
RECOMMENDED_IMAGE_WIDTH = 1200  # Recommended minimum
RECOMMENDED_IMAGE_HEIGHT = 1200  # Recommended minimum

# API retry settings
MAX_RETRIES = 2  # Number of retries on API failure
RETRY_DELAY = 1.0  # Seconds between retries

# Parallel processing limits
MAX_PARALLEL_RECOGNITIONS = 3  # Max concurrent API calls for multi-question recognition
