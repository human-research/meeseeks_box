from setuptools import setup, find_packages

setup(
    name="pdf_translator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "PyMuPDF",
        "langdetect",
        "Pillow",
        "pytesseract",
        "reportlab",
        "PyPDF2",
        "pdf2image",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "pdf-translator=pdf_translator.main:main",
        ],
    },
)