import sys
from unittest.mock import MagicMock

# Mock pytesseract so tests don't crash on machines without Tesseract installed
import pytesseract
pytesseract.get_tesseract_version = MagicMock(return_value="5.0.0-mock")
pytesseract.image_to_string = MagicMock(return_value="")
