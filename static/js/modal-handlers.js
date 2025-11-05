// Modal handlers for the SHACL creator with JointJS
// This file contains the implementations of the modal functions that were missing in the JointJS implementation

// Show Add Class Modal
function showAddClassModal() {
    // Clear previous values
    document.getElementById('class-title').value = '';
    document.getElementById('class-description-de').value = '';
    document.getElementById('class-description-fr').value = '';
    document.getElementById('class-description-it').value = '';
    document.getElementById('class-description-en').value = '';
    
    // Show the modal
    new bootstrap.Modal(document.getElementById('addClassModal')).show();
}

// Add Class from Modal
function addClass() {
    const title = document.getElementById('class-title').value;
    const descriptionDe = document.getElementById('class-description-de').value;
    const descriptionFr = document.getElementById('class-description-fr').value;
    const descriptionIt = document.getElementById('class-description-it').value;
    const descriptionEn = document.getElementById('class-description-en').value;

    if (!title) {
        alert('Title is required');
        return;
    }

    // Build multilingual description object
    const description = {
        de: descriptionDe,
        fr: descriptionFr,
        it: descriptionIt,
        en: descriptionEn
    };

    fetch('/api/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: 'class',
            title: title,
            description: description
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('addClassModal')).hide();
            
            // Clear form fields
            document.getElementById('class-title').value = '';
            document.getElementById('class-description-de').value = '';
            document.getElementById('class-description-fr').value = '';
            document.getElementById('class-description-it').value = '';
            document.getElementById('class-description-en').value = '';
            
            // Reload the graph with D3.js
            loadGraphWithD3();
        } else {
            alert('Error adding class: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding class');
    });
}

// Global variable to store selected concept for data element
let selectedConceptForDataElement = null;

// Show Add Data Element Modal
function showAddDataElementModal() {
    // Clear previous state
    document.getElementById('data-element-title').value = '';
    document.getElementById('data-element-description').value = '';
    document.getElementById('data-element-concept-search').value = '';
    document.getElementById('data-element-concept-results').style.display = 'none';
    document.getElementById('data-element-selected-concept').style.display = 'none';
    selectedConceptForDataElement = null;
    
    // Clear the displayed concept information
    document.getElementById('selected-concept-name').textContent = '';
    document.getElementById('selected-concept-publisher').textContent = '';
    document.getElementById('selected-concept-id').textContent = '';
    
    // Show the modal
    new bootstrap.Modal(document.getElementById('addDataElementModal')).show();
}

