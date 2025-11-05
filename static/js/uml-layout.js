// UML Layout implementation using JointJS
// This file provides UML-style visualization for the SHACL editor

// Initialize JointJS graph and paper
let graph, paper;

// Map to keep track of JointJS elements corresponding to our data model
const elementMap = new Map();

// Initialize UML visualization
function initializeUmlVisualization(containerId) {
    // Create the JointJS graph
    graph = new joint.dia.Graph();

    // Create the paper (view) for the graph
    paper = new joint.dia.Paper({
        el: document.getElementById(containerId),
        model: graph,
        width: '100%',
        height: 600,
        gridSize: 10,
        drawGrid: true,
        background: {
            color: 'rgba(0, 0, 0, 0.05)'
        },
        interactive: {
            vertexAdd: false,
            vertexRemove: false,
            arrowheadMove: false
        }
    });

    // Set up event listeners
    paper.on('cell:pointerdown', function(cellView, evt, x, y) {
        if (connectionMode) {
            // If we're in connection mode
            const clickedElement = cellView.model;
            if (clickedElement.isElement()) {  // Only handle element nodes, not links
                const originalId = clickedElement.get('originalId');
                
                if (!connectionSource) {
                    // First node selection - set as source
                    connectionSource = originalId;
                    console.log('Connection source selected:', originalId);
                } else if (connectionSource !== originalId) {
                    // Second node selection - create connection
                    console.log('Creating connection from', connectionSource, 'to', originalId);
                    
                    // Call API to create connection
                    fetch('/api/edges', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            from: connectionSource,
                            to: originalId
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Exit connection mode
                            connectionMode = false;
                            connectionSource = null;
                            document.getElementById('connection-status').style.display = 'none';
                            
                            // Reload graph
                            loadGraphWithUmlLayout();
                        } else {
                            alert('Failed to create connection: ' + (data.error || 'Unknown error'));
                        }
                    });
                }
            }
        } else {
            // Normal selection mode - just select the element
            selectElement(cellView.model.id);
        }
    });

    paper.on('blank:pointerdown', function(evt, x, y) {
        clearSelection();
    });

    // Enable element dragging but maintain parent-child relationship
    paper.on('element:pointerup', function(elementView, evt, x, y) {
        const element = elementView.model;
        // Apply layout to maintain proper positioning
        arrangeUmlLayout();
    });

    console.log('UML visualization initialized with JointJS');
}

// Load graph data from API and render with UML layout
function loadGraphWithUmlLayout() {
    fetch('/api/graph')
        .then(response => response.json())
        .then(data => {
            // Clear the existing graph
            graph.clear();
            elementMap.clear();

            // First process all nodes
            if (data.nodes && Array.isArray(data.nodes)) {
                processNodes(data.nodes);
            }

            // Then process all edges
            if (data.edges && Array.isArray(data.edges)) {
                processEdges(data.edges);
            }

            // Apply UML layout
            arrangeUmlLayout();
        })
        .catch(error => {
            console.error('Error loading graph:', error);
        });
}

// Process and create JointJS elements for nodes
function processNodes(nodes) {
    // Group nodes by type
    const datasetNodes = nodes.filter(node => node.type === 'dataset');
    const classNodes = nodes.filter(node => node.type === 'class');
    const dataElementNodes = nodes.filter(node => node.type === 'data_element');
    const conceptNodes = nodes.filter(node => node.type === 'concept');

    // Process datasets first (top level)
    datasetNodes.forEach((node, index) => {
        createUmlElement(node, 'dataset', index * 300, 50);
    });

    // Process classes (middle level)
    classNodes.forEach((node, index) => {
        createUmlElement(node, 'class', index * 300, 200);
    });

    // Process data elements (bottom level)
    dataElementNodes.forEach((node, index) => {
        createUmlElement(node, 'data_element', index * 150, 350);
    });

    // Process concepts
    conceptNodes.forEach((node, index) => {
        createUmlElement(node, 'concept', index * 150, 350);
    });
}

