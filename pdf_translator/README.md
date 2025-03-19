# PDF Translator for English to Russian

This tool translates PDF documents from English to Russian while preserving images, formulas, and document layout. It's designed to handle academic and technical documents with proper Cyrillic character rendering.

## Features

- Translates English text to Russian using OpenAI API
- Preserves images, formulas, and document formatting
- Automatically detects the best font size to fit translated text in original spaces
- Caches translations to reduce API costs
- Supports custom font selection for best Cyrillic rendering
- Debug mode to test on specific pages before full translation

## Requirements

```
pip install -e .
```

## Usage

The tool has two main commands:

1. `translate` - Extract text and translate it, saving translations to cache
2. `regenerate` - Create a translated PDF using cached translations

### Basic Usage

```bash
# Step 1: Extract and translate text (creates translation cache)
pdf-translator translate input.pdf output.pdf

# Step 2: Generate the translated PDF
pdf-translator regenerate input.pdf output.pdf
```

### Advanced Options

```bash
# Ignore existing translation cache
python pdf_translator.py translate input.pdf output.pdf --ignore-cache

# Use a specific Cyrillic font
python pdf_translator.py regenerate input.pdf output.pdf --font "/Library/Fonts/Arial.ttf"

# Debug mode: process only specific pages (useful for testing)
python pdf_translator.py translate input.pdf output.pdf --debug --start-page 1 --end-page 2
```

## Configuration

The tool uses OpenAI API for translation, with credentials stored in `~/.meeseeks_box/llm`:

```
API_KEY=your-openai-api-key
OPENAI_API_ENDPOINT=https://your-company-openai-endpoint.com/v1/chat/completions
```

If this file doesn't exist, it will be created with instructions on the first run.

## How It Works

1. **Translation Phase**:
   - Extracts text from the PDF
   - Identifies paragraphs that should be translated
   - Sends text to OpenAI API for translation
   - Caches the translations using MD5 hashes

2. **Regeneration Phase**:
   - Creates a new PDF document
   - Preserves all images and non-text elements from the original
   - Replaces original text with translated text
   - Automatically adjusts font size to fit translated text in original spaces

## Tips for Best Results

- **Font Selection**: Different fonts display Cyrillic characters with varying quality. For best results on Mac OS, use Arial or Times New Roman.
- **Translation Quality**: Review the translations before regenerating the PDF, as automatic translation may need manual corrections.
- **Formulas**: The system is designed to detect and preserve mathematical formulas. If you notice formulas being incorrectly translated, you can adjust the formula detection threshold.
- **Image-Heavy Documents**: For documents with many images or complex formatting, the regeneration process may take longer.

## Troubleshooting

- **Question Marks Instead of Cyrillic**: Try specifying a different font with `--font`
- **Text Overflow**: The system will try to reduce font size to fit text, but Russian text is often longer than English
- **Missing Images**: If images don't appear in the output, try adjusting the image extraction method in the code

## License

[MIT License](LICENSE)

## Acknowledgements

This tool uses PyMuPDF (fitz) library for PDF manipulation and the OpenAI API for translation services.