// Search for concepts when adding a data element
function searchConceptsForDataElement() {
    const query = document.getElementById('data-element-concept-search').value;
    if (!query) return;

    const resultsDiv = document.getElementById('data-element-concept-results');
    resultsDiv.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Searching...</div>';
    resultsDiv.style.display = 'block';

    fetch(`/api/i14y/search?query=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            resultsDiv.innerHTML = '';
            
            // The API returns an object with concepts array
            const concepts = data.concepts || [];
            if (concepts.length === 0) {
                resultsDiv.innerHTML = '<div class="text-muted">No concepts found</div>';
                return;
            }

            concepts.forEach(concept => {
                // Handle multilingual fields properly
                const title = getMultilingualText(concept.title) || 'Untitled';
                const description = getMultilingualText(concept.description) || 'No description';
                
                const conceptDiv = document.createElement('div');
                conceptDiv.className = 'border p-2 mb-2 concept-result';
                conceptDiv.style.cursor = 'pointer';
                conceptDiv.innerHTML = `
                    <strong>${escapeHtml(title)}</strong>
                    <div class="small text-muted">${escapeHtml(description)}</div>
                    <div class="small"><strong>ID:</strong> ${escapeHtml(concept.id)}</div>
                `;
                conceptDiv.onclick = () => selectConceptForDataElement(concept);
                resultsDiv.appendChild(conceptDiv);
            });
        })
        .catch(error => {
            resultsDiv.innerHTML = '<div class="text-danger">Error searching concepts</div>';
            console.error('Error:', error);
        });
}

// Select a concept for the data element
function selectConceptForDataElement(concept) {
    selectedConceptForDataElement = concept;
    document.getElementById('data-element-concept-results').style.display = 'none';
    
    // Extract proper title using multilingual text function
    const title = getMultilingualText(concept.title) || 'Untitled';
    const publisher = getMultilingualText(concept.publisherName) || 'Unknown Publisher';
    const conceptId = concept.id || 'Unknown ID';
    
    document.getElementById('selected-concept-name').textContent = title;
    document.getElementById('selected-concept-publisher').textContent = `Publisher: ${publisher}`;
    document.getElementById('selected-concept-id').textContent = conceptId;
    
    document.getElementById('data-element-selected-concept').style.display = 'block';
}

// Clear the selected concept
function clearSelectedConcept() {
    selectedConceptForDataElement = null;
    document.getElementById('data-element-selected-concept').style.display = 'none';
    document.getElementById('data-element-concept-results').style.display = 'none';
    
    // Clear the displayed information
    document.getElementById('selected-concept-name').textContent = '';
    document.getElementById('selected-concept-publisher').textContent = '';
    document.getElementById('selected-concept-id').textContent = '';
}

// Add Data Element from Modal
function addDataElement() {
    const title = document.getElementById('data-element-title').value;
    const description = document.getElementById('data-element-description').value;

    if (!title) {
        alert('Local name is required');
        return;
    }

    // Determine if a class is selected as parent
    let parentId = null;
    if (selectedNode) {
        // Check if the selected node is a class using the D3 nodes data
        const selectedNodeData = nodes.find(n => n.id === selectedNode);
        if (selectedNodeData && selectedNodeData.type === 'class') {
            parentId = selectedNode;
        }
        
        const payload = {
            type: 'data_element',
            title: title,
            description: description,
            local_name: title,
            parent_id: parentId
        };

        // If a concept is selected, include it
        if (selectedConceptForDataElement) {
            payload.concept_data = selectedConceptForDataElement;
        }

        fetch('/api/data-elements', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Hide the modal
                bootstrap.Modal.getInstance(document.getElementById('addDataElementModal')).hide();
                
                // Reload the graph with D3.js
                loadGraphWithD3();
            } else {
                alert('Error creating data element: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error creating data element: ' + error.message);
        });
    } else {
        // No parent selected - create data element attached to dataset
        const payload = {
            type: 'data_element',
            title: title,
            description: description,
            local_name: title
        };

        // If a concept is selected, include it
        if (selectedConceptForDataElement) {
            payload.concept_data = selectedConceptForDataElement;
        }

        fetch('/api/data-elements', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Hide the modal
                bootstrap.Modal.getInstance(document.getElementById('addDataElementModal')).hide();
                
                // Reload the graph with D3.js
                loadGraphWithD3();
            } else {
                alert('Error creating data element: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error creating data element: ' + error.message);
        });
    }
}

// Additional functions for the JointJS integration

// Function to show confirmation dialog before removing elements
function removeSelected() {
    if (!selectedNodeId && !selectedEdgeId) {
        alert('No element selected');
        return;
    }
    
    const confirmMessage = selectedNodeId 
        ? 'Are you sure you want to remove the selected node?' 
        : 'Are you sure you want to remove the selected connection?';
    
    if (confirm(confirmMessage)) {
        if (selectedNodeId) {
            // Remove node
            fetch(`/api/nodes/${selectedNodeId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    selectedNodeId = null;
                    clearNodeSelection();
                    loadGraphWithD3();
                } else {
                    alert('Error removing node: ' + (data.error || 'Unknown error'));
                }
            });
        } else if (selectedEdgeId) {
            // Remove edge
            fetch(`/api/edges/${selectedEdgeId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    selectedEdgeId = null;
                    clearEdgeSelection();
                    loadGraphWithD3();
                } else {
                    alert('Error removing connection: ' + (data.error || 'Unknown error'));
                }
            });
        }
    }
}

// For connection mode
// Define as a global variable that can be accessed from other scripts
window.connectionMode = false;
let connectionSource = null;

// Toggle connection mode for creating connections between nodes
function toggleConnectionMode() {
    window.connectionMode = !window.connectionMode;
    
    if (window.connectionMode) {
        // Entering connection mode
        document.getElementById('connection-status').style.display = 'block';
        connectionSource = null;
    } else {
        // Exiting connection mode
        document.getElementById('connection-status').style.display = 'none';
        connectionSource = null;
    }
}

// Function to detach selected connection
function detachSelected() {
    if (!selectedEdgeId) {
        alert('No connection selected');
        return;
    }
    
    if (confirm('Are you sure you want to detach this connection?')) {
        fetch(`/api/edges/${selectedEdgeId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                selectedEdgeId = null;
                clearEdgeSelection();
                loadGraphWithD3();
            } else {
                alert('Error detaching connection: ' + (data.error || 'Unknown error'));
            }
        });
    }
}

// I14Y Integration functions

// Function to search I14Y
function searchI14Y() {
    const query = document.getElementById('i14y-search-query').value;
    if (!query) return;

    const resultsDiv = document.getElementById('i14y-results');
    resultsDiv.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div> Searching...</div>';

    fetch(`/api/i14y/search?query=${encodeURIComponent(query)}`)
    .then(response => response.json())
    .then(data => {
        resultsDiv.innerHTML = '';
        
        const concepts = data.concepts || [];
        if (concepts.length === 0) {
            resultsDiv.innerHTML = '<div class="alert alert-info">No concepts found</div>';
            return;
        }

        concepts.forEach(concept => {
            const title = getMultilingualText(concept.title) || 'Untitled';
            const description = getMultilingualText(concept.description) || 'No description';
            const publisher = getMultilingualText(concept.publisherName) || 'Unknown Publisher';
            
            const conceptCard = document.createElement('div');
            conceptCard.className = 'card mb-3';
            conceptCard.innerHTML = `
                <div class="card-body">
                    <h5 class="card-title">${escapeHtml(title)}</h5>
                    <h6 class="card-subtitle mb-2 text-muted">${escapeHtml(publisher)}</h6>
                    <p class="card-text small">${escapeHtml(description)}</p>
                    <button class="btn btn-outline-primary btn-sm" onclick='addI14YConcept(${JSON.stringify(concept)})'>Add Concept</button>
                    <button class="btn btn-outline-secondary btn-sm" onclick='createDataElementFromConcept(${JSON.stringify(concept)})'>Create Data Element</button>
                </div>
            `;
            resultsDiv.appendChild(conceptCard);
        });
    })
    .catch(error => {
        resultsDiv.innerHTML = `<div class="alert alert-danger">Error searching I14Y: ${error.message}</div>`;
    });
}

