from typing import Dict, List, Tuple

from chardet import detect
import fitz


def is_formula(text: str) -> bool:
    """Simple heuristic to detect if text is likely a formula."""
    # Check for common formula indicators
    formula_indicators = ['=', '+', '-', '*', '/', '^', '∫', '∑', '∏', '√', '≈', '≠', '≤', '≥']
    math_symbols_count = sum(1 for char in text if char in formula_indicators)
    
    # If there are multiple math symbols and few words, likely a formula
    words = len(text.split())
    return (math_symbols_count > 1 and words < 5) or (math_symbols_count / len(text) > 0.05)

def extract_paragraphs(pdf_path: str,
                       debug_mode: bool = False, start_page: int = None, end_page: int = None
                       ) -> Dict[int, List[Tuple[str, Tuple[float, float, float, float]]]]:
    """
    Extract paragraphs and their bounding boxes from a PDF file.
    Returns a dictionary mapping page numbers to lists of (text, bbox) tuples.
    """
    paragraphs_by_page = {}
    
    # Open the PDF file
    doc = fitz.open(pdf_path)
    
    for page_num, page in enumerate(doc):
        # Skip pages not in debug range if in debug mode
        if debug_mode and (page_num < start_page or page_num > end_page):
            paragraphs_by_page[page_num] = []
            continue
            
        text_blocks = page.get_text("blocks")
        paragraphs = []
        
        for block in text_blocks:
            if block[6] == 0:  # Text blocks have type 0
                text = block[4]
                if text.strip():
                    try:
                        # Skip if not English or if it's a formula (simple heuristic)
                        if len(text.strip()) > 10 and not is_formula(text):
                            lang = detect(text)
                            if lang == 'en':
                                # Store text with its bounding box (x0, y0, x1, y1)
                                paragraphs.append((text, (block[0], block[1], block[2], block[3])))
                    except:
                        # If language detection fails, include it anyway
                        if len(text.strip()) > 10:
                            paragraphs.append((text, (block[0], block[1], block[2], block[3])))
        
        paragraphs_by_page[page_num] = paragraphs
    
    doc.close()
    return paragraphs_by_page