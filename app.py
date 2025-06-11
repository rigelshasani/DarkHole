import os
from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from pdf_extractor import extract_text_from_pdf
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    try:
        # Create a temporary file
        temp_dir = os.path.join(app.root_path, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)
        
        # Set a timeout for the extraction process
        extracted_text = extract_text_from_pdf(filepath)
        
        # Clean up the temporary file
        try:
            os.remove(filepath)
        except:
            pass
            
        return jsonify({'text': extracted_text})
        
    except Exception as e:
        # Clean up in case of error
        try:
            if 'filepath' in locals():
                os.remove(filepath)
        except:
            pass
            
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download_file():
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted_text.txt')
    if os.path.exists(output_path):
        return send_file(
            output_path,
            as_attachment=True,
            download_name='extracted_text.txt',
            mimetype='text/plain'
        )
    return jsonify({'error': 'File not found'}), 404

@app.route('/ping')
def ping():
    return 'pong'

# Add error handlers
@app.errorhandler(500)
def handle_500(e):
    return jsonify({'error': 'Internal server error. Please try again.'}), 500

@app.errorhandler(413)
def handle_413(e):
    return jsonify({'error': 'File too large. Please upload a smaller PDF.'}), 413

@app.errorhandler(408)
def handle_408(e):
    return jsonify({'error': 'Request timeout. Please try again.'}), 408

if __name__ == '__main__':
    app.run(debug=True) 