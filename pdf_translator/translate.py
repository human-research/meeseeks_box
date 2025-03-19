import io
import os
import time
from typing import Dict, List, Tuple

import fitz
from pdf_translator.llm import load_api_config
import requests
from PIL import Image, ImageDraw, ImageFont

from pdf_translator.text_utils import is_formula
from pdf_translator.utils import get_text_md5

def translate_text(text: str, file_md5: str, cache: Dict[str, Dict[str, str]], ignore_cache: bool = False, debug_mode: bool = False) -> str:
    """Translate text from English to Russian using custom OpenAI API endpoint with caching."""
    # Calculate text hash for cache lookup
    text_md5 = get_text_md5(text)
    
    # Check cache first if not ignoring cache
    if not ignore_cache and file_md5 in cache and text_md5 in cache[file_md5]:
        print("Cache hit! Using cached translation.")
        return cache[file_md5][text_md5]
    
    # Load API configuration
    config = load_api_config()
    api_key = config["API_KEY"]
    api_endpoint = config["OPENAI_API_ENDPOINT"]
    
    # Validate configuration
    if not api_key or not api_endpoint:
        print("Error: API configuration incomplete. Please check ~/.meeseeks_box/llm file.")
        return text  # Return original text if config is incomplete
    
    max_retries = 3
    retry_delay = 2
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"OAuth {api_key}"
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional translator from English to Russian with the specialization in informatics, math, machine learning and AI."},
            {"role": "user", "content": f"Translate the following English text to Russian, preserving formatting and structure. Do not forget about machine learning field specialization:\n\n{text}"}
        ],
        "temperature": 0.3,
        "max_tokens": 4096
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                api_endpoint,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'response' in result and 'choices' in result['response']:
                    translated = result['response']['choices'][0]['message']['content'].strip()
                else:
                    print(f"API Warning: Something with choices: {response.text}")
                    return text  # Return original text if API response is empty
                
                if debug_mode:
                    print(f"Original: {text[:50]}...")
                    print(f"Translated: {translated[:50]}...")
                
                # Add to cache
                if file_md5 not in cache:
                    cache[file_md5] = {}
                cache[file_md5][text_md5] = translated
                
                return translated
            else:
                print(f"API Error: {response.status_code}, {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return text  # Return original text if all retries fail
                    
        except Exception as e:
            print(f"Error translating text (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return text  # Return original text if all retries fail
    
    return text  # Fallback


import os
import fitz  # PyMuPDF
from typing import Dict, List, Tuple, Optional

def load_cyrillic_font():
    """Load a Cyrillic font with PyMuPDF 1.25.4."""
    print(f"PyMuPDF version: {fitz.version}")
    
    # Mac fonts with good Cyrillic support
    mac_fonts = [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        
    ]
    
    # Test each font
    for font_path in mac_fonts:
        if os.path.exists(font_path):
            print(f"Found font: {font_path}")
            return font_path
    
    print("No suitable Cyrillic font found.")
    return None


def check_font_availability() -> Dict[str, str]:
    """
    Check availability of recommended fonts for Russian text on the system
    and return a dictionary of available fonts with their paths.
    """
    # Recommended fonts in order of preference for Mac OS
    recommended_fonts = [
        # Mac OS fonts with Cyrillic support
        {"name": "Times New Roman", "paths": [
            "/Library/Fonts/Times New Roman.ttf",
            "/Library/Fonts/TimesNewRomanPSMT.ttf"
        ]},
        {"name": "Georgia", "paths": [
            "/Library/Fonts/Georgia.ttf",
            "/System/Library/Fonts/Supplemental/Georgia.ttf"
        ]},
        {"name": "Palatino", "paths": [
            "/Library/Fonts/Palatino.ttc",
            "/System/Library/Fonts/Palatino.ttc"
        ]},
        {"name": "Arial", "paths": [
            "/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial Unicode.ttf"
        ]},
        # Common Linux fonts as fallback
        {"name": "DejaVu Serif", "paths": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
        ]},
        # Windows fonts as fallback
        {"name": "Times New Roman", "paths": [
            "C:/Windows/Fonts/times.ttf"
        ]}
    ]
    
    available_fonts = {}
    
    for font in recommended_fonts:
        for path in font["paths"]:
            if os.path.exists(path):
                available_fonts[font["name"]] = path
                break
    
    return available_fonts

def fallback_insert_text_as_image(page, text: str, bbox: Tuple[float, float, float, float]) -> None:
    """
    Insert text as an image when text insertion fails.
    This is a reliable fallback for Cyrillic text.
    """
    # Get dimensions
    width = int(bbox[2] - bbox[0])
    height = int(bbox[3] - bbox[1])
    
    # Find an available font
    available_fonts = check_font_availability()
    font_path = next(iter(available_fonts.values()), None)
    
    # Create an image with the text
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use the specified font or fall back to default
    try:
        if font_path:
            font = ImageFont.truetype(font_path, 11)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Draw text in black with word wrapping
    lines = []
    words = text.split()
    current_line = []
    
    # Very simple word wrapping
    for word in words:
        test_line = ' '.join(current_line + [word])
        # Use the new method for getting text dimensions
        try:
            # For newer versions of Pillow
            left, top, right, bottom = font.getbbox(test_line)
            w = right - left
            h = bottom - top
        except AttributeError:
            # Fallback for older versions
            try:
                w, h = font.getsize(test_line)
            except:
                # Ultimate fallback: guess based on character count
                w = len(test_line) * 7  # rough estimate
                h = 12
        
        if w <= width - 10:  # 5px margin on each side
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Word is too long, add it anyway
                lines.append(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # Draw each line
    y_offset = 5
    for line in lines:
        draw.text((5, y_offset), line, font=font, fill='black')
        # Get height for next line
        try:
            # For newer versions of Pillow
            left, top, right, bottom = font.getbbox(line)
            h = bottom - top
        except AttributeError:
            # Fallback for older versions
            try:
                w, h = font.getsize(line)
            except:
                h = 12
        y_offset += h + 2
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    # Insert the image into the PDF
    page.insert_image(bbox, stream=img_bytes)


def create_clean_translated_pdf(input_pdf: str, output_pdf: str, 
                              paragraphs_by_page: Dict[int, List[Tuple[str, Tuple[float, float, float, float]]]],
                              translation_cache: Dict[str, Dict[str, str]],
                              file_md5: str, custom_font: str = None,
                              debug_mode: bool = False, start_page: int = 0, end_page: Optional[int] = None) -> None:
    """
    Create a PDF with translations while preserving images and formulas.
    """
    print(f"PyMuPDF version: {fitz.version}")
    
    # Try to load the Cyrillic font
    try:
        font = fitz.Font("tiro")
        font_loaded = True
        print("Successfully loaded tiro font")
    except Exception as e:
        print(f"Could not load tiro font: {e}")
        font_loaded = False
    
    # Open the source PDF to extract information
    src_doc = fitz.open(input_pdf)
    
    # Create a new PDF document
    dst_doc = fitz.open()
    
    # Process each page
    for page_idx in range(len(src_doc)):
        # Skip pages not in debug range if in debug mode
        if debug_mode and (page_idx < start_page or (end_page is not None and page_idx > end_page)):
            # Copy original page as-is for skipped pages
            dst_doc.insert_pdf(src_doc, from_page=page_idx, to_page=page_idx)
            continue
            
        # Get source page
        src_page = src_doc[page_idx]
        
        # Get paragraphs for this page
        paragraphs = paragraphs_by_page.get(page_idx, [])
        
        # Get all the bounding boxes for text that should be translated
        text_bboxes = [bbox for _, bbox in paragraphs]
        
        # Create a copy of the original page first
        # This ensures we preserve all non-text elements (images, formulas, graphics)
        temp_doc = fitz.open()
        temp_page = temp_doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
        temp_page.show_pdf_page(temp_page.rect, src_doc, page_idx)
        
        # Now create a new page for our final output
        dst_page = dst_doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
        
        # We need to copy the original page content, but then clear out the text areas
        # that we want to replace with translations
        
        # First, render the original page to an image to preserve all non-text elements
        pix = src_page.get_pixmap(alpha=False)
        
        # Create a mask for the text areas we want to replace
        mask_doc = fitz.open()
        mask_page = mask_doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
        
        # Draw white rectangles for the text areas we want to preserve
        for bbox in text_bboxes:
            mask_page.draw_rect(fitz.Rect(bbox), color=(1, 1, 1), fill=(1, 1, 1))
        
        # Render the mask to an image
        mask_pix = mask_page.get_pixmap(alpha=False)
        
        # Now draw the masked original page to our destination
        dst_page.insert_image(dst_page.rect, stream=pix.tobytes("png"))
        
        # If font was loaded successfully, insert it into the page
        if font_loaded:
            try:
                dst_page.insert_font(fontname="F0", fontbuffer=font.buffer)
                font_name = "F0"
                print("Successfully inserted font into page")
            except Exception as e:
                print(f"Could not insert font into page: {e}")
                font_name = "tiro"  # Fallback to built-in
        else:
            font_name = "tiro"  # Use built-in
        
        # Now add translated text in the text areas
        for i, (text, bbox) in enumerate(paragraphs):
            # Determine if this is likely a formula
            if is_formula(text):
                print(f"Skipping formula in paragraph {i+1}")
                continue
            
            # Get translation
            text_md5 = get_text_md5(text)
            if file_md5 in translation_cache and text_md5 in translation_cache[file_md5]:
                translated_text = translation_cache[file_md5][text_md5]
            else:
                print(f"Warning: Translation not found for paragraph {i+1}. Using original text.")
                translated_text = text
            
            # Find best font size that fits
            best_font_size = None
            
            for font_size in [11, 10, 9, 8, 7, 6]:
                # Create a temporary document to test text fitting
                test_doc = fitz.open()
                test_page = test_doc.new_page(width=10000, height=10000)  # Large page to ensure fitting
                
                # Insert font if needed
                if font_loaded:
                    try:
                        test_page.insert_font(fontname="F0", fontbuffer=font.buffer)
                    except:
                        pass
                
                # Calculate line height based on font size
                line_height = font_size + 2
                
                # Calculate starting position
                x = 50  # Arbitrary position for test
                y = 50 + font_size
                
                # Split text into words for manual wrapping
                words = translated_text.split()
                line = []
                max_width = bbox[2] - bbox[0] - 4  # Width with margins
                
                current_y = y
                fits = True
                
                # Process each word for this font size
                for word in words:
                    if not line:  # First word on the line
                        line.append(word)
                    else:
                        # Check if word fits on current line
                        test_line = ' '.join(line + [word])
                        # Estimate text width - character count * font size * factor
                        width_factor = 0.5  # Adjust based on font characteristics
                        if len(test_line) * font_size * width_factor < max_width:
                            line.append(word)
                        else:
                            # Line is full, render it
                            try:
                                test_page.insert_text((x, current_y), ' '.join(line), 
                                                   fontname=font_name, fontsize=font_size)
                            except Exception as e:
                                print(f"Error rendering line: {e}")
                                fits = False
                                break
                                
                            line = [word]  # Start new line with current word
                            current_y += line_height
                            
                            # Check if we've gone beyond the bbox height
                            if (current_y - y) > (bbox[3] - bbox[1] - 5):
                                fits = False
                                break
                
                # Render the last line if there is one and we still fit
                if line and fits:
                    try:
                        test_page.insert_text((x, current_y), ' '.join(line), 
                                           fontname=font_name, fontsize=font_size)
                    except:
                        fits = False
                
                # If everything fit, save this as our best option
                if fits:
                    best_font_size = font_size
                    test_doc.close()
                    break  # We found a good size, no need to try smaller
                
                # Close the test document if not successful
                test_doc.close()
            
            # Use the best result if we found one
            if best_font_size:
                print(f"Success with font size {best_font_size} for paragraph {i+1}")
                
                # Cover original text with white rectangle
                dst_page.draw_rect(fitz.Rect(bbox), color=(1, 1, 1), fill=(1, 1, 1))
                
                # Add the translated text
                x = bbox[0] + 2
                y = bbox[1] + best_font_size
                line_height = best_font_size + 2
                
                words = translated_text.split()
                line = []
                max_width = bbox[2] - bbox[0] - 4
                current_y = y
                
                for word in words:
                    if not line:
                        line.append(word)
                    else:
                        test_line = ' '.join(line + [word])
                        width_factor = 0.5
                        if len(test_line) * best_font_size * width_factor < max_width:
                            line.append(word)
                        else:
                            # Render the line
                            dst_page.insert_text((x, current_y), ' '.join(line), 
                                             fontname=font_name, fontsize=best_font_size)
                            line = [word]
                            current_y += line_height
                
                # Render the last line if there is one
                if line:
                    dst_page.insert_text((x, current_y), ' '.join(line), 
                                     fontname=font_name, fontsize=best_font_size)
            else:
                print(f"Warning: Could not fit text for paragraph {i+1}")
        
        # Clean up temporary documents
        temp_doc.close()
        mask_doc.close()
    
    # Save the new PDF
    dst_doc.save(output_pdf)
    dst_doc.close()
    src_doc.close()
    
    print(f"Translation completed. Output saved to {output_pdf}")
    