// Create a UML-style element in JointJS
function createUmlElement(node, type, x, y) {
    let element;
    
    // Get appropriate color for this node type
    const colors = getColorsForNodeType(type);
    
    switch (type) {
        case 'dataset':
            element = new joint.shapes.uml.Class({
                position: { x, y },
                size: { width: 200, height: 60 },
                name: node.title || node.label,
                attributes: [],
                methods: [],
                attrs: {
                    '.uml-class-name-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 2
                    },
                    '.uml-class-attrs-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 2
                    },
                    '.uml-class-methods-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 2
                    },
                    '.uml-class-name-text': {
                        'font-weight': 'bold',
                        'font-size': 14
                    }
                }
            });
            break;
            
        case 'class':
            element = new joint.shapes.uml.Class({
                position: { x, y },
                size: { width: 180, height: 60 },
                name: node.title || node.label,
                attributes: [],
                methods: [],
                attrs: {
                    '.uml-class-name-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 2
                    },
                    '.uml-class-attrs-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 2
                    },
                    '.uml-class-methods-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 2
                    },
                    '.uml-class-name-text': {
                        'font-weight': 'bold',
                        'font-size': 12
                    }
                }
            });
            break;
            
        case 'data_element':
        case 'concept':
            // For data elements and concepts, create a simpler UML attribute box
            element = new joint.shapes.uml.Class({
                position: { x, y },
                size: { width: 160, height: 40 },
                name: node.title || node.label,
                attributes: [],
                methods: [],
                attrs: {
                    '.uml-class-name-rect': {
                        fill: colors.background,
                        stroke: colors.border,
                        'stroke-width': 1
                    },
                    '.uml-class-attrs-rect, .uml-class-methods-rect': {
                        display: 'none'
                    },
                    '.uml-class-name-text': {
                        'font-size': 11,
                        'text-anchor': 'middle'
                    }
                }
            });
            break;
    }
    
    // Store the node type for our custom behavior
    element.set('type', type);
    element.set('originalId', node.id);
    
    // Add to graph
    graph.addCell(element);
    
    // Store in our map for later reference
    elementMap.set(node.id, element);
    
    return element;
}

// Process and create JointJS links for edges
function processEdges(edges) {
    edges.forEach(edge => {
        const sourceElement = elementMap.get(edge.from);
        const targetElement = elementMap.get(edge.to);
        
        if (sourceElement && targetElement) {
            // Create a UML association link
            const link = new joint.shapes.uml.Association({
                source: { id: sourceElement.id },
                target: { id: targetElement.id },
                attrs: {
                    '.marker-target': {
                        d: 'M 10 0 L 0 5 L 10 10 z',
                        fill: '#4b4a67',
                        stroke: '#4b4a67'
                    },
                    '.connection': {
                        stroke: '#4b4a67',
                        'stroke-width': 1
                    }
                },
                labels: [
                    {
                        position: 0.5,
                        attrs: {
                            text: {
                                text: edge.cardinality || '',
                                'font-size': 10,
                                'font-family': 'sans-serif'
                            },
                            rect: {
                                fill: 'white'
                            }
                        }
                    }
                ]
            });
            
            // Store the original edge ID
            link.set('originalId', edge.id);
            
            // Add to graph
            graph.addCell(link);
        }
    });
}