// Link to I14Y Concept Modal handler
function showLinkToI14YModal() {
    // This function will be called when the "Link to I14Y Concept" button is clicked
    new bootstrap.Modal(document.getElementById('linkToI14YModal')).show();
    searchForI14YLink(''); // Load initial results
}

// Global variable to store the latest link search results
let lastLinkI14YSearchResults = [];

function searchForI14YLink(query = null) {
    if (query === null) {
        query = document.getElementById('link-i14y-search-query').value;
    }

    const resultsDiv = document.getElementById('link-i14y-results');
    resultsDiv.innerHTML = '<p class="text-muted">Searching...</p>';

    fetch(`/api/i14y/search?query=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            // Log the response structure
            console.log('I14Y search response:', data);
            console.log('First concept (if any):', data.concepts && data.concepts.length > 0 ? data.concepts[0] : 'No concepts found');
            
            // Use data.concepts instead of data.results
            const results = data.concepts || [];
            lastLinkI14YSearchResults = results;
            
            if (results.length === 0) {
                resultsDiv.innerHTML = '<p class="text-muted">No results found</p>';
                return;
            }
            
            let html = '<div class="list-group">';
            results.forEach((result, index) => {
                // Extract title from multilingual structure or use identifier
                let title = 'Unnamed Concept';
                if (typeof result.title === 'object') {
                    // Try to get from multilingual object
                    title = result.title.en || result.title.de || result.title.fr || result.title.it || 
                            Object.values(result.title)[0] || title;
                } else if (typeof result.title === 'string') {
                    title = result.title;
                } else if (result.identifiers && result.identifiers.length > 0) {
                    title = result.identifiers[0].notation;
                } else if (result.identifier) {
                    title = result.identifier;
                }
                
                // Extract description from multilingual structure
                let description = 'No description available';
                if (typeof result.description === 'object') {
                    description = result.description.en || result.description.de || 
                                 result.description.fr || result.description.it || 
                                 Object.values(result.description)[0] || description;
                } else if (typeof result.description === 'string') {
                    description = result.description;
                }
                
                // Get type or default to 'Concept'
                const type = result.type || 'Concept';
                
                // Extract publisher information
                let publisher = 'Unknown publisher';
                
                // Try all possible publisher properties and formats
                if (result.publisherName) {
                    // Direct publisherName property (often found in I14Y API)
                    if (typeof result.publisherName === 'object') {
                        publisher = result.publisherName.en || result.publisherName.de || 
                                   result.publisherName.fr || result.publisherName.it ||
                                   Object.values(result.publisherName)[0] || publisher;
                    } else if (typeof result.publisherName === 'string') {
                        publisher = result.publisherName;
                    }
                } else if (result.publisher) {
                    // Structured publisher object
                    if (typeof result.publisher === 'object') {
                        if (result.publisher.name) {
                            // Publisher with name property
                            if (typeof result.publisher.name === 'object') {
                                publisher = result.publisher.name.en || result.publisher.name.de || 
                                           result.publisher.name.fr || result.publisher.name.it ||
                                           Object.values(result.publisher.name)[0] || publisher;
                            } else if (typeof result.publisher.name === 'string') {
                                publisher = result.publisher.name;
                            }
                        } else if (result.publisher.title) {
                            // Publisher with title property
                            if (typeof result.publisher.title === 'object') {
                                publisher = result.publisher.title.en || result.publisher.title.de || 
                                           result.publisher.title.fr || result.publisher.title.it ||
                                           Object.values(result.publisher.title)[0] || publisher;
                            } else if (typeof result.publisher.title === 'string') {
                                publisher = result.publisher.title;
                            }
                        } else {
                            // Try to extract from top level publisher object
                            const publisherValue = Object.values(result.publisher).find(v => 
                                typeof v === 'string' || 
                                (typeof v === 'object' && (v.de || v.en || v.fr || v.it))
                            );
                            
                            if (publisherValue) {
                                if (typeof publisherValue === 'object') {
                                    publisher = publisherValue.de || publisherValue.en || 
                                               publisherValue.fr || publisherValue.it ||
                                               Object.values(publisherValue)[0] || publisher;
                                } else {
                                    publisher = publisherValue;
                                }
                            }
                        }
                    } else if (typeof result.publisher === 'string') {
                        publisher = result.publisher;
                    }
                } else if (result.creator) {
                    // Fallback to creator if publisher is not available
                    if (typeof result.creator === 'object' && result.creator.name) {
                        if (typeof result.creator.name === 'object') {
                            publisher = result.creator.name.en || result.creator.name.de || 
                                       result.creator.name.fr || result.creator.name.it ||
                                       Object.values(result.creator.name)[0] || publisher;
                        } else if (typeof result.creator.name === 'string') {
                            publisher = result.creator.name;
                        }
                    } else if (typeof result.creator === 'string') {
                        publisher = result.creator;
                    }
                }
                
                // Get URI or construct one from id
                const uri = result.uri || 
                           result.id && `https://www.i14y.admin.ch/de/catalog/concepts/${result.id}/description` || 
                           '#';
                
                html += `
                    <a href="#" class="list-group-item list-group-item-action" onclick="selectI14YLinkResult(${index})">
                        <div class="d-flex justify-content-between align-items-center">
                            <h6 class="mb-1">${title}</h6>
                            <span class="badge bg-primary">${type}</span>
                        </div>
                        <p class="mb-1 small">${description}</p>
                        <div class="d-flex justify-content-between align-items-center mt-1">
                            <small class="text-muted">${uri}</small>
                            <span class="badge bg-secondary">${publisher}</span>
                        </div>
                    </a>
                `;
            });
            html += '</div>';
            resultsDiv.innerHTML = html;
        })
        .catch(error => {
            console.error('Error searching I14Y:', error);
            resultsDiv.innerHTML = `<p class="text-danger">Error: ${error.message}</p>`;
        });
}

