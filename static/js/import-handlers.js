const IMPORT_DEFAULT_DATASET_NAME = 'Imported Dataset';
const IMPORT_ERROR_NO_FILE = 'No file selected';
const IMPORT_ERROR_DATASET_REQUIRED = 'Dataset name is required';
const IMPORT_SUCCESS_CSV_HTML = '<small><strong>Success:</strong> CSV file imported.</small>';
const IMPORT_SUCCESS_XSD_HTML = '<small><strong>Success:</strong> XSD file imported.</small>';

function showSelectionStatus(html) {
    const status = document.getElementById('selection-status');
    if (!status) {
        return;
    }

    status.style.display = 'block';
    status.innerHTML = html;
    setTimeout(() => { status.style.display = 'none'; }, 3000);
}

function showSuccessStatus(message) {
    showSelectionStatus(`<small><strong>Success:</strong> ${message}</small>`);
}

function getApiErrorMessage(data) {
    return (data && data.error) || 'Unknown error';
}

function showActionError(errorLabel, error) {
    const errorMessage = error && error.message ? error.message : String(error);
    alert(`${errorLabel}: ${errorMessage}`);
    console.error(`${errorLabel}:`, error);
}

function showImportModal(fileInput, extension, invalidFileMessage, modalId) {
    if (!fileInput.files || fileInput.files.length === 0) {
        console.log('No file selected');
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.endsWith(extension)) {
        alert(invalidFileMessage);
        fileInput.value = '';
        return;
    }

    new bootstrap.Modal(document.getElementById(modalId)).show();
}

function showCSVImportModal(fileInput) {
    showImportModal(fileInput, '.csv', 'Please select a CSV file', 'csvImportModal');
}

function handleImportSuccess(modalId, successHtml, resetFormFields) {
    const modalElement = document.getElementById(modalId);
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    if (modalInstance) {
        modalInstance.hide();
    }

    if (window.clearNodeSelection) {
        window.clearNodeSelection();
    }

    showSelectionStatus(successHtml);

    loadGraphWithD3();

    if (typeof resetFormFields === 'function') {
        resetFormFields();
    }
}

function runImportRequest({ url, formData, modalId, successHtml, resetFormFields, errorLabel }) {
    document.body.classList.add('loading');

    return fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(async response => {
        let data;
        try {
            data = await response.json();
        } catch (parseError) {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            throw new Error('Invalid server response');
        }

        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Unknown error');
        }

        handleImportSuccess(modalId, successHtml, resetFormFields);
    })
    .catch(error => {
        showActionError(errorLabel, error);
    })
    .finally(() => {
        document.body.classList.remove('loading');
    });
}

function getRequiredFile(fileInputId) {
    const fileInput = document.getElementById(fileInputId);
    if (!fileInput.files || fileInput.files.length === 0) {
        alert(IMPORT_ERROR_NO_FILE);
        return null;
    }
    return { fileInput, file: fileInput.files[0] };
}

function getRequiredValue(inputId, message) {
    const value = document.getElementById(inputId).value;
    if (!value) {
        alert(message);
        return null;
    }
    return value;
}

// CSV Import function
function importCSV() {
    const fileData = getRequiredFile('csv-file');
    if (!fileData) {
        return;
    }

    const { fileInput, file } = fileData;
    const datasetName = getRequiredValue('csv-dataset-name', IMPORT_ERROR_DATASET_REQUIRED);
    if (!datasetName) {
        return;
    }
    const lang = document.getElementById('csv-lang').value;
    const encoding = document.getElementById('csv-encoding').value;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);
    formData.append('lang', lang);
    formData.append('encoding', encoding);
    
    runImportRequest({
        url: '/api/import/csv',
        formData,
        modalId: 'csvImportModal',
        successHtml: IMPORT_SUCCESS_CSV_HTML,
        resetFormFields: () => {
            document.getElementById('csv-dataset-name').value = IMPORT_DEFAULT_DATASET_NAME;
            document.getElementById('csv-lang').value = 'de';
            document.getElementById('csv-encoding').value = 'auto';
        },
        errorLabel: 'Error importing CSV'
    });
    
    // Reset file input
    fileInput.value = '';
}

function showXSDImportModal(fileInput) {
    showImportModal(fileInput, '.xsd', 'Please select an XSD file', 'xsdImportModal');
}