// Apply UML-style layout to the graph
function arrangeUmlLayout() {
    console.log('Applying UML layout...');

    // Group elements by type
    const datasets = [];
    const classes = [];
    const dataElements = {};
    
    // Collect elements by type
    graph.getElements().forEach(element => {
        const type = element.get('type');
        if (type === 'dataset') {
            datasets.push(element);
        } else if (type === 'class') {
            classes.push(element);
        } else if (type === 'data_element') {
            const originalId = element.get('originalId');
            dataElements[originalId] = element;
        }
    });
    
    // Find parent-child relationships
    const childrenMap = {};
    graph.getLinks().forEach(link => {
        const sourceId = link.get('source').id;
        const targetId = link.get('target').id;
        
        const sourceElement = graph.getCell(sourceId);
        const targetElement = graph.getCell(targetId);
        
        if (sourceElement && targetElement) {
            const sourceType = sourceElement.get('type');
            const targetType = targetElement.get('type');
            
            // If source is a class/dataset and target is a data element
            if ((sourceType === 'class' || sourceType === 'dataset') && 
                targetType === 'data_element') {
                
                // Create an entry in the children map if it doesn't exist
                if (!childrenMap[sourceId]) {
                    childrenMap[sourceId] = [];
                }
                
                // Add the target element to the children of the source
                childrenMap[sourceId].push(targetElement);
            }
        }
    });
    
    // Layout calculation
    const horizontalSpacing = 350;
    const verticalSpacing = 150;
    
    // Position datasets at the top
    datasets.forEach((dataset, index) => {
        dataset.position(index * horizontalSpacing, 50);
    });
    
    // Position classes below datasets
    classes.forEach((cls, index) => {
        cls.position(index * horizontalSpacing, 250);
    });
    
    // Position data elements below their parents
    Object.keys(childrenMap).forEach(parentId => {
        const parent = graph.getCell(parentId);
        const children = childrenMap[parentId];
        
        if (parent && children && children.length > 0) {
            // Position each child in a column below the parent
            const parentPos = parent.position();
            children.forEach((child, index) => {
                const yPos = parentPos.y + verticalSpacing + (index * 60);
                child.position(parentPos.x, yPos);
            });
        }
    });
    
    console.log('UML layout applied');
}

// Get colors for different node types
function getColorsForNodeType(type) {
    switch (type) {
        case 'dataset':
            return {
                background: '#ffffcc',
                border: '#ffcc00'
            };
        case 'class':
            return {
                background: '#e6f3ff',
                border: '#4d94ff'
            };
        case 'data_element':
            return {
                background: '#f0f0f0',
                border: '#a0a0a0'
            };
        case 'concept':
            return {
                background: '#e6ffe6',
                border: '#66cc66'
            };
        default:
            return {
                background: '#ffffff',
                border: '#000000'
            };
    }
}

// Select an element (node or edge) by ID
function selectElement(elementId) {
    const element = graph.getCell(elementId);
    
    if (element) {
        // Highlight the selected element
        if (element.isLink()) {
            // It's a link/edge
            element.attr({
                '.connection': {
                    'stroke-width': 3,
                    stroke: '#ff0000'
                }
            });
            
            // Get the original edge ID and trigger selection in the main app
            const originalId = element.get('originalId');
            if (originalId) {
                // Call the main app's edge selection function
                window.selectEdge(originalId);
            }
        } else {
            // It's a node
            element.attr({
                '.uml-class-name-rect': {
                    stroke: '#ff0000',
                    'stroke-width': 3
                }
            });
            
            // Get the original node ID and trigger selection in the main app
            const originalId = element.get('originalId');
            if (originalId) {
                // Call the main app's node selection function
                window.selectNode(originalId);
            }
        }
    }
}

// Clear selection highlighting
function clearSelection() {
    graph.getCells().forEach(cell => {
        if (cell.isLink()) {
            // Reset link styling
            cell.attr({
                '.connection': {
                    'stroke-width': 1,
                    stroke: '#4b4a67'
                }
            });
        } else {
            // Reset node styling
            const type = cell.get('type');
            const colors = getColorsForNodeType(type);
            
            cell.attr({
                '.uml-class-name-rect': {
                    stroke: colors.border,
                    'stroke-width': type === 'dataset' || type === 'class' ? 2 : 1
                }
            });
        }
    });
    
    // Call the main app's clear selection function
    window.clearNodeSelection();
}

// Export functions for use in the main app
window.initializeUmlVisualization = initializeUmlVisualization;
window.loadGraphWithUmlLayout = loadGraphWithUmlLayout;
window.arrangeUmlLayout = arrangeUmlLayout;
