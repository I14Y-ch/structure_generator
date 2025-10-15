// CSV Import Modal handler
function showCSVImportModal(fileInput) {
    if (!fileInput.files || fileInput.files.length === 0) {
        console.log('No file selected');
        return;
    }
    
    const file = fileInput.files[0];
    if (!file.name.endsWith('.csv')) {
        alert('Please select a CSV file');
        fileInput.value = '';
        return;
    }
    
    // Show the modal
    new bootstrap.Modal(document.getElementById('csvImportModal')).show();
}

// CSV Import function
function importCSV() {
    const fileInput = document.getElementById('csv-file');
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('No file selected');
        return;
    }
    
    const file = fileInput.files[0];
    const datasetName = document.getElementById('csv-dataset-name').value;
    const lang = document.getElementById('csv-lang').value;
    
    if (!datasetName) {
        alert('Dataset name is required');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);
    formData.append('lang', lang);
    
    document.body.classList.add('loading');
    
    fetch('/api/import/csv', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.body.classList.remove('loading');
        
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('csvImportModal')).hide();
            
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> CSV file imported.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            alert('Error importing CSV: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        document.body.classList.remove('loading');
        alert('Error importing CSV: ' + error.message);
        console.error('Error importing CSV:', error);
    });
    
    // Reset file input
    fileInput.value = '';
}

// XSD Import Modal handler
function showXSDImportModal(fileInput) {
    if (!fileInput.files || fileInput.files.length === 0) {
        console.log('No file selected');
        return;
    }
    
    const file = fileInput.files[0];
    if (!file.name.endsWith('.xsd')) {
        alert('Please select an XSD file');
        fileInput.value = '';
        return;
    }
    
    // Show the modal
    new bootstrap.Modal(document.getElementById('xsdImportModal')).show();
}

// XSD Import function
function importXSD() {
    const fileInput = document.getElementById('xsd-file');
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('No file selected');
        return;
    }
    
    const file = fileInput.files[0];
    const datasetName = document.getElementById('xsd-dataset-name').value;
    
    if (!datasetName) {
        alert('Dataset name is required');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);
    
    document.body.classList.add('loading');
    
    fetch('/api/import/xsd', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.body.classList.remove('loading');
        
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('xsdImportModal')).hide();
            
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> XSD file imported.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            alert('Error importing XSD: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        document.body.classList.remove('loading');
        alert('Error importing XSD: ' + error.message);
        console.error('Error importing XSD:', error);
    });
    
    // Reset file input
    fileInput.value = '';
}

// Make sure all functions are exported to global scope
window.showCSVImportModal = showCSVImportModal;
window.importCSV = importCSV;
window.showXSDImportModal = showXSDImportModal;
window.importXSD = importXSD;