function selectI14YLinkResult(index) {
    const result = lastLinkI14YSearchResults[index];
    if (!result) return;
    
    // Get the currently selected node
    const selectedNodeIds = Array.from(selectedNodes);
    if (selectedNodeIds.length !== 1) {
        alert('Please select exactly one data element to link');
        return;
    }
    
    // Make sure we're getting just the node ID string, not the full node object
    let nodeId = selectedNodeIds[0];
    console.log('Raw selected node ID for linking:', nodeId, typeof nodeId);
    
    // Extract ID if it's an object with an id property
    if (typeof nodeId === 'object' && nodeId !== null && 'id' in nodeId) {
        nodeId = nodeId.id;
    }
    
    console.log('Processed node ID for linking:', nodeId, typeof nodeId);
    
    // Extract or construct URI
    const uri = result.uri || 
               result.id && `https://www.i14y.admin.ch/de/catalog/concepts/${result.id}/description` || 
               '#';
               
    // Prepare title for display
    let title = 'Unnamed Concept';
    if (typeof result.title === 'object') {
        title = result.title.en || result.title.de || result.title.fr || 
                result.title.it || Object.values(result.title)[0] || title;
    } else if (typeof result.title === 'string') {
        title = result.title;
    } else if (result.identifiers && result.identifiers.length > 0) {
        title = result.identifiers[0].notation;
    } else if (result.identifier) {
        title = result.identifier;
    }
    
    // Prepare description - keep multilingual structure for backend
    let description = result.description;
    if (typeof result.description === 'string') {
        // If it's a string, convert to multilingual object with German as default
        description = { de: result.description };
    } else if (typeof result.description === 'object') {
        // Keep the full multilingual object
        description = result.description;
    } else {
        // Fallback to empty multilingual object
        description = { de: '' };
    }
    
    // Extract publisher information
    let publisher = 'Unknown publisher';
    
    // Try all possible publisher properties and formats
    if (result.publisherName) {
        // Direct publisherName property (often found in I14Y API)
        if (typeof result.publisherName === 'object') {
            publisher = result.publisherName.en || result.publisherName.de || 
                       result.publisherName.fr || result.publisherName.it ||
                       Object.values(result.publisherName)[0] || publisher;
        } else if (typeof result.publisherName === 'string') {
            publisher = result.publisherName;
        }
    } else if (result.publisher) {
        // Structured publisher object
        if (typeof result.publisher === 'object') {
            if (result.publisher.name) {
                // Publisher with name property
                if (typeof result.publisher.name === 'object') {
                    publisher = result.publisher.name.en || result.publisher.name.de || 
                               result.publisher.name.fr || result.publisher.name.it ||
                               Object.values(result.publisher.name)[0] || publisher;
                } else if (typeof result.publisher.name === 'string') {
                    publisher = result.publisher.name;
                }
            } else if (result.publisher.title) {
                // Publisher with title property
                if (typeof result.publisher.title === 'object') {
                    publisher = result.publisher.title.en || result.publisher.title.de || 
                               result.publisher.title.fr || result.publisher.title.it ||
                               Object.values(result.publisher.title)[0] || publisher;
                } else if (typeof result.publisher.title === 'string') {
                    publisher = result.publisher.title;
                }
            } else {
                // Try to extract from top level publisher object
                const publisherValue = Object.values(result.publisher).find(v => 
                    typeof v === 'string' || 
                    (typeof v === 'object' && (v.de || v.en || v.fr || v.it))
                );
                
                if (publisherValue) {
                    if (typeof publisherValue === 'object') {
                        publisher = publisherValue.de || publisherValue.en || 
                                   publisherValue.fr || publisherValue.it ||
                                   Object.values(publisherValue)[0] || publisher;
                    } else {
                        publisher = publisherValue;
                    }
                }
            }
        } else if (typeof result.publisher === 'string') {
            publisher = result.publisher;
        }
    } else if (result.creator) {
        // Fallback to creator if publisher is not available
        if (typeof result.creator === 'object' && result.creator.name) {
            if (typeof result.creator.name === 'object') {
                publisher = result.creator.name.en || result.creator.name.de || 
                           result.creator.name.fr || result.creator.name.it ||
                           Object.values(result.creator.name)[0] || publisher;
            } else if (typeof result.creator.name === 'string') {
                publisher = result.creator.name;
            }
        } else if (typeof result.creator === 'string') {
            publisher = result.creator;
        }
    }
    
    // Prepare sanitized concept data with string values
    const sanitizedConcept = {
        id: result.id,
        uri: uri,
        title: title,
        description: description,
        type: result.type || 'Concept',
        publisherName: publisher  // Use publisherName to match UI expectations
    };
    
    // Send the link request to the server
    console.log('Sending node ID for linking:', nodeId, typeof nodeId);
    
    fetch('/api/link/i14y', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            node_id: nodeId,
            concept_uri: uri,
            concept_data: sanitizedConcept
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('linkToI14YModal')).hide();
            
            // Reload the graph
            loadGraphWithD3();
            
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Node linked to I14Y concept.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
        } else {
            alert('Error linking to I14Y: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error linking to I14Y: ' + error.message);
        console.error('Error linking to I14Y:', error);
    });
}

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

