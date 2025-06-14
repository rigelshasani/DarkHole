import os
import logging
import time
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
import io
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import tempfile

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
        try:
            logger.info("Extracting text with PDFMiner...")
            text_pages = []
            with open(self.pdf_path, 'rb') as file:
                parser = PDFParser(file)
                document = PDFDocument(parser)
                if not document.is_extractable:
                    return []
                
                rsrcmgr = PDFResourceManager()
                laparams = LAParams()
                device = TextConverter(rsrcmgr, io.StringIO(), laparams=laparams)
                interpreter = PDFPageInterpreter(rsrcmgr, device)
                
                for page in PDFPage.create_pages(document):
                    interpreter.process_page(page)
                    text = device.get_text()
                    if text.strip():
                        text_pages.append(text.strip())
                    device.reset()
            
            return text_pages
        except Exception as e:
            logger.error(f"PDFMiner extraction failed: {str(e)}")
            return []
    
    def extract_with_pymupdf(self):
        """Extract text using PyMuPDF."""
        try:
            logger.info("Extracting text with PyMuPDF...")
            text_pages = []
            doc = fitz.open(self.pdf_path)
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_pages.append(text.strip())
            return text_pages
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {str(e)}")
            return []
    
    def extract_with_ocr(self):
        """Extract text using OCR."""
        try:
            # Convert PDF to images with lower DPI to reduce memory usage
            images = convert_from_path(
                self.pdf_path,
                dpi=150,  # Reduced from 300 to 150
                thread_count=1,  # Single thread to reduce memory usage
                fmt='jpeg',  # Use JPEG instead of PNG
                grayscale=True  # Use grayscale to reduce memory
            )
            
            texts = []
            for img in images:
                # Process one page at a time
                text = pytesseract.image_to_string(img)
                texts.append(text)
                # Clear memory
                del img
                
            return texts
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            return []
    
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
        """Extract text using all available methods and combine results."""
        try:
            # Set a timeout for the entire extraction process
            start_time = time.time()
            timeout = 30  # 30 seconds timeout
            
            # Try PDFMiner first (fastest)
            pdfminer_texts = self.extract_with_pdfminer()
            pdfminer_text = "\n".join(pdfminer_texts) if pdfminer_texts else ""
            if pdfminer_text and len(pdfminer_text.strip()) > 100:
                return pdfminer_text
                
            # Try PyMuPDF next
            pymupdf_texts = self.extract_with_pymupdf()
            pymupdf_text = "\n".join(pymupdf_texts) if pymupdf_texts else ""
            if pymupdf_text and len(pymupdf_text.strip()) > 100:
                return pymupdf_text
                
            # Only try OCR if other methods failed and we haven't timed out
            if time.time() - start_time < timeout:
                ocr_texts = self.extract_with_ocr()
                if ocr_texts:
                    return "\n".join(ocr_texts)
            
            # If all methods failed or timed out, return the best result
            return pdfminer_text or pymupdf_text or "Text extraction failed. Please try a different PDF."
            
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            return "An error occurred during text extraction. Please try again."

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