import io
import os
from typing import Dict, List, Tuple

from chardet import detect
import fitz

import pytesseract

from pdf_translator.text_utils import is_formula
from pdf_translator.translate import translate_text


def is_image_based_pdf(pdf_path: str, threshold: float = 0.3) -> bool:
    """
    Determine if a PDF is primarily image-based.
    Returns True if the PDF seems to be primarily images, False if it's primarily text.
    
    Args:
        pdf_path: Path to the PDF file
        threshold: Ratio of text blocks to total blocks below which PDF is considered image-based
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    text_content_ratio = 0
    
    for page_num in range(min(total_pages, 5)):  # Check first 5 pages or fewer
        page = doc[page_num]
        
        # Get text blocks
        text_blocks = page.get_text("blocks")
        text_blocks_count = sum(1 for block in text_blocks if block[6] == 0)
        
        # Get image blocks
        image_blocks = len(page.get_images(full=True))
        
        # Calculate ratio for this page
        if text_blocks_count + image_blocks > 0:
            page_ratio = text_blocks_count / (text_blocks_count + image_blocks)
            text_content_ratio += page_ratio
    
    # Average ratio across sampled pages
    avg_ratio = text_content_ratio / min(total_pages, 5)
    doc.close()
    
    # If avg_ratio is low, it means there are few text blocks compared to total blocks
    return avg_ratio < threshold

def extract_text_with_ocr(pdf_path: str, 
                          debug_mode: bool = False, start_page: int = None, end_page: int = None
                          ) -> Dict[int, List[Tuple[str, Tuple[float, float, float, float]]]]:
    """
    Extract text from a PDF using OCR for image-based PDFs.
    Returns a dictionary mapping page numbers to lists of (text, bbox) tuples.
    """
    from pdf2image import convert_from_path
    
    paragraphs_by_page = {}
    
    # Convert PDF pages to images
    images = convert_from_path(pdf_path, dpi=300)
    
    for page_num, image in enumerate(images):
        # Skip pages not in debug range if in debug mode
        if debug_mode and (page_num < start_page or page_num > end_page):
            paragraphs_by_page[page_num] = []
            continue
        
        # Perform OCR to extract text and bounding boxes
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang='eng')
        
        paragraphs = []
        current_paragraph = []
        current_bbox = None
        
        # Group OCR results into paragraphs
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i]
            if text.strip():
                x = ocr_data['left'][i]
                y = ocr_data['top'][i]
                w = ocr_data['width'][i]
                h = ocr_data['height'][i]
                
                if current_bbox is None:
                    current_bbox = [x, y, x + w, y + h]
                else:
                    # Expand bounding box
                    current_bbox[0] = min(current_bbox[0], x)
                    current_bbox[1] = min(current_bbox[1], y)
                    current_bbox[2] = max(current_bbox[2], x + w)
                    current_bbox[3] = max(current_bbox[3], y + h)
                
                current_paragraph.append(text)
            elif current_paragraph:
                # End of paragraph, add it
                paragraph_text = ' '.join(current_paragraph)
                
                # Skip if the paragraph is very short or likely a formula
                if len(paragraph_text.strip()) > 10 and not is_formula(paragraph_text):
                    try:
                        lang = detect(paragraph_text)
                        if lang == 'en':
                            paragraphs.append((paragraph_text, tuple(current_bbox)))
                    except:
                        # If language detection fails, include it anyway
                        paragraphs.append((paragraph_text, tuple(current_bbox)))
                
                current_paragraph = []
                current_bbox = None
        
        # Add final paragraph if exists
        if current_paragraph:
            paragraph_text = ' '.join(current_paragraph)
            if len(paragraph_text.strip()) > 10 and not is_formula(paragraph_text):
                try:
                    lang = detect(paragraph_text)
                    if lang == 'en':
                        paragraphs.append((paragraph_text, tuple(current_bbox)))
                except:
                    paragraphs.append((paragraph_text, tuple(current_bbox)))
        
        paragraphs_by_page[page_num] = paragraphs
    
    return paragraphs_by_page

def create_translated_pdf_ocr_approach(input_pdf: str, output_pdf: str, paragraphs_by_page: Dict[int, List[Tuple[str, Tuple[float, float, float, float]]]],
                                       debug_mode: bool = False, start_page: int = None, end_page: int = None
                                       ) -> None:
    """Create a new PDF with translated text using a completely different approach that works with Cyrillic."""
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from PyPDF2 import PdfReader, PdfWriter
    
    # Find a font that supports Cyrillic characters
    font_path = None
    possible_fonts = [
        # Linux fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # MacOS fonts
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        # Windows fonts
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/times.ttf",
    ]
    
    for path in possible_fonts:
        if os.path.exists(path):
            font_path = path
            break
    
    if font_path:
        print(f"Using font: {font_path} for Russian text")
        # Register the font
        pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
    else:
        print("Warning: Could not find a font that supports Cyrillic characters")
        return  # Exit if no suitable font is found
    
    # Open the original PDF
    with fitz.open(input_pdf) as doc:
        # Create a PDF writer for the output
        pdf_writer = PdfWriter()
        
        # Create a PDF reader for the input
        pdf_reader = PdfReader(input_pdf)
        
        # Process each page
        for page_num in range(len(doc)):
            if debug_mode and (page_num < start_page or page_num > end_page):
                # Just copy the original page
                pdf_writer.add_page(pdf_reader.pages[page_num])
                continue
            
            page = doc[page_num]
            paragraphs = paragraphs_by_page.get(page_num, [])
            
            if not paragraphs:
                # No paragraphs to translate, just copy the original page
                pdf_writer.add_page(pdf_reader.pages[page_num])
                continue
            
            # Get page dimensions
            width, height = page.rect.width, page.rect.height
            
            # Create a new page in memory
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=(width, height))
            
            # First render the original page as background
            page_pixmap = page.get_pixmap()
            img_data = page_pixmap.tobytes("jpeg")
            
            # Save the image to a temporary file and then load it
            temp_img_path = f"temp_page_{page_num}.jpg"
            with open(temp_img_path, 'wb') as img_file:
                img_file.write(img_data)
            
            # Draw the background image
            c.drawImage(temp_img_path, 0, 0, width=width, height=height)
            
            # Now add the translated text on top
            c.setFont('CyrillicFont', 11)
            
            for i, (text, bbox) in enumerate(paragraphs):
                print(f"Translating paragraph {i+1}/{len(paragraphs)} on page {page_num+1}...")
                translated_text = translate_text(text)
                
                # Draw white rectangle to cover original text
                c.setFillColorRGB(1, 1, 1)
                c.rect(bbox[0], height - bbox[3], bbox[2] - bbox[0], bbox[3] - bbox[1], fill=True)
                
                # Add translated text
                c.setFillColorRGB(0, 0, 0)
                
                # Split text into lines with simple word wrapping
                text_width = bbox[2] - bbox[0] - 4  # Subtract margins
                words = translated_text.split()
                lines = []
                current_line = []
                
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    if c.stringWidth(test_line, 'CyrillicFont', 11) <= text_width:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            # Word is too long for the line, add it anyway
                            lines.append(word)
                            current_line = []
                
                if current_line:
                    lines.append(' '.join(current_line))
                
                # Draw each line of text
                line_height = 14  # Adjust based on font size
                for j, line in enumerate(lines):
                    y_pos = height - bbox[1] - (j+1) * line_height
                    if y_pos > height - bbox[3]:  # Make sure we don't go out of the box
                        c.drawString(bbox[0] + 2, y_pos, line)
                    else:
                        # If we run out of space, add ellipsis to the last visible line
                        if j > 0:  # Not the first line
                            last_line_pos = height - bbox[1] - j * line_height
                            # Backtrack and add ellipsis to the last line
                            c.drawString(bbox[0] + 2, last_line_pos, "...")
                        break
            
            c.save()
            
            # Get the PDF content from the canvas
            packet.seek(0)
            new_page = PdfReader(packet).pages[0]
            
            # Add the new page to the output PDF
            pdf_writer.add_page(new_page)
            
            # Clean up the temporary image file
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)
        
        # Save the output PDF
        with open(output_pdf, 'wb') as output_file:
            pdf_writer.write(output_file)
    
    print(f"Translation completed. Output saved to {output_pdf}")
