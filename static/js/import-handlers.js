const IMPORT_DEFAULT_DATASET_NAME = 'Imported Dataset';
const IMPORT_ERROR_NO_FILE = 'No file selected';
const IMPORT_ERROR_DATASET_REQUIRED = 'Dataset name is required';
const IMPORT_SUCCESS_CSV_HTML = '<small><strong>Success:</strong> CSV file imported.</small>';
const IMPORT_SUCCESS_GEOJSON_HTML = '<small><strong>Success:</strong> GeoJSON file imported.</small>';
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
    // Success is visible from the graph update; no status banner needed
}

function getApiErrorMessage(data) {
    return (data && data.error) || 'Unknown error';
}

function showActionError(errorLabel, error) {
    const errorMessage = error && error.message ? error.message : String(error);
    alert(`${errorLabel}: ${errorMessage}`);
    console.error(`${errorLabel}:`, error);
}

function showActionErrorIfNeeded(errorLabel, error, options = {}) {
    if (options.silent) {
        console.error(`${errorLabel}:`, error);
        return;
    }
    showActionError(errorLabel, error);
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

function showGeoJSONImportModal(fileInput) {
    if (!fileInput.files || fileInput.files.length === 0) {
        console.log('No file selected');
        return;
    }

    const file = fileInput.files[0];
    const isGeoJSON = file.name.match(/\.(geojson|json)$/i);
    if (!isGeoJSON) {
        alert('Please select a GeoJSON file (.geojson or .json)');
        fileInput.value = '';
        return;
    }

    const basename = file.name.replace(/\.(geojson|json)$/i, '');
    document.getElementById('geojson-dataset-name').value = basename || IMPORT_DEFAULT_DATASET_NAME;

    new bootstrap.Modal(document.getElementById('geojsonImportModal')).show();
}

function importGeoJSON() {
    const fileData = getRequiredFile('geojson-file');
    if (!fileData) {
        return;
    }

    const { fileInput, file } = fileData;
    const datasetName = getRequiredValue('geojson-dataset-name', IMPORT_ERROR_DATASET_REQUIRED);
    if (!datasetName) {
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);

    runImportRequest({
        url: '/api/import/geojson',
        formData,
        modalId: 'geojsonImportModal',
        successHtml: IMPORT_SUCCESS_GEOJSON_HTML,
        resetFormFields: () => {
            document.getElementById('geojson-dataset-name').value = IMPORT_DEFAULT_DATASET_NAME;
        },
        errorLabel: 'Error importing GeoJSON'
    });

    fileInput.value = '';
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
window.showGeoJSONImportModal = showGeoJSONImportModal;
window.importGeoJSON = importGeoJSON;
window.showXSDImportModal = showXSDImportModal;
window.importXSD = importXSD;

// ---- Excel Import ----

let excelFileForImport = null;

function showExcelImportModal(fileInput) {
    if (!fileInput.files || fileInput.files.length === 0) {
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.match(/\.(xlsx|xls)$/i)) {
        alert('Please select an Excel file (.xlsx or .xls)');
        fileInput.value = '';
        return;
    }

    excelFileForImport = file;

    // Pre-fill dataset name from filename
    const basename = file.name.replace(/\.(xlsx|xls)$/i, '');
    document.getElementById('excel-dataset-name').value = basename || IMPORT_DEFAULT_DATASET_NAME;

    // Fetch sheet names from the server
    document.body.classList.add('loading');
    const formData = new FormData();
    formData.append('file', file);

    fetch('/api/import/excel/sheets', { method: 'POST', body: formData })
        .then(async response => {
            let data;
            try { data = await response.json(); } catch (e) { throw new Error('Invalid server response'); }
            if (!response.ok || !data.success) throw new Error(data.error || 'Unknown error');
            return data;
        })
        .then(data => {
            const sheets = data.sheets;
            const select = document.getElementById('excel-sheet');
            select.innerHTML = '';
            sheets.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });

            // Only show the sheet row when there are multiple sheets
            document.getElementById('excel-sheet-row').style.display = sheets.length > 1 ? '' : 'none';

            new bootstrap.Modal(document.getElementById('excelImportModal')).show();
        })
        .catch(err => {
            showActionError('Error reading Excel file', err);
            excelFileForImport = null;
            fileInput.value = '';
        })
        .finally(() => {
            document.body.classList.remove('loading');
        });
}

