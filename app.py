import os
import logging
import sys
import io
import uuid
import time
from flask import Flask, request, render_template, send_file, jsonify, session
from werkzeug.utils import secure_filename
from pdf_extractor import extract_text_from_pdf
import tempfile
import traceback
from collections import defaultdict
from datetime import datetime, timedelta

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Also configure werkzeug logger
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# In-memory storage for extracted text (with expiration)
text_storage = {}
TEXT_STORAGE_EXPIRY = 3600  # 1 hour

# Configure Flask logging
app.logger.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file_path(filepath, base_dir):
    """Validate that file path is within base directory to prevent path traversal."""
    try:
        real_filepath = os.path.realpath(filepath)
        real_base_dir = os.path.realpath(base_dir)
        return real_filepath.startswith(real_base_dir + os.sep)
    except (OSError, ValueError):
        return False


def get_session_id():
    """Get or create a unique session ID."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']


def sanitize_error(error_msg):
    """Return sanitized error message for user."""
    # Log the full error server-side but return generic message to user
    logger.error(f'Internal error: {error_msg}')
    return 'An error occurred while processing your request. Please try again.'


@app.before_request
def log_request_info():
    app.logger.info('%s %s', request.method, request.path)


@app.after_request
def log_response_info(response):
    app.logger.info('Status: %s', response.status)
    return response


@app.route('/')
def index():
    app.logger.info('Serving index page')
    return render_template('index.html')


@app.route('/features')
def features():
    app.logger.info('Serving features page')
    return render_template('features.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        app.logger.info('Received upload request')
        if 'file' not in request.files:
            app.logger.error('No file part in request')
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            app.logger.error('No selected file')
            return jsonify({'error': 'No selected file'}), 400

        if not allowed_file(file.filename):
            app.logger.error('Invalid file type: %s', file.filename)
            return jsonify({'error': 'Invalid file type'}), 400

        if file.mimetype != 'application/pdf':
            app.logger.error('Invalid MIME type: %s', file.mimetype)
            return jsonify({'error': 'Invalid file type'}), 400
            
        # Additional file size validation
        if len(file.read()) == 0:
            app.logger.error('Empty file uploaded')
            return jsonify({'error': 'Empty file not allowed'}), 400
        file.seek(0)  # Reset file pointer after size check
        
        # Basic PDF header validation
        file_header = file.read(8)
        file.seek(0)  # Reset file pointer
        if not file_header.startswith(b'%PDF-'):
            app.logger.error('Invalid PDF header')
            return jsonify({'error': 'File does not appear to be a valid PDF'}), 400

        # Create session-specific temp directory
        session_id = get_session_id()
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'darkhole_temp', session_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate unique filename with timestamp
        timestamp = int(time.time() * 1000)
        base_filename = secure_filename(file.filename)
        filename = f'{timestamp}_{base_filename}'
        filepath = os.path.join(temp_dir, filename)
        
        # Validate file path to prevent directory traversal
        if not validate_file_path(filepath, temp_dir):
            app.logger.error('Invalid file path detected')
            return jsonify({'error': 'Invalid file path'}), 400
            
        file.save(filepath)
        app.logger.info('File saved to session directory')

        # Extract text
        try:
            text = extract_text_from_pdf(filepath)
            app.logger.info('Text extraction successful')

            # Store text temporarily with expiration (avoid session cookie size limit)
            text_id = str(uuid.uuid4())
            text_storage[text_id] = {
                'text': text,
                'created': datetime.now(),
                'session_id': get_session_id()
            }
            app.logger.info('Text stored temporarily for download')

            return jsonify({
                'message': 'File processed successfully',
                'text': text,
                'text_id': text_id,
                'success': True
            })
        except Exception as e:
            app.logger.error('Text extraction failed: %s', str(e))
            app.logger.error('Traceback: %s', traceback.format_exc())
            return jsonify({'error': sanitize_error(str(e))}), 500
        finally:
            # Clean up uploaded file
            try:
                os.remove(filepath)
                app.logger.info('Uploaded file cleaned up successfully')
            except Exception as e:
                app.logger.error('Failed to clean up uploaded file: %s', str(e))
    except Exception as e:
        app.logger.error('Upload processing failed: %s', str(e))
        app.logger.error('Traceback: %s', traceback.format_exc())
        return jsonify({'error': sanitize_error(str(e))}), 500


@app.route('/download/<text_id>')
def download_file(text_id):
    try:
        app.logger.info('Download request received for text_id: %s', text_id)
        
        # Clean expired entries
        clean_expired_texts()
        
        # Get extracted text from temporary storage
        text_data = text_storage.get(text_id)
        
        if not text_data:
            app.logger.error('No text available for download with id: %s', text_id)
            return jsonify({'error': 'No text available for download'}), 404
            
        # Verify session matches (basic security)
        if text_data.get('session_id') != get_session_id():
            app.logger.error('Session mismatch for download')
            return jsonify({'error': 'Invalid download request'}), 403
            
        extracted_text = text_data['text']
        app.logger.info('Sending text file for download')
        
        # Clean up after download
        del text_storage[text_id]
        
        return send_file(
            io.BytesIO(extracted_text.encode('utf-8')),
            as_attachment=True,
            download_name='extracted_text.txt',
            mimetype='text/plain'
        )
        
    except Exception as e:
        app.logger.error('Download failed: %s', str(e))
        app.logger.error('Traceback: %s', traceback.format_exc())
        return jsonify({'error': sanitize_error(str(e))}), 500


def clean_expired_texts():
    """Remove expired text entries from memory."""
    current_time = datetime.now()
    expired_keys = []
    
    for text_id, data in text_storage.items():
        if current_time - data['created'] > timedelta(seconds=TEXT_STORAGE_EXPIRY):
            expired_keys.append(text_id)
    
    for key in expired_keys:
        del text_storage[key]
        app.logger.info('Cleaned up expired text entry: %s', key)


@app.errorhandler(404)
def handle_404(e):
    app.logger.error('404 error: %s', request.url)
    return jsonify({'error': 'Not Found'}), 404


@app.errorhandler(413)
def handle_413(e):
    app.logger.error('413 error: File too large')
    return jsonify(
        {'error': 'File too large. Please upload a smaller PDF.'}), 413


@app.errorhandler(500)
def handle_500(e):
    app.logger.error('500 error: %s', str(e))
    app.logger.error('Traceback: %s', traceback.format_exc())
    return jsonify({'error': sanitize_error(str(e))}), 500


if __name__ == '__main__':
    app.run()
