"""Test Tesseract configuration"""
import os
import pytesseract
from PIL import Image

# Configure Tesseract path
if os.name == 'nt':  # Windows
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"[OK] Tesseract path configured: {tesseract_path}")
    else:
        print(f"[ERROR] Tesseract not found at: {tesseract_path}")

# Test Tesseract
try:
    version = pytesseract.get_tesseract_version()
    print(f"[OK] Tesseract version: {version}")

    # Test with a simple image
    img = Image.new('RGB', (200, 50), color='white')
    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
    print(f"[OK] OCR test successful")

    # List available languages
    langs = pytesseract.get_languages()
    print(f"[OK] Available languages: {langs}")

except Exception as e:
    print(f"[ERROR] Tesseract test failed: {e}")
