document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('statusText');
    const resultContainer = document.getElementById('resultContainer');
    const downloadButton = document.getElementById('downloadButton');
    const uploadContainer = document.getElementById('uploadContainer');

    // Handle drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('dragover');
    }

    function unhighlight(e) {
        dropZone.classList.remove('dragover');
    }

    // Handle file drop
    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Handle file input change
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    // Handle click on upload area
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'application/pdf') {
                uploadFile(file);
            } else {
                alert('Please upload a PDF file.');
            }
        }
    }

    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Show progress container
        uploadContainer.style.display = 'none';
        progressContainer.style.display = 'block';
        resultContainer.style.display = 'none';

        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += 5;
            if (progress > 90) {
                clearInterval(progressInterval);
            }
            progressBar.style.width = `${progress}%`;
        }, 200);

        // Upload file
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            clearInterval(progressInterval);
            progressBar.style.width = '100%';
            
            if (data.success) {
                statusText.textContent = 'Processing complete!';
                setTimeout(() => {
                    progressContainer.style.display = 'none';
                    resultContainer.style.display = 'block';
                    downloadButton.href = data.download_url;
                }, 500);
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        })
        .catch(error => {
            clearInterval(progressInterval);
            progressContainer.style.display = 'none';
            uploadContainer.style.display = 'block';
            alert('Error: ' + error.message);
        });
    }

    // Handle download button click
    downloadButton.addEventListener('click', (e) => {
        e.preventDefault();
        window.location.href = downloadButton.href;
    });
}); 