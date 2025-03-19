import argparse
import os
import json

from pdf_translator.llm import load_api_config
from pdf_translator.ocr import create_translated_pdf_ocr_approach, extract_text_with_ocr, is_image_based_pdf
from pdf_translator.text_utils import extract_paragraphs
from pdf_translator.translate import create_clean_translated_pdf, translate_text
from pdf_translator.utils import get_file_md5, get_text_md5, load_translation_cache, save_translation_cache


def main():
    # Define command-line arguments
    parser = argparse.ArgumentParser(description='Translate PDF from English to Russian')
    parser.add_argument('command', choices=['translate', 'regenerate'], 
                        help='Command: translate (extract and translate text) or regenerate (create translated PDF)')
    parser.add_argument('input_pdf', help='Input PDF file path')
    parser.add_argument('output_pdf', help='Output PDF file path')
    parser.add_argument('--ignore-cache', action='store_true', help='Ignore existing translation cache')
    parser.add_argument('--font', default=None, help='Specify font to use for Russian text')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--start-page', type=int, default=0, help='Start page for processing (0-based)')
    parser.add_argument('--end-page', type=int, default=None, help='End page for processing (0-based)')
    
    args = parser.parse_args()
    
    # Set debug settings based on args
    global DEBUG_MODE, DEBUG_START_PAGE, DEBUG_END_PAGE
    DEBUG_MODE = args.debug
    DEBUG_START_PAGE = args.start_page
    if args.end_page is not None:
        DEBUG_END_PAGE = args.end_page
    
    # Load API configuration
    config = load_api_config()
    print(f"API Endpoint: {config['OPENAI_API_ENDPOINT']}")
    print(f"API Key found: {'Yes' if config['API_KEY'] else 'No'}")
    
    # Cache file path
    cache_file = 'translation_cache.json'
    
    # Load cache
    translation_cache = load_translation_cache(cache_file)
    
    # Calculate file MD5
    file_md5 = get_file_md5(args.input_pdf)
    print(f"File MD5: {file_md5}")
    
    # Check if file is already in cache
    if file_md5 in translation_cache and not args.ignore_cache:
        print(f"File found in cache with {len(translation_cache[file_md5])} translated paragraphs")
    else:
        print("File not in cache or cache is being ignored")

    # Determine if PDF is image-based
    is_image_pdf = is_image_based_pdf(args.input_pdf)
    print(f"PDF is primarily {'image-based' if is_image_pdf else 'text-based'}")
    
    # Process based on command
    if args.command == 'translate':
        # Extract paragraphs based on PDF type
        if is_image_pdf:
            print("Using OCR to extract text...")
            paragraphs_by_page = extract_text_with_ocr(args.input_pdf)
        else:
            print("Extracting text directly from PDF...")
            paragraphs_by_page = extract_paragraphs(args.input_pdf)
        
        # Save extracted paragraphs for regeneration
        with open(f"{file_md5}_paragraphs.json", 'w', encoding='utf-8') as f:
            # Convert tuples to lists for JSON serialization
            serializable_data = {}
            for page_num, paragraphs in paragraphs_by_page.items():
                serializable_data[str(page_num)] = [
                    (text, list(bbox)) for text, bbox in paragraphs
                ]
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)
        
        total_paragraphs = sum(len(paragraphs) for paragraphs in paragraphs_by_page.values())
        print(f"Found {total_paragraphs} paragraphs across {len(paragraphs_by_page)} pages")
        
        # Translate paragraphs
        for page_num, paragraphs in paragraphs_by_page.items():
            if DEBUG_MODE and (page_num < DEBUG_START_PAGE or (DEBUG_END_PAGE is not None and page_num > DEBUG_END_PAGE)):
                continue
                
            for i, (text, _) in enumerate(paragraphs):
                print(f"Translating paragraph {i+1}/{len(paragraphs)} on page {page_num+1}...")
                # This will use cache if available
                translated_text = translate_text(text, file_md5, translation_cache, args.ignore_cache)

                # Ensure the translation is in the cache
                text_md5 = get_text_md5(text)
                if file_md5 not in translation_cache:
                    translation_cache[file_md5] = {}
                translation_cache[file_md5][text_md5] = translated_text
        
        # Save updated cache
        save_translation_cache(cache_file, translation_cache)
        print(f"Translation completed. Cache saved to {cache_file}")
        
    elif args.command == 'regenerate':
        # Load saved paragraphs
        paragraphs_file = f"{file_md5}_paragraphs.json"
        if not os.path.exists(paragraphs_file):
            print(f"Error: Paragraphs file {paragraphs_file} not found. Run 'translate' command first.")
            return
            
        with open(paragraphs_file, 'r', encoding='utf-8') as f:
            serialized_data = json.load(f)
            # Convert back from serialized format
            paragraphs_by_page = {}
            for page_num_str, paragraphs in serialized_data.items():
                paragraphs_by_page[int(page_num_str)] = [
                    (text, tuple(bbox)) for text, bbox in paragraphs
                ]
        
        # Choose method based on PDF type
        if is_image_pdf:
            print("Creating translated PDF with image-based approach...")
            create_translated_pdf_ocr_approach(args.input_pdf, args.output_pdf, 
                                                 paragraphs_by_page, translation_cache, 
                                                 file_md5, args.font)
        else:
            print("Creating translated PDF with text-based approach...")
            # create_translated_pdf_text_approach(args.input_pdf, args.output_pdf, 
            #                                   paragraphs_by_page, translation_cache, 
            #                                   file_md5, args.font)
            create_clean_translated_pdf(args.input_pdf, args.output_pdf, 
                                              paragraphs_by_page, translation_cache, 
                                              file_md5, args.font)
            
        print(f"PDF regeneration completed. Output saved to {args.output_pdf}")


if __name__ == "__main__":
    main()
