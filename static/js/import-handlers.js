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
    const encoding = document.getElementById('csv-encoding').value;
    
    if (!datasetName) {
        alert('Dataset name is required');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);
    formData.append('lang', lang);
    formData.append('encoding', encoding);
    
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Dataset updated.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }

            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            alert('Error updating dataset: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error updating dataset: ' + error.message);
        console.error('Error updating dataset:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Data element updated.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            alert('Error updating data element: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error updating data element: ' + error.message);
        console.error('Error updating data element:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Node updated.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            alert('Error updating node: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error updating node: ' + error.message);
        console.error('Error updating node:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Data element detached from concept.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph and node details
            loadGraphWithD3();
            loadNodeDetails(window.selectedNodeId);
        } else {
            alert('Error unlinking data element: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error unlinking data element: ' + error.message);
        console.error('Error unlinking data element:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Dataset disconnected from I14Y.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            alert('Error disconnecting dataset: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error disconnecting dataset: ' + error.message);
        console.error('Error disconnecting dataset:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Concept disconnected from I14Y.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph and node details
            loadGraphWithD3();
            loadNodeDetails(window.selectedNodeId);
        } else {
            alert('Error disconnecting concept: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error disconnecting concept: ' + error.message);
        console.error('Error disconnecting concept:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Constraints applied.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            alert('Error applying constraints: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error applying constraints: ' + error.message);
        console.error('Error applying constraints:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Order updated.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload node details to reflect the change (keep selection)
            loadNodeDetails(window.selectedNodeId);
            // Also reload graph to update visualization
            loadGraphWithD3();
        } else {
            alert('Error updating order: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error updating order: ' + error.message);
        console.error('Error updating order:', error);
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
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Class converted to dataset.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            
            // Reload the graph to show updated information
            loadGraphWithD3();
        } else {
            alert('Error converting class to dataset: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error converting class to dataset: ' + error.message);
        console.error('Error converting class to dataset:', error);
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
