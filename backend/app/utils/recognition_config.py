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

    OPTIMIZED STRATEGY (2024-05):
    - Single-stage is now preferred for most cases (faster, better multi-question handling)
    - Two-stage only for very small images (likely single questions needing high accuracy)

    Single-stage advantages:
    - 1 API call instead of N+1 (much faster for multi-question images)
    - Better context for multi-question recognition (no question confusion)
    - Simpler error handling

    Two-stage advantages:
    - Higher accuracy for single questions
    - Better for very small/cropped images
    """
    # Use image dimensions to decide
    max_dim = max(image_width, image_height)
    min_dim = min(image_width, image_height)

    # Very small images (likely single question screenshots): use two-stage for accuracy
    # But if detected 3+ questions, will auto-fallback to single-stage anyway
    if max_dim < 1000 and min_dim < 800:
        return RecognitionStrategy.TWO_STAGE

    # All other cases: use single-stage for speed and better multi-question handling
    # This includes:
    # - Medium images (1000-2000px): likely 1-3 questions
    # - Large images (2000+px): likely full pages with multiple questions
    # - PDF pages: better to recognize all at once
    return RecognitionStrategy.SINGLE_STAGE


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