// Export functions and ensure they're globally available
window.showAddClassModal = showAddClassModal;
window.addClass = addClass;
window.showAddDataElementModal = showAddDataElementModal;
window.searchConceptsForDataElement = searchConceptsForDataElement;
window.selectConceptForDataElement = selectConceptForDataElement;
window.clearSelectedConcept = clearSelectedConcept;
window.addDataElement = addDataElement;
window.removeSelected = removeSelected;
window.toggleConnectionMode = toggleConnectionMode;
window.detachSelected = detachSelected;
window.searchI14Y = searchI14Y;
window.exportTTL = exportTTL;
window.importTTL = importTTL;
window.showCSVImportModal = showCSVImportModal;
window.importCSV = importCSV;
window.showXSDImportModal = showXSDImportModal;
window.importXSD = importXSD;

// Additional I14Y functions
function addI14YConcept(concept) {
    fetch('/api/i14y/add-concept', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept: concept })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('i14ySearchModal')).hide();
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            alert('Error adding I14Y concept: ' + (data.error || 'Unknown error'));
        }
    });
}

function createDataElementFromConcept(concept) {
    const localName = prompt('Enter local name for this data element:', getMultilingualText(concept.title));
    if (!localName) return;
    
    fetch('/api/i14y/create-data-element', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            concept: concept,
            local_name: localName,
            parent_id: selectedNode // Connect to selected node if any
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('i14ySearchModal')).hide();
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            alert('Error creating data element: ' + (data.error || 'Unknown error'));
        }
    });
}

// Project management functions
function createNewStructure() {
    if (confirm('Are you sure you want to create a new empty structure? This will delete all current data.')) {
        fetch('/api/reset', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadGraphWithD3();
            } else {
                alert('Error creating new structure');
            }
        });
    }
}

function saveProject() {
    fetch('/api/project/save', {
        method: 'GET'
    })
    .then(response => {
        if (!response.ok) {
            // If the response is not ok, try to read it as text to show the error
            return response.text().then(text => {
                throw new Error(`Save failed: ${response.status} ${response.statusText} - ${text}`);
            });
        }
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'shacl_project.json';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        
        // Show success message
        const status = document.getElementById('selection-status');
        if (status) {
            status.style.display = 'block';
            status.innerHTML = '<small><strong>Success:</strong> Project saved.</small>';
            setTimeout(() => { status.style.display = 'none'; }, 3000);
        }
    })
    .catch(error => {
        console.error('Save error:', error);
        const status = document.getElementById('selection-status');
        if (status) {
            status.style.display = 'block';
            status.innerHTML = `<small><strong>Error:</strong> ${error.message}</small>`;
        }
    });
}

function loadProject(fileInput) {
    const file = fileInput.files[0];
    if (!file) {
        console.log('No file selected');
        return;
    }
    
    console.log('File selected:', file.name, 'Size:', file.size, 'Type:', file.type);
    
    // Validate file type
    if (!file.name.endsWith('.json')) {
        alert('Please select a JSON file');
        fileInput.value = '';
        return;
    }
    
    // Read file content to verify it's valid JSON before sending
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const content = e.target.result;
            console.log('File content preview:', content.substring(0, 200));
            
            // Try to parse as JSON to validate
            JSON.parse(content);
            console.log('File is valid JSON');
            
            // Now send the file
            const formData = new FormData();
            formData.append('file', file);
            
            console.log('Sending FormData with file:', file.name);
            
            fetch('/api/project/load', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('Response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Server response:', data);
                const status = document.getElementById('selection-status');
                if (data.success) {
                    if (status) {
                        status.style.display = 'block';
                        status.innerHTML = '<small><strong>Success:</strong> Project loaded.</small>';
                        setTimeout(() => { status.style.display = 'none'; }, 3000);
                    }
                    loadGraphWithD3();
                } else {
                    if (status) {
                        status.style.display = 'block';
                        status.innerHTML = `<small><strong>Error:</strong> ${data.error || 'Unknown error'}</small>`;
                    }
                }
            })
            .catch(error => {
                console.error('Upload error:', error);
                const status = document.getElementById('selection-status');
                if (status) {
                    status.style.display = 'block';
                    status.innerHTML = `<small><strong>Error:</strong> ${error.message}</small>`;
                }
            });
        } catch (parseError) {
            console.error('Invalid JSON file:', parseError);
            alert('The selected file is not valid JSON');
            fileInput.value = '';
        }
    };
    
    reader.onerror = function() {
        console.error('File reading error');
        alert('Error reading the selected file');
        fileInput.value = '';
    };
    
    reader.readAsText(file);
}