function importExcel() {
    if (!excelFileForImport) {
        alert(IMPORT_ERROR_NO_FILE);
        return;
    }

    const datasetName = getRequiredValue('excel-dataset-name', IMPORT_ERROR_DATASET_REQUIRED);
    if (!datasetName) return;

    const sheet = document.getElementById('excel-sheet').value;
    const lang = document.getElementById('excel-lang').value;

    const formData = new FormData();
    formData.append('file', excelFileForImport);
    formData.append('dataset_name', datasetName);
    formData.append('sheet', sheet);
    formData.append('lang', lang);

    runImportRequest({
        url: '/api/import/excel',
        formData,
        modalId: 'excelImportModal',
        successHtml: '<small><strong>Success:</strong> Excel file imported.</small>',
        resetFormFields: () => {
            document.getElementById('excel-dataset-name').value = IMPORT_DEFAULT_DATASET_NAME;
            document.getElementById('excel-lang').value = 'de';
            excelFileForImport = null;
            document.getElementById('excel-file').value = '';
        },
        errorLabel: 'Error importing Excel'
    });
}

window.showExcelImportModal = showExcelImportModal;
window.importExcel = importExcel;

// Update dataset information
function updateDatasetInfo(options = {}) {
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
        if (!options.silent) {
            alert('At least one title (in any language) is required');
        }
        return Promise.resolve(false);
    }

    return fetch('/api/dataset', {
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
            if (options.reloadGraph !== false) {
                loadGraphWithD3();
            }
            return true;
        } else {
            showActionErrorIfNeeded('Error updating dataset', getApiErrorMessage(data), options);
            return false;
        }
    })
    .catch(error => {
        showActionErrorIfNeeded('Error updating dataset', error, options);
        return false;
    });
}

// Update data element information
function updateDataElementInfo(options = {}) {
    if (!window.selectedNodeId) {
        if (!options.silent) {
            alert('No data element selected');
        }
        return Promise.resolve(false);
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
        if (!options.silent) {
            alert('At least one title (in any language) is required');
        }
        return Promise.resolve(false);
    }

    return fetch(`/api/data-elements/${window.selectedNodeId}`, {
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
            if (options.reloadGraph !== false) {
                loadGraphWithD3();
            }
            return true;
        } else {
            showActionErrorIfNeeded('Error updating data element', getApiErrorMessage(data), options);
            return false;
        }
    })
    .catch(error => {
        showActionErrorIfNeeded('Error updating data element', error, options);
        return false;
    });
}

