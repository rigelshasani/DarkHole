import fitz  # PyMuPDF
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from pdf2image import convert_from_path
import pytesseract
import re
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFExtractor:
    def __init__(self, pdf_path, dpi=300, min_text_length=50):
        self.pdf_path = pdf_path
        self.dpi = dpi
        self.min_text_length = min_text_length
        self.output = []
        
    def clean_text(self, text):
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep important punctuation
        text = re.sub(r'[^\w\s.,;:!?()-]', '', text)
        # Fix common OCR mistakes
        text = text.replace('|', 'I')
        text = text.replace('l', 'I')
        return text.strip()
    
    def extract_with_pdfminer(self):
        """Extract text using PDFMiner."""
        logger.info("Extracting text with PDFMiner...")
        text_by_page = []
        for page_layout in extract_pages(self.pdf_path):
            page_text = ""
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    page_text += element.get_text()
            text_by_page.append(self.clean_text(page_text))
        return text_by_page
    
    def extract_with_pymupdf(self):
        """Extract text using PyMuPDF."""
        logger.info("Extracting text with PyMuPDF...")
        text_by_page = []
        doc = fitz.open(self.pdf_path)
        for page in doc:
            text = page.get_text("text")
            text_by_page.append(self.clean_text(text))
        doc.close()
        return text_by_page
    
    def extract_with_ocr(self):
        """Extract text using Tesseract OCR."""
        logger.info("Extracting text with OCR...")
        text_by_page = []
        images = convert_from_path(self.pdf_path, dpi=self.dpi)
        for img in images:
            text = pytesseract.image_to_string(img, lang='eng', config='--psm 4')
            text_by_page.append(self.clean_text(text))
        return text_by_page
    
    def merge_texts(self, pdfminer_texts, pymupdf_texts, ocr_texts):
        """Merge texts from different methods, preferring the longest valid text for each page."""
        merged_texts = []
        for i in range(max(len(pdfminer_texts), len(pymupdf_texts), len(ocr_texts))):
            texts = []
            if i < len(pdfminer_texts) and len(pdfminer_texts[i]) > self.min_text_length:
                texts.append(pdfminer_texts[i])
            if i < len(pymupdf_texts) and len(pymupdf_texts[i]) > self.min_text_length:
                texts.append(pymupdf_texts[i])
            if i < len(ocr_texts) and len(ocr_texts[i]) > self.min_text_length:
                texts.append(ocr_texts[i])
            
            # Use the longest text for this page
            if texts:
                merged_texts.append(max(texts, key=len))
            else:
                merged_texts.append("")
        
        return merged_texts
    
    def extract(self):
        """Main extraction method that combines all approaches."""
        try:
            # Extract using all methods
            pdfminer_texts = self.extract_with_pdfminer()
            pymupdf_texts = self.extract_with_pymupdf()
            ocr_texts = self.extract_with_ocr()
            
            # Merge the results
            merged_texts = self.merge_texts(pdfminer_texts, pymupdf_texts, ocr_texts)
            
            # Format the output
            output = []
            for i, text in enumerate(merged_texts, 1):
                if text:  # Only include non-empty pages
                    output.append(f"\n{'='*50}\nPage {i}\n{'='*50}\n\n{text}\n")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error during extraction: {str(e)}")
            raise

def main():
    pdf_path = "responsiveRecord.pdf"
    output_path = "extracted_text.txt"
    
    try:
        extractor = PDFExtractor(pdf_path)
        extracted_text = extractor.extract()
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(extracted_text)
        
        logger.info(f"Extraction complete. Results saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to process PDF: {str(e)}")

def extract_text_from_pdf(filepath):
    extractor = PDFExtractor(filepath)
    return extractor.extract()

if __name__ == "__main__":
    main() 