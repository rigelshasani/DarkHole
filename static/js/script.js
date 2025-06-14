document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const progressContainer = document.querySelector('.progress-container');
    const progressBar = document.querySelector('.progress');
    const progressText = document.querySelector('.progress-text');
    const resultContainer = document.querySelector('.result-container');
    const downloadLink = document.getElementById('downloadLink');

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);

    // Handle file input change
    fileInput.addEventListener('change', handleFileSelect, false);

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight(e) {
        dropZone.classList.add('highlight');
    }

    function unhighlight(e) {
        dropZone.classList.remove('highlight');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFileSelect(e) {
        const files = e.target.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'application/pdf') {
                // Track file upload attempt
                gtag('event', 'pdf_upload_attempt', {
                    'file_size': file.size,
                    'file_name': file.name
                });
                uploadFile(file);
            } else {
                // Track invalid file type
                gtag('event', 'invalid_file_type', {
                    'file_type': file.type
                });
                alert('Please upload a PDF file.');
            }
        }
    }

    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Show progress container
        progressContainer.style.display = 'block';
        resultContainer.style.display = 'none';

        // Simulate progress
        let progress = 0;
        const interval = setInterval(() => {
            progress += 5;
            progressBar.style.width = progress + '%';
            if (progress >= 100) {
                clearInterval(interval);
            }
        }, 200);

        // Send file to server
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            clearInterval(interval);
            progressBar.style.width = '100%';
            progressText.textContent = 'Processing complete!';

            // Track successful processing
            gtag('event', 'pdf_processing_success', {
                'file_size': file.size,
                'file_name': file.name
            });

            // Show result container
            setTimeout(() => {
                progressContainer.style.display = 'none';
                resultContainer.style.display = 'block';
                
                // Set the download link
                if (data.download_url) {
                    downloadLink.href = data.download_url;
                    downloadLink.style.display = 'inline-block';
                } else {
                    console.error('No download URL in response:', data);
                    downloadLink.style.display = 'none';
                }
            }, 500);
        })
        .catch(error => {
            console.error('Error:', error);
            progressText.textContent = 'Error processing file. Please try again.';
            
            // Track processing error
            gtag('event', 'pdf_processing_error', {
                'file_size': file.size,
                'file_name': file.name,
                'error': error.message
            });
        });
    }

    // Add error handling for download link
    downloadLink.addEventListener('click', function(e) {
        if (!this.href || this.href === 'undefined') {
            e.preventDefault();
            console.error('Invalid download URL');
            alert('Download link is not available. Please try processing the file again.');
        }
    });

    // Add parallax effect to stars
    document.addEventListener('mousemove', function(e) {
        const stars = document.querySelector('.stars');
        const twinkling = document.querySelector('.twinkling');
        const x = e.clientX / window.innerWidth;
        const y = e.clientY / window.innerHeight;
        
        stars.style.transform = `translate(${x * 50}px, ${y * 50}px)`;
        twinkling.style.transform = `translate(${x * 30}px, ${y * 30}px)`;
    });
}); 