function exportTTL() {
    fetch('/api/export/ttl', {
        method: 'GET'
    })
    .then(response => response.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'shacl_export.ttl';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    });
}

function importTTL(fileInput) {
    if (!fileInput.files || fileInput.files.length === 0) {
        console.log('No file selected');
        return;
    }
    const file = fileInput.files[0];
    if (!file.name.endsWith('.ttl')) {
        // Show error in status area
        const status = document.getElementById('selection-status');
        if (status) {
            status.style.display = 'block';
            status.innerHTML = '<small><strong>Error:</strong> Please select a TTL file.</small>';
        }
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    document.body.classList.add('loading');
    fetch('/api/import/ttl', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.body.classList.remove('loading');
        const status = document.getElementById('selection-status');
        if (data.success) {
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> TTL file imported.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
            loadGraphWithD3();
        } else {
            if (status) {
                status.style.display = 'block';
                status.innerHTML = `<small><strong>Error:</strong> ${data.error || 'Unknown error'}</small>`;
            }
        }
    })
    .catch(error => {
        document.body.classList.remove('loading');
        const status = document.getElementById('selection-status');
        if (status) {
            status.style.display = 'block';
            status.innerHTML = `<small><strong>Error importing TTL:</strong> ${error.message}</small>`;
        }
        console.error('Error importing TTL:', error);
    });
    fileInput.value = '';
}

// Export functions to global scope
window.showLinkToI14YModal = showLinkToI14YModal;
window.searchForI14YLink = searchForI14YLink;
window.selectI14YLinkResult = selectI14YLinkResult;

// I14Y Dataset Search Modal handler
function showI14YDatasetSearchModal() {
    // This function will be called when the "Link to I14Y Dataset" button is clicked
    new bootstrap.Modal(document.getElementById('i14yDatasetSearchModal')).show();
    searchI14YDatasets(''); // Load initial results
}

// Global variable to store the latest dataset search results
let lastI14YDatasetSearchResults = [];