// Update node information (for class and concept nodes)
function updateNodeInfo(options = {}) {
    if (!window.selectedNodeId) {
        if (!options.silent) {
            alert('No node selected');
        }
        return Promise.resolve(false);
    }

    // Check if we're editing a class node (has multilingual title fields)
    const classTitleDe = document.getElementById('edit-class-title-de');
    let title, description, identifier;

    if (classTitleDe) {
        // Class node with multilingual title + identifier + multilingual description
        title = {
            de: classTitleDe.value,
            fr: document.getElementById('edit-class-title-fr').value,
            it: document.getElementById('edit-class-title-it').value,
            en: document.getElementById('edit-class-title-en').value
        };
        identifier = (document.getElementById('edit-class-identifier')?.value || '').trim();
        description = {
            de: document.getElementById('edit-class-description-de').value,
            fr: document.getElementById('edit-class-description-fr').value,
            it: document.getElementById('edit-class-description-it').value,
            en: document.getElementById('edit-class-description-en').value
        };
        if (!title.de && !title.fr && !title.it && !title.en) {
            if (!options.silent) {
                alert('At least one title is required');
            }
            return Promise.resolve(false);
        }
    } else {
        // Concept or other node type with single-language title
        title = document.getElementById('edit-node-title').value;
        if (!title) {
            if (!options.silent) {
                alert('Title is required');
            }
            return Promise.resolve(false);
        }
        const descField = document.getElementById('edit-node-description');
        description = descField ? descField.value : '';
    }

    const payload = { title: title, description: description };
    if (identifier) payload.identifier = identifier;

    return fetch(`/api/nodes/${window.selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Node updated.');
            
            // Reload the graph to show updated information
            if (options.reloadGraph !== false) {
                loadGraphWithD3();
            }
            return true;
        } else {
            showActionErrorIfNeeded('Error updating node', getApiErrorMessage(data), options);
            return false;
        }
    })
    .catch(error => {
        showActionErrorIfNeeded('Error updating node', error, options);
        return false;
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
function applyConstraints(options = {}) {
    if (!window.selectedNodeId) {
        if (!options.silent) {
            alert('No node selected');
        }
        return Promise.resolve(false);
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

    return fetch(`/api/nodes/${window.selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(constraints)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccessStatus('Constraints applied.');
            
            // Reload the graph to show updated information
            if (options.reloadGraph !== false) {
                loadGraphWithD3();
            }
            return true;
        } else {
            showActionErrorIfNeeded('Error applying constraints', getApiErrorMessage(data), options);
            return false;
        }
    })
    .catch(error => {
        showActionErrorIfNeeded('Error applying constraints', error, options);
        return false;
    });
}

// Apply order to data element
function applyOrder(options = {}) {
    if (!window.selectedNodeId) {
        if (!options.silent) {
            alert('No node selected');
        }
        return Promise.resolve(false);
    }

    const orderValue = document.getElementById('element-order').value;
    console.log('Applying order - raw value:', orderValue);
    
    // Prepare data - order can be null/empty or a number
    const orderData = {
        order: orderValue && orderValue.trim() !== '' ? parseInt(orderValue) : null
    };
    
    console.log('Sending order data:', orderData);

    return fetch(`/api/nodes/${window.selectedNodeId}`, {
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
            if (options.reloadNodeDetails !== false) {
                loadNodeDetails(window.selectedNodeId);
            }
            // Also reload graph to update visualization
            if (options.reloadGraph !== false) {
                loadGraphWithD3();
            }
            return true;
        } else {
            showActionErrorIfNeeded('Error updating order', getApiErrorMessage(data), options);
            return false;
        }
    })
    .catch(error => {
        showActionErrorIfNeeded('Error updating order', error, options);
        return false;
    });
}

const AUTO_SAVE_ACTIONS = {
    DATASET: 'dataset',
    DATA_ELEMENT_INFO: 'data_element_info',
    NODE_INFO: 'node_info',
    CONSTRAINTS: 'constraints',
    ORDER: 'order'
};

const AUTO_SAVE_DEBOUNCE_MS = 350;
const AUTO_SAVE_INFO_FIELD_IDS = new Set([
    'edit-dataset-identifier',
    'edit-dataset-title-de',
    'edit-dataset-title-fr',
    'edit-dataset-title-it',
    'edit-dataset-title-en',
    'edit-dataset-description-de',
    'edit-dataset-description-fr',
    'edit-dataset-description-it',
    'edit-dataset-description-en',
    'edit-data-element-identifier',
    'edit-data-element-title-de',
    'edit-data-element-title-fr',
    'edit-data-element-title-it',
    'edit-data-element-title-en',
    'edit-data-element-description-de',
    'edit-data-element-description-fr',
    'edit-data-element-description-it',
    'edit-data-element-description-en',
    'edit-class-identifier',
    'edit-class-title-de',
    'edit-class-title-fr',
    'edit-class-title-it',
    'edit-class-title-en',
    'edit-class-description-de',
    'edit-class-description-fr',
    'edit-class-description-it',
    'edit-class-description-en',
    'edit-node-title',
    'edit-node-description'
]);

