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

# Configure Flask logging
app.logger.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


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

        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'darkhole_temp')
        os.makedirs(temp_dir, exist_ok=True)

        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(temp_dir, filename)
        file.save(filepath)
        app.logger.info('File saved to: %s', filepath)

        # Extract text
        try:
            text = extract_text_from_pdf(filepath)
            app.logger.info('Text extraction successful')

            # Save extracted text
            output_path = os.path.join(temp_dir, 'extracted_text.txt')
            if os.path.exists(output_path):
                os.remove(output_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            app.logger.info('Extracted text saved to: %s', output_path)

            return jsonify({
                'message': 'File processed successfully',
                'download_url': '/download'
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


@app.route('/download')
def download_file():
    try:
        app.logger.info('Download request received')
        
        # Get session info
        session_id = session.get('session_id')
        output_filename = session.get('output_filename')
        
        if not session_id or not output_filename:
            app.logger.error('No file available for download in session')
            return jsonify({'error': 'No file available for download'}), 404
            
        output_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            'darkhole_temp',
            session_id,
            output_filename
        )
        
        # Validate file path
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'darkhole_temp', session_id)
        if not validate_file_path(output_path, session_dir):
            app.logger.error('Invalid download path detected')
            return jsonify({'error': 'Invalid file path'}), 400
            
        if os.path.exists(output_path):
            app.logger.info('Sending file for download')
            with open(output_path, 'rb') as f:
                data = f.read()
            
            # Clean up file after reading
            try:
                os.remove(output_path)
                # Clean up session data and try to remove session directory if empty
                session.pop('output_filename', None)
                try:
                    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'darkhole_temp', session_id)
                    if os.path.exists(session_dir) and not os.listdir(session_dir):
                        os.rmdir(session_dir)
                        app.logger.info('Empty session directory cleaned up')
                except Exception as dir_cleanup_error:
                    app.logger.warning('Failed to cleanup session directory: %s', str(dir_cleanup_error))
            except Exception as cleanup_error:
                app.logger.error('Failed to cleanup file: %s', str(cleanup_error))
                
            return send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name='extracted_text.txt',
                mimetype='text/plain'
            )
        
        app.logger.error('File not found for download')
        return jsonify({'error': 'File not found'}), 404
        
    except Exception as e:
        app.logger.error('Download failed: %s', str(e))
        app.logger.error('Traceback: %s', traceback.format_exc())
        return jsonify({'error': sanitize_error(str(e))}), 500


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