// XSD Import function
function importXSD() {
    const fileData = getRequiredFile('xsd-file');
    if (!fileData) {
        return;
    }

    const { fileInput, file } = fileData;
    const datasetName = getRequiredValue('xsd-dataset-name', IMPORT_ERROR_DATASET_REQUIRED);
    if (!datasetName) {
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);
    
    runImportRequest({
        url: '/api/import/xsd',
        formData,
        modalId: 'xsdImportModal',
        successHtml: IMPORT_SUCCESS_XSD_HTML,
        resetFormFields: () => {
            document.getElementById('xsd-dataset-name').value = IMPORT_DEFAULT_DATASET_NAME;
        },
        errorLabel: 'Error importing XSD'
    });
    
    // Reset file input
    fileInput.value = '';
}

// Make sure all functions are exported to global scope
window.showCSVImportModal = showCSVImportModal;
window.importCSV = importCSV;
window.showXSDImportModal = showXSDImportModal;
window.importXSD = importXSD;

// Update dataset information
function updateDatasetInfo() {
    // Collect multilingual titles
    const title = {
        de: document.getElementById('edit-dataset-title-de').value.trim(),
        fr: document.getElementById('edit-dataset-title-fr').value.trim(),
        it: document.getElementById('edit-dataset-title-it').value.trim(),
        en: document.getElementById('edit-dataset-title-en').value.trim()
    };

    // Collect multilingual descriptions
    const description = {
        de: document.getElementById('edit-dataset-description-de').value.trim(),
        fr: document.getElementById('edit-dataset-description-fr').value.trim(),
        it: document.getElementById('edit-dataset-description-it').value.trim(),
        en: document.getElementById('edit-dataset-description-en').value.trim()
    };

    // Collect identifier
    const identifier = document.getElementById('edit-dataset-identifier').value.trim();

    // Check if at least one title is provided
    const hasTitle = Object.values(title).some(t => t.length > 0);
    if (!hasTitle) {
        alert('At least one title (in any language) is required');
        return;
    }

    fetch('/api/dataset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            description: description,
            identifier: identifier
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Dataset updated.');

            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            showActionError('Error updating dataset', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error updating dataset', error);
    });
}