function searchI14YDatasets(query = null) {
    if (query === null) {
        query = document.getElementById('i14y-dataset-search-query').value;
    }

    const resultsDiv = document.getElementById('i14y-dataset-results');
    resultsDiv.innerHTML = '<p class="text-muted">Searching...</p>';

    fetch(`/api/i14y/dataset/search?query=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            // Log the response structure
            console.log('I14Y dataset search response:', data);
            console.log('First dataset (if any):', data.datasets && data.datasets.length > 0 ? data.datasets[0] : 'No datasets found');
            
            // Use data.datasets instead of data.results
            const results = data.datasets || [];
            lastI14YDatasetSearchResults = results;
            
            if (results.length === 0) {
                resultsDiv.innerHTML = '<p class="text-muted">No results found</p>';
                return;
            }
            
            let html = '<div class="list-group">';
            results.forEach((result, index) => {
                // Extract title from multilingual structure or use identifier
                let title = 'Unnamed Dataset';
                if (typeof result.title === 'object') {
                    // Try to get from multilingual object
                    title = result.title.en || result.title.de || result.title.fr || result.title.it || 
                            Object.values(result.title)[0] || title;
                } else if (typeof result.title === 'string') {
                    title = result.title;
                } else if (result.identifiers && result.identifiers.length > 0) {
                    title = result.identifiers[0].notation;
                } else if (result.identifier) {
                    title = result.identifier;
                }
                
                // Extract description from multilingual structure
                let description = 'No description available';
                if (typeof result.description === 'object') {
                    description = result.description.en || result.description.de || 
                                 result.description.fr || result.description.it || 
                                 Object.values(result.description)[0] || description;
                } else if (typeof result.description === 'string') {
                    description = result.description;
                }
                
                // Get type or default to 'Dataset'
                const type = result.type || 'Dataset';
                
                // Extract publisher information
                let publisher = 'Unknown publisher';
                
                // Try all possible publisher properties and formats
                if (result.publisherName) {
                    // Direct publisherName property (often found in I14Y API)
                    if (typeof result.publisherName === 'object') {
                        publisher = result.publisherName.en || result.publisherName.de || 
                                   result.publisherName.fr || result.publisherName.it ||
                                   Object.values(result.publisherName)[0] || publisher;
                    } else if (typeof result.publisherName === 'string') {
                        publisher = result.publisherName;
                    }
                } else if (result.publisher) {
                    // Structured publisher object
                    if (typeof result.publisher === 'object') {
                        if (result.publisher.name) {
                            // Publisher with name property
                            if (typeof result.publisher.name === 'object') {
                                publisher = result.publisher.name.en || result.publisher.name.de || 
                                           result.publisher.name.fr || result.publisher.name.it ||
                                           Object.values(result.publisher.name)[0] || publisher;
                            } else if (typeof result.publisher.name === 'string') {
                                publisher = result.publisher.name;
                            }
                        } else if (result.publisher.title) {
                            // Publisher with title property
                            if (typeof result.publisher.title === 'object') {
                                publisher = result.publisher.title.en || result.publisher.title.de || 
                                           result.publisher.title.fr || result.publisher.title.it ||
                                           Object.values(result.publisher.title)[0] || publisher;
                            } else if (typeof result.publisher.title === 'string') {
                                publisher = result.publisher.title;
                            }
                        } else {
                            // Try to extract from top level publisher object
                            const publisherValue = Object.values(result.publisher).find(v => 
                                typeof v === 'string' || 
                                (typeof v === 'object' && (v.de || v.en || v.fr || v.it))
                            );
                            
                            if (publisherValue) {
                                if (typeof publisherValue === 'object') {
                                    publisher = publisherValue.de || publisherValue.en || 
                                               publisherValue.fr || publisherValue.it ||
                                               Object.values(publisherValue)[0] || publisher;
                                } else {
                                    publisher = publisherValue;
                                }
                            }
                        }
                    } else if (typeof result.publisher === 'string') {
                        publisher = result.publisher;
                    }
                } else if (result.creator) {
                    // Fallback to creator if publisher is not available
                    if (typeof result.creator === 'object' && result.creator.name) {
                        if (typeof result.creator.name === 'object') {
                            publisher = result.creator.name.en || result.creator.name.de || 
                                       result.creator.name.fr || result.creator.name.it ||
                                       Object.values(result.creator.name)[0] || publisher;
                        } else if (typeof result.creator.name === 'string') {
                            publisher = result.creator.name;
                        }
                    } else if (typeof result.creator === 'string') {
                        publisher = result.creator;
                    }
                }
                
                // Get URI or construct one from id
                const uri = result.uri || 
                           result.id && `https://www.i14y.admin.ch/de/catalog/datasets/${result.id}/description` || 
                           '#';
                
                html += `
                    <a href="#" class="list-group-item list-group-item-action" onclick="selectI14YDatasetResult(${index})">
                        <div class="d-flex justify-content-between align-items-center">
                            <h6 class="mb-1">${title}</h6>
                            <span class="badge bg-primary">${type}</span>
                        </div>
                        <p class="mb-1 small">${description}</p>
                        <div class="d-flex justify-content-between align-items-center mt-1">
                            <small class="text-muted">${uri}</small>
                            <span class="badge bg-secondary">${publisher}</span>
                        </div>
                    </a>
                `;
            });
            html += '</div>';
            resultsDiv.innerHTML = html;
        })
        .catch(error => {
            console.error('Error searching I14Y datasets:', error);
            resultsDiv.innerHTML = `<p class="text-danger">Error: ${error.message}</p>`;
        });
}