const AUTO_SAVE_CONSTRAINT_FIELD_IDS = new Set([
    'min-length',
    'max-length',
    'pattern',
    'in-values',
    'node-reference',
    'range'
]);

let autoSaveTimer = null;
let autoSaveInFlight = false;
let pendingAutoSaveActions = new Set();

function getAutoSaveActionForElement(element) {
    if (!element || !element.id) {
        return null;
    }

    if (element.id === 'element-order') {
        return AUTO_SAVE_ACTIONS.ORDER;
    }

    if (AUTO_SAVE_CONSTRAINT_FIELD_IDS.has(element.id)) {
        return AUTO_SAVE_ACTIONS.CONSTRAINTS;
    }

    if (AUTO_SAVE_INFO_FIELD_IDS.has(element.id)) {
        if (element.id.startsWith('edit-dataset-')) {
            return AUTO_SAVE_ACTIONS.DATASET;
        }
        if (element.id.startsWith('edit-data-element-')) {
            return AUTO_SAVE_ACTIONS.DATA_ELEMENT_INFO;
        }
        return AUTO_SAVE_ACTIONS.NODE_INFO;
    }

    return null;
}

function scheduleAutoSaveAction(action) {
    if (!action) {
        return;
    }

    pendingAutoSaveActions.add(action);

    if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
    }

    autoSaveTimer = setTimeout(flushAutoSaveActions, AUTO_SAVE_DEBOUNCE_MS);
}

async function flushAutoSaveActions() {
    if (!window.selectedNodeId || pendingAutoSaveActions.size === 0) {
        pendingAutoSaveActions.clear();
        return;
    }

    if (autoSaveInFlight) {
        return;
    }

    autoSaveInFlight = true;
    autoSaveTimer = null;

    const actionsToRun = new Set(pendingAutoSaveActions);
    pendingAutoSaveActions.clear();

    const actionOrder = [
        AUTO_SAVE_ACTIONS.DATASET,
        AUTO_SAVE_ACTIONS.DATA_ELEMENT_INFO,
        AUTO_SAVE_ACTIONS.NODE_INFO,
        AUTO_SAVE_ACTIONS.CONSTRAINTS,
        AUTO_SAVE_ACTIONS.ORDER
    ];

    let hasSuccessfulUpdate = false;
    const updateOptions = { silent: true, reloadGraph: false, reloadNodeDetails: false };

    for (const action of actionOrder) {
        if (!actionsToRun.has(action)) {
            continue;
        }

        let result = false;
        if (action === AUTO_SAVE_ACTIONS.DATASET) {
            result = await updateDatasetInfo(updateOptions);
        } else if (action === AUTO_SAVE_ACTIONS.DATA_ELEMENT_INFO) {
            result = await updateDataElementInfo(updateOptions);
        } else if (action === AUTO_SAVE_ACTIONS.NODE_INFO) {
            result = await updateNodeInfo(updateOptions);
        } else if (action === AUTO_SAVE_ACTIONS.CONSTRAINTS) {
            result = await applyConstraints(updateOptions);
        } else if (action === AUTO_SAVE_ACTIONS.ORDER) {
            result = await applyOrder(updateOptions);
        }

        hasSuccessfulUpdate = hasSuccessfulUpdate || !!result;
    }

    if (hasSuccessfulUpdate) {
        loadGraphWithD3();
    }

    autoSaveInFlight = false;

    // Process fields edited while the previous save was running.
    if (pendingAutoSaveActions.size > 0) {
        scheduleAutoSaveAction(Array.from(pendingAutoSaveActions)[0]);
    }
}

function setupAutoSaveOnBlur() {
    if (window.__autoSaveOnBlurInitialized) {
        return;
    }

    document.addEventListener('focusout', event => {
        const action = getAutoSaveActionForElement(event.target);
        if (!action) {
            return;
        }

        scheduleAutoSaveAction(action);
    }, true);

    window.__autoSaveOnBlurInitialized = true;
}

setupAutoSaveOnBlur();

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
