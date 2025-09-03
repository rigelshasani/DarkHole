import os
import logging
import sys
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
import tempfile
import re
import traceback

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using multiple methods."""
    logger.info(f"Starting text extraction for: {pdf_path}")
    extractor = PDFExtractor(pdf_path, max_pages=50, page_timeout=15)
    return extractor.extract()


class PDFExtractor:
    def __init__(self, pdf_path, dpi=150, min_text_length=50, max_pages=50, page_timeout=10):
        self.pdf_path = pdf_path
        self.dpi = dpi
        self.min_text_length = min_text_length
        self.max_pages = max_pages
        self.page_timeout = page_timeout
        self.output = []
        
    def validate_pdf(self):
        """Validate PDF file before processing."""
        try:
            if not os.path.exists(self.pdf_path):
                logger.error(f"PDF file not found: {self.pdf_path}")
                return False
                
            # Check file size (limit to 50MB)
            file_size = os.path.getsize(self.pdf_path)
            if file_size > 50 * 1024 * 1024:
                logger.error(f"PDF file too large: {file_size} bytes")
                return False
                
            # Basic PDF validation with PyMuPDF
            with fitz.open(self.pdf_path) as doc:
                if doc.page_count == 0:
                    logger.error("PDF has no pages")
                    return False
                if doc.page_count > self.max_pages:
                    logger.warning(f"PDF has {doc.page_count} pages, limiting to {self.max_pages}")
                    
            return True
        except Exception as e:
            logger.error(f"PDF validation failed: {str(e)}")
            return False

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
                    logger.warning("PDF is not extractable with PDFMiner")
                    return []

                rsrcmgr = PDFResourceManager()
                laparams = LAParams()

                for page in PDFPage.create_pages(document):
                    output_string = io.StringIO()
                    device = TextConverter(
                        rsrcmgr, output_string, laparams=laparams)
                    interpreter = PDFPageInterpreter(rsrcmgr, device)
                    interpreter.process_page(page)
                    text = output_string.getvalue()
                    if text.strip():
                        text_pages.append(text.strip())
                    device.close()
                    output_string.close()

            logger.info(f"PDFMiner extracted {len(text_pages)} pages")
            return text_pages
        except Exception as e:
            logger.error(f"PDFMiner extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def extract_with_pymupdf(self):
        """Extract text using PyMuPDF."""
        try:
            logger.info("Extracting text with PyMuPDF...")
            text_pages = []
            with fitz.open(self.pdf_path) as doc:
                page_count = min(doc.page_count, self.max_pages)
                for i in range(page_count):
                    page = doc[i]
                    text = page.get_text()
                    if text.strip():
                        text_pages.append(text.strip())
            logger.info(f"PyMuPDF extracted {len(text_pages)} pages")
            return text_pages
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def extract_with_ocr(self):
        """Extract text using OCR with safety limits."""
        try:
            logger.info("Extracting text with OCR...")
            text_pages = []
            
            # Limit pages for OCR to prevent resource exhaustion
            max_ocr_pages = min(10, self.max_pages)
            
            images = convert_from_path(
                self.pdf_path,
                dpi=self.dpi,
                thread_count=1,
                fmt='jpeg',
                first_page=1,
                last_page=max_ocr_pages
            )

            for i, image in enumerate(images):
                if i >= max_ocr_pages:
                    logger.info(f"Limiting OCR to {max_ocr_pages} pages")
                    break
                    
                logger.info(f"Processing page {i + 1} with OCR")
                # Convert to grayscale and resize if too large
                image = image.convert('L')
                
                # Limit image size to prevent memory issues
                if image.width > 2000 or image.height > 2000:
                    image.thumbnail((2000, 2000))
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(
                    suffix='.jpg', delete=False
                ) as temp_file:
                    image.save(temp_file.name, 'JPEG')
                    try:
                        # Perform OCR with timeout
                        text = pytesseract.image_to_string(
                            temp_file.name,
                            timeout=self.page_timeout
                        )
                        if text.strip():
                            text_pages.append(text.strip())
                    except pytesseract.TesseractError as te:
                        logger.warning(f"OCR failed for page {i + 1}: {str(te)}")
                    finally:
                        # Clean up
                        try:
                            os.unlink(temp_file.name)
                        except OSError:
                            pass

            logger.info(f"OCR extracted {len(text_pages)} pages")
            return text_pages
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def merge_texts(self, pdfminer_texts, pymupdf_texts, ocr_texts):
        """Merge texts from different methods; keep longest per page."""
        merged_texts = []
        for i in range(max(len(pdfminer_texts), len(
                pymupdf_texts), len(ocr_texts))):
            texts = []
            if i < len(pdfminer_texts) and len(
                    pdfminer_texts[i]) > self.min_text_length:
                texts.append(pdfminer_texts[i])
            if i < len(pymupdf_texts) and len(
                    pymupdf_texts[i]) > self.min_text_length:
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
            # Validate PDF before processing
            if not self.validate_pdf():
                return "Invalid PDF file. Please check the file and try again."
                
            # Set a timeout for the entire extraction process
            start_time = time.time()
            timeout = 60  # 60 seconds timeout (increased for larger files)

            # Try PDFMiner first (fastest)
            pdfminer_texts = self.extract_with_pdfminer()
            pdfminer_text = "\n".join(pdfminer_texts) if pdfminer_texts else ""
            if pdfminer_text and len(pdfminer_text.strip()) > 100:
                logger.info("Using PDFMiner results")
                return self.clean_text(pdfminer_text)

            # Try PyMuPDF next
            if time.time() - start_time < timeout:
                pymupdf_texts = self.extract_with_pymupdf()
                pymupdf_text = "\n".join(pymupdf_texts) if pymupdf_texts else ""
                if pymupdf_text and len(pymupdf_text.strip()) > 100:
                    logger.info("Using PyMuPDF results")
                    return self.clean_text(pymupdf_text)

            # Only try OCR if other methods failed and we haven't timed out
            if time.time() - start_time < timeout:
                ocr_texts = self.extract_with_ocr()
                if ocr_texts:
                    logger.info("Using OCR results")
                    return self.clean_text("\n".join(ocr_texts))

            # If all methods failed or timed out, return the best result
            logger.warning("All extraction methods failed or timed out")
            best_result = pdfminer_text or pymupdf_text
            if best_result:
                return self.clean_text(best_result)
            else:
                return "Text extraction failed. The PDF may be corrupted, password-protected, or contain only images without readable text."

        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "An error occurred during text extraction. Please try again with a different PDF file."


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


if __name__ == "__main__":
    main()