function selectI14YDatasetResult(index) {
    const result = lastI14YDatasetSearchResults[index];
    if (!result) return;
    
    // Get the currently selected node
    const selectedNodeIds = Array.from(selectedNodes);
    if (selectedNodeIds.length !== 1) {
        alert('Please select exactly one dataset node to link');
        return;
    }
    
    // Make sure we're getting just the node ID string, not the full node object
    let nodeId = selectedNodeIds[0];
    console.log('Raw selected node ID for dataset linking:', nodeId, typeof nodeId);
    
    // Extract ID if it's an object with an id property
    if (typeof nodeId === 'object' && nodeId !== null && 'id' in nodeId) {
        nodeId = nodeId.id;
    }
    
    console.log('Processed node ID for dataset linking:', nodeId, typeof nodeId);
    
    // Extract or construct URI
    const uri = result.uri || 
               result.id && `https://www.i14y.admin.ch/de/catalog/datasets/${result.id}/description` || 
               '#';
               
    // Prepare title for display
    let title = 'Unnamed Dataset';
    if (typeof result.title === 'object') {
        title = result.title.en || result.title.de || result.title.fr || 
                result.title.it || Object.values(result.title)[0] || title;
    } else if (typeof result.title === 'string') {
        title = result.title;
    } else if (result.identifiers && result.identifiers.length > 0) {
        title = result.identifiers[0].notation;
    } else if (result.identifier) {
        title = result.identifier;
    }
    
    // Prepare description for display
    let description = '';
    if (typeof result.description === 'object') {
        description = result.description.en || result.description.de || 
                     result.description.fr || result.description.it || 
                     Object.values(result.description)[0] || '';
    } else if (typeof result.description === 'string') {
        description = result.description;
    }
    
    // Extract publisher information
    let publisher = 'Unknown publisher';
    
    // Try all possible publisher properties and formats
    if (result.publisherName) {
        // Direct publisherName property (often found in I14Y API)
        if (typeof result.publisherName === 'object') {
            publisher = result.publisherName.en || result.publisherName.de || 
                       result.publisherName.fr || result.publisherName.it ||
                       Object.values(result.publisherName)[0] || publisher;
        } else if (typeof result.publisherName === 'string') {
            publisher = result.publisherName;
        }
    } else if (result.publisher) {
        // Structured publisher object
        if (typeof result.publisher === 'object') {
            if (result.publisher.name) {
                // Publisher with name property
                if (typeof result.publisher.name === 'object') {
                    publisher = result.publisher.name.en || result.publisher.name.de || 
                               result.publisher.name.fr || result.publisher.name.it ||
                               Object.values(result.publisher.name)[0] || publisher;
                } else if (typeof result.publisher.name === 'string') {
                    publisher = result.publisher.name;
                }
            } else if (result.publisher.title) {
                // Publisher with title property
                if (typeof result.publisher.title === 'object') {
                    publisher = result.publisher.title.en || result.publisher.title.de || 
                               result.publisher.title.fr || result.publisher.title.it ||
                               Object.values(result.publisher.title)[0] || publisher;
                } else if (typeof result.publisher.title === 'string') {
                    publisher = result.publisher.title;
                }
            } else {
                // Try to extract from top level publisher object
                const publisherValue = Object.values(result.publisher).find(v => 
                    typeof v === 'string' || 
                    (typeof v === 'object' && (v.de || v.en || v.fr || v.it))
                );
                
                if (publisherValue) {
                    if (typeof publisherValue === 'object') {
                        publisher = publisherValue.de || publisherValue.en || 
                                   publisherValue.fr || publisherValue.it ||
                                   Object.values(publisherValue)[0] || publisher;
                    } else {
                        publisher = publisherValue;
                    }
                }
            }
        } else if (typeof result.publisher === 'string') {
            publisher = result.publisher;
        }
    } else if (result.creator) {
        // Fallback to creator if publisher is not available
        if (typeof result.creator === 'object' && result.creator.name) {
            if (typeof result.creator.name === 'object') {
                publisher = result.creator.name.en || result.creator.name.de || 
                           result.creator.name.fr || result.creator.name.it ||
                           Object.values(result.creator.name)[0] || publisher;
            } else if (typeof result.creator.name === 'string') {
                publisher = result.creator.name;
            }
        } else if (typeof result.creator === 'string') {
            publisher = result.creator;
        }
    }
    
    // Prepare sanitized dataset data with string values
    const sanitizedDataset = {
        id: result.id,
        uri: uri,
        title: title,
        description: description,
        type: result.type || 'Dataset',
        publisher: publisher
    };
    
    // Send the link request to the server
    console.log('Sending node ID for dataset linking:', nodeId, typeof nodeId);
    
    fetch('/api/i14y/dataset/link', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            dataset_id: nodeId,
            dataset_data: sanitizedDataset
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide the modal
            bootstrap.Modal.getInstance(document.getElementById('i14yDatasetSearchModal')).hide();
            
            // Reload the graph
            loadGraphWithD3();
            
            // Show success message
            const status = document.getElementById('selection-status');
            if (status) {
                status.style.display = 'block';
                status.innerHTML = '<small><strong>Success:</strong> Dataset linked to I14Y dataset.</small>';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
        } else {
            alert('Error linking to I14Y dataset: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error linking to I14Y dataset: ' + error.message);
        console.error('Error linking to I14Y dataset:', error);
    });
}

// Alias for backwards compatibility with existing HTML
window.showLinkDataElementToConceptModal = showLinkToI14YModal;
window.showI14YDatasetSearchModal = showI14YDatasetSearchModal;
window.searchI14YDatasets = searchI14YDatasets;
window.selectI14YDatasetResult = selectI14YDatasetResult;

// Update Data Element Info function
function updateDataElementInfo() {
    if (!selectedNodeId) {
        alert('No data element selected');
        return;
    }

    // Collect form data
    const localName = document.getElementById('edit-data-element-local-name').value.trim();
    const descriptionDe = document.getElementById('edit-data-element-description-de').value.trim();
    const descriptionFr = document.getElementById('edit-data-element-description-fr').value.trim();
    const descriptionIt = document.getElementById('edit-data-element-description-it').value.trim();
    const descriptionEn = document.getElementById('edit-data-element-description-en').value.trim();

    if (!localName) {
        alert('Local name is required');
        return;
    }

    // Prepare multilingual description object
    const description = {};
    if (descriptionDe) description.de = descriptionDe;
    if (descriptionFr) description.fr = descriptionFr;
    if (descriptionIt) description.it = descriptionIt;
    if (descriptionEn) description.en = descriptionEn;

    // Prepare update data
    const updateData = {
        local_name: localName,
        description: description
    };

    // Send update request
    fetch(`/api/nodes/${selectedNodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData)
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
            
            // Reload the graph to reflect changes
            loadGraphWithD3();
            
            // Reload node details to show updated information
            loadNodeDetails(selectedNodeId);
        } else {
            alert('Error updating data element: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error updating data element: ' + error.message);
        console.error('Error updating data element:', error);
    });
}

// Export the function to global scope
window.updateDataElementInfo = updateDataElementInfo;
