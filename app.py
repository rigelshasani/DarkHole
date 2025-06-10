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

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Extract text from the PDF
            extracted_text = extract_text_from_pdf(filepath)
            
            # Save the extracted text to a temporary file
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted_text.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            
            # Clean up the uploaded PDF
            os.remove(filepath)
            
            return jsonify({
                'success': True,
                'message': 'Text extracted successfully',
                'download_url': '/download'
            })
            
        except Exception as e:
            # Clean up in case of error
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

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

if __name__ == '__main__':
    app.run(debug=True) 