// Update data element information
function updateDataElementInfo() {
    if (!window.selectedNodeId) {
        alert('No data element selected');
        return;
    }

    const title = {
        de: document.getElementById('edit-data-element-title-de').value.trim(),
        fr: document.getElementById('edit-data-element-title-fr').value.trim(),
        it: document.getElementById('edit-data-element-title-it').value.trim(),
        en: document.getElementById('edit-data-element-title-en').value.trim()
    };

    const localName = title.en || title.de || title.fr || title.it;
    
    // Collect multilingual descriptions
    const description = {
        de: document.getElementById('edit-data-element-description-de').value.trim(),
        fr: document.getElementById('edit-data-element-description-fr').value.trim(),
        it: document.getElementById('edit-data-element-description-it').value.trim(),
        en: document.getElementById('edit-data-element-description-en').value.trim()
    };

    // Collect identifier
    const identifier = document.getElementById('edit-data-element-identifier').value.trim();

    if (!localName) {
        alert('At least one title (in any language) is required');
        return;
    }

    fetch(`/api/data-elements/${window.selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            local_name: localName,
            description: description,
            identifier: identifier
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Data element updated.');
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            showActionError('Error updating data element', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error updating data element', error);
    });
}

// Update node information (for class and concept nodes)
function updateNodeInfo() {
    if (!window.selectedNodeId) {
        alert('No node selected');
        return;
    }

    const title = document.getElementById('edit-node-title').value;
    
    // Check if we're editing a class with multilingual descriptions
    const classDescDe = document.getElementById('edit-class-description-de');
    let description;
    
    if (classDescDe) {
        // Class node with multilingual descriptions
        description = {
            de: classDescDe.value,
            fr: document.getElementById('edit-class-description-fr').value,
            it: document.getElementById('edit-class-description-it').value,
            en: document.getElementById('edit-class-description-en').value
        };
    } else {
        // Fallback to single-language description for other node types or legacy data
        const descField = document.getElementById('edit-node-description');
        description = descField ? descField.value : '';
    }

    if (!title) {
        alert('Title is required');
        return;
    }

    fetch(`/api/nodes/${window.selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            description: description
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Node updated.');
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            showActionError('Error updating node', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error updating node', error);
    });
}

// Unlink data element from I14Y concept
function unlinkDataElementFromConcept() {
    if (!window.selectedNodeId) {
        alert('No data element selected');
        return;
    }

    if (!confirm('Are you sure you want to detach this data element from its I14Y concept?')) {
        return;
    }

    fetch(`/api/data-elements/${window.selectedNodeId}/unlink-concept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Data element detached from concept.');
            
            // Reload the graph and node details
            loadGraphWithD3();
            loadNodeDetails(window.selectedNodeId);
        } else {
            showActionError('Error unlinking data element', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error unlinking data element', error);
    });
}

// Disconnect I14Y dataset
function disconnectI14YDataset() {
    if (!confirm('Are you sure you want to disconnect this dataset from I14Y?')) {
        return;
    }

    fetch('/api/i14y/dataset/disconnect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Dataset disconnected from I14Y.');
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            showActionError('Error disconnecting dataset', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error disconnecting dataset', error);
    });
}

// Disconnect I14Y concept
function disconnectI14YConcept() {
    if (!window.selectedNodeId) {
        alert('No concept selected');
        return;
    }

    if (!confirm('Are you sure you want to disconnect this concept from I14Y?')) {
        return;
    }

    fetch(`/api/nodes/${window.selectedNodeId}/disconnect-i14y`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Concept disconnected from I14Y.');
            
            // Reload the graph and node details
            loadGraphWithD3();
            loadNodeDetails(window.selectedNodeId);
        } else {
            showActionError('Error disconnecting concept', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error disconnecting concept', error);
    });
}

// Apply SHACL constraints to selected node
function applyConstraints() {
    if (!window.selectedNodeId) {
        alert('No node selected');
        return;
    }

    // Collect constraint values
    const minLength = document.getElementById('min-length').value;
    const maxLength = document.getElementById('max-length').value;
    const pattern = document.getElementById('pattern').value;
    const inValues = document.getElementById('in-values').value;
    const nodeReference = document.getElementById('node-reference').value;
    const range = document.getElementById('range').value;
    const datatype = document.getElementById('datatype').value;

    // Prepare constraint data
    const constraints = {};

    if (minLength) constraints.min_length = parseInt(minLength);
    if (maxLength) constraints.max_length = parseInt(maxLength);
    if (pattern) constraints.pattern = pattern;
    if (inValues) constraints.in_values = inValues.split(',').map(v => v.trim()).filter(v => v);
    if (nodeReference) constraints.node_reference = nodeReference;
    if (range) constraints.range = range;
    if (datatype) constraints.datatype = datatype;

    fetch(`/api/nodes/${window.selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(constraints)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Constraints applied.');
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            showActionError('Error applying constraints', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error applying constraints', error);
    });
}

// Apply order to data element
function applyOrder() {
    if (!window.selectedNodeId) {
        alert('No node selected');
        return;
    }

    const orderValue = document.getElementById('element-order').value;
    console.log('Applying order - raw value:', orderValue);
    
    // Prepare data - order can be null/empty or a number
    const orderData = {
        order: orderValue && orderValue.trim() !== '' ? parseInt(orderValue) : null
    };
    
    console.log('Sending order data:', orderData);

    fetch(`/api/nodes/${window.selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Order update response:', data);
        if (data.success) {
            showSuccessStatus('Order updated.');
            
            // Reload node details to reflect the change (keep selection)
            loadNodeDetails(window.selectedNodeId);
            // Also reload graph to update visualization
            loadGraphWithD3();
        } else {
            showActionError('Error updating order', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error updating order', error);
    });
}

// Convert class to dataset
function confirmConvertToDataset() {
    if (!window.selectedNodeId) {
        alert('No node selected');
        return;
    }
    
    if (!confirm('Are you sure you want to convert this class to a dataset? This will remove all incoming connections to this node.')) {
        return;
    }
    
    fetch(`/api/nodes/${window.selectedNodeId}/convert-to-dataset`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Class converted to dataset.');
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            showActionError('Error converting class to dataset', getApiErrorMessage(data));
        }
    })
    .catch(error => {
        showActionError('Error converting class to dataset', error);
    });
}

// Export all functions to global scope
window.updateDatasetInfo = updateDatasetInfo;
window.updateDataElementInfo = updateDataElementInfo;
window.updateNodeInfo = updateNodeInfo;
window.applyConstraints = applyConstraints;
window.applyOrder = applyOrder;
window.unlinkDataElementFromConcept = unlinkDataElementFromConcept;
window.disconnectI14YDataset = disconnectI14YDataset;
window.disconnectI14YConcept = disconnectI14YConcept;
window.confirmConvertToDataset = confirmConvertToDataset;
