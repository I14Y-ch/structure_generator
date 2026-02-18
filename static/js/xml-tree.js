// Tree Visualization for SHACL Creator
// Hierarchical tree layout similar to XML editors

let xmlTreeSvg;
let xmlTreeG;
let xmlTreeRoot;
let xmlTreeLayout;
let xmlTreeConnectionMode = false;
let xmlTreePendingConnection = null;

// Initialize XML tree visualization
function initializeXmlTreeVisualization(containerId) {
    console.log('Initializing XML tree visualization in container:', containerId);
    
    const container = document.getElementById(containerId);
    if (!container) {
        console.error('Container not found:', containerId);
        return;
    }
    
    // Clear any existing content
    container.innerHTML = '';
    
    // Get container dimensions
    const containerRect = container.getBoundingClientRect();
    const width = containerRect.width || 800;
    const height = containerRect.height || 600;
    
    // Create SVG
    xmlTreeSvg = d3.select('#' + containerId)
        .append('svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .style('background', '#ffffff');
    
    // Create main group with zoom support
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            xmlTreeG.attr('transform', event.transform);
        });
    
    xmlTreeSvg.call(zoom);
    
    xmlTreeG = xmlTreeSvg.append('g')
        .attr('transform', 'translate(40, 20)');
    
    // Create tree layout
    xmlTreeLayout = d3.tree()
        .size([height - 40, width - 200])
        .separation((a, b) => {
            return a.parent == b.parent ? 1 : 1.2;
        });
    
    console.log('XML tree visualization initialized');
}

// Convert flat graph data to hierarchical tree structure
function convertToTreeData(graphData) {
    const nodes = graphData.nodes || [];
    const edges = graphData.edges || [];
    
    console.log('Converting to tree - Total nodes:', nodes.length, 'Total edges:', edges.length);
    console.log('Edges:', edges);
    
    // Find root nodes (nodes with no incoming edges)
    const hasIncomingEdge = new Set();
    edges.forEach(edge => {
        hasIncomingEdge.add(edge.to);
    });
    
    // Get nodes with no incoming edges
    let rootNodes = nodes.filter(node => !hasIncomingEdge.has(node.id));
    
    console.log('Root nodes found:', rootNodes.length, rootNodes.map(n => ({id: n.id, type: n.type, label: n.label})));
    
    // If we have multiple root nodes, prioritize dataset
    if (rootNodes.length > 1) {
        const datasetNode = rootNodes.find(node => node.type === 'dataset');
        if (datasetNode) {
            rootNodes = [datasetNode];
        }
    }
    
    // If no root found, pick the first dataset or the first node
    if (rootNodes.length === 0 && nodes.length > 0) {
        const datasetNode = nodes.find(node => node.type === 'dataset');
        rootNodes.push(datasetNode || nodes[0]);
    }
    
    // Build tree structure
    const nodeMap = new Map();
    nodes.forEach(node => {
        nodeMap.set(node.id, {
            ...node,
            children: []
        });
    });
    
    console.log('Created nodeMap with', nodeMap.size, 'nodes');
    
    // Add children based on edges (using 'from' and 'to' properties from API)
    edges.forEach(edge => {
        const parent = nodeMap.get(edge.from);
        const child = nodeMap.get(edge.to);
        console.log('Processing edge from', edge.from, 'to', edge.to, 'parent:', !!parent, 'child:', !!child);
        if (parent && child) {
            // Add edge metadata to the child
            child.edgeLabel = edge.label || 'sh:property';
            child.edgeId = edge.id;
            child.cardinality = edge.cardinality;
            parent.children.push(child);
        }
    });

    const resolveLabel = node => {
        if (node && typeof node.title === 'object') {
            return node.title.de || node.title.en || node.title.fr || node.title.it || Object.values(node.title)[0] || '';
        }
        return (node && (node.title || node.label || node.id)) || '';
    };

    const compareNodes = (a, b) => {
        const orderA = Number.isFinite(a.order) ? a.order : Number.POSITIVE_INFINITY;
        const orderB = Number.isFinite(b.order) ? b.order : Number.POSITIVE_INFINITY;
        if (orderA !== orderB) {
            return orderA - orderB;
        }
        return resolveLabel(a).localeCompare(resolveLabel(b), 'de', { sensitivity: 'base' });
    };

    nodeMap.forEach(node => {
        if (node.children && node.children.length > 1) {
            node.children.sort(compareNodes);
        }
    });
    
    console.log('Tree data - rootNodes:', rootNodes.length);
    if (rootNodes.length > 0) {
        const root = nodeMap.get(rootNodes[0].id);
        console.log('Root node:', root.label || root.id, 'with', root.children.length, 'children');
        console.log('Root children:', root.children.map(c => ({id: c.id, label: c.label, type: c.type, childCount: c.children.length})));
        
        // Log second level children (e.g., classes with their data elements)
        root.children.forEach(child => {
            if (child.children && child.children.length > 0) {
                console.log(`  - ${child.label || child.id} (${child.type}) has ${child.children.length} children:`, 
                    child.children.map(gc => ({label: gc.label, type: gc.type})));
            }
        });
    }
    
    // Create root structure
    if (rootNodes.length === 1) {
        return nodeMap.get(rootNodes[0].id);
    } else if (rootNodes.length > 1) {
        // Multiple roots - create virtual root
        return {
            id: 'virtual-root',
            label: 'SHACL Structure',
            type: 'virtual',
            children: rootNodes.map(n => nodeMap.get(n.id))
        };
    }
    
    return null;
}

// Load and render XML tree
function loadXmlTree() {
    fetch('/api/graph')
        .then(response => response.json())
        .then(data => {
            renderXmlTree(data);
        })
        .catch(error => {
            console.error('Error loading graph data:', error);
        });
}

// Render the XML tree
function renderXmlTree(graphData) {
    if (!xmlTreeG) {
        console.error('XML tree not initialized');
        return;
    }
    
    // Clear existing content
    xmlTreeG.selectAll('*').remove();
    
    // Convert to tree structure
    const treeData = convertToTreeData(graphData);
    
    if (!treeData) {
        xmlTreeG.append('text')
            .attr('x', 20)
            .attr('y', 20)
            .text('No data to display')
            .style('font-size', '14px')
            .style('fill', '#666');
        return;
    }
    
    // Create hierarchy
    const root = d3.hierarchy(treeData, d => d.children);
    
    // Apply layout
    xmlTreeLayout(root);
    
    // Create links (connections)
    const links = xmlTreeG.selectAll('.xml-link')
        .data(root.links())
        .enter()
        .append('g')
        .attr('class', 'xml-link')
        .style('cursor', 'pointer')
        .on('click', (event, d) => handleTreeEdgeClick(event, d));
    
    // Draw connection lines
    links.append('path')
        .attr('d', d => {
            const sourceX = d.source.y;
            const sourceY = d.source.x;
            const targetX = d.target.y;
            const targetY = d.target.x;
            
            return `M ${sourceX + 150} ${sourceY} 
                    L ${sourceX + 170} ${sourceY}
                    L ${sourceX + 170} ${targetY}
                    L ${targetX} ${targetY}`;
        })
        .style('fill', 'none')
        .style('stroke', '#999')
        .style('stroke-width', '1px')
        .attr('class', 'tree-edge-path');
    
    // Add invisible wider hitbox for easier clicking
    links.append('path')
        .attr('d', d => {
            const sourceX = d.source.y;
            const sourceY = d.source.x;
            const targetX = d.target.y;
            const targetY = d.target.x;
            
            return `M ${sourceX + 150} ${sourceY} 
                    L ${sourceX + 170} ${sourceY}
                    L ${sourceX + 170} ${targetY}
                    L ${targetX} ${targetY}`;
        })
        .style('fill', 'none')
        .style('stroke', 'transparent')
        .style('stroke-width', '10px')
        .attr('class', 'tree-edge-hitbox');
    
    // Add edge labels
    links.append('text')
        .attr('x', d => d.target.y - 10)
        .attr('y', d => d.target.x - 5)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'middle')
        .style('font-size', '10px')
        .style('fill', '#666')
        .style('font-style', 'italic')
        .style('pointer-events', 'none')
        .text(d => {
            const edgeLabel = d.target.data.edgeLabel || '';
            const cardinality = d.target.data.cardinality || '';
            return cardinality ? `${edgeLabel} [${cardinality}]` : edgeLabel;
        });
    
    // Highlight selected edge if any
    if (selectedEdgeId) {
        links.each(function(d) {
            if (d.target.data.edgeId === selectedEdgeId) {
                d3.select(this).select('.tree-edge-path')
                    .style('stroke', '#ff0000')
                    .style('stroke-width', '3px')
                    .style('stroke-dasharray', '5,5');
            }
        });
    }
    
    // Create nodes
    const nodeGroups = xmlTreeG.selectAll('.xml-node')
        .data(root.descendants())
        .enter()
        .append('g')
        .attr('class', 'xml-node')
        .attr('transform', d => `translate(${d.y}, ${d.x})`)
        .style('cursor', 'pointer')
        .on('click', (event, d) => {
            handleXmlNodeClick(event, d);
        });
    
    // Draw node boxes with XML-style appearance
    nodeGroups.each(function(d) {
        const group = d3.select(this);
        const nodeData = d.data;
        
        // Skip virtual root
        if (nodeData.type === 'virtual') {
            group.append('text')
                .attr('x', 0)
                .attr('y', 0)
                .attr('text-anchor', 'start')
                .style('font-size', '14px')
                .style('font-weight', 'bold')
                .style('fill', '#333')
                .text(nodeData.label || 'Root');
            return;
        }
        
        // Calculate box size based on content
        // Get title - handle multilingual titles
        let label = nodeData.title;
        if (typeof label === 'object') {
            label = label.de || label.en || label.fr || label.it || Object.values(label)[0] || '';
        }
        if (!label) {
            label = nodeData.label || nodeData.id || 'unnamed';
        }
        const labelWidth = Math.max(150, label.length * 7 + 20);
        
        // Different styles for different node types - matching network view colors
        let bgColor, borderColor, textColor;
        
        switch (nodeData.type) {
            case 'dataset':
                // Blue for datasets
                bgColor = '#87CEFA';
                borderColor = '#4682B4';
                textColor = '#1e3a5f';
                break;
            case 'class':
                // Green for classes
                bgColor = '#99ff99';
                borderColor = '#4CAF50';
                textColor = '#2e7d32';
                break;
            case 'data_element':
                // Check if linked to I14Y concept
                if (nodeData.is_linked_to_concept === true) {
                    // Purple/pink for I14Y-linked data elements
                    bgColor = '#f9cee7';
                    borderColor = '#d81b60';
                    textColor = '#880e4f';
                } else {
                    // Orange for regular data elements
                    bgColor = '#ffcc99';
                    borderColor = '#ff9800';
                    textColor = '#e65100';
                }
                break;
            case 'NodeShape':
                // Blue for SHACL NodeShapes (datasets)
                bgColor = '#87CEFA';
                borderColor = '#4682B4';
                textColor = '#1e3a5f';
                break;
            case 'PropertyShape':
                // Orange for SHACL PropertyShapes (data elements)
                bgColor = '#ffcc99';
                borderColor = '#ff9800';
                textColor = '#e65100';
                break;
            default:
                bgColor = '#f5f5f5';
                borderColor = '#999';
                textColor = '#666';
        }
        
        // Main box
        group.append('rect')
            .attr('x', 0)
            .attr('y', -12)
            .attr('width', labelWidth)
            .attr('height', 24)
            .attr('rx', 2)
            .style('fill', bgColor)
            .style('stroke', borderColor)
            .style('stroke-width', '1.5px');
        
        // Expand/collapse indicator for nodes with children
        if (nodeData.children && nodeData.children.length > 0) {
            group.append('text')
                .attr('x', 5)
                .attr('y', 0)
                .attr('text-anchor', 'start')
                .attr('dominant-baseline', 'middle')
                .style('font-size', '12px')
                .style('font-weight', 'bold')
                .style('fill', borderColor)
                .style('user-select', 'none')
                .text('▼');
        }
        
        // Node label
        group.append('text')
            .attr('x', nodeData.children && nodeData.children.length > 0 ? 18 : 8)
            .attr('y', 0)
            .attr('text-anchor', 'start')
            .attr('dominant-baseline', 'middle')
            .style('font-size', '11px')
            .style('fill', textColor)
            .style('font-family', 'monospace')
            .style('user-select', 'none')
            .text(label);
        
        // Add constraint indicators
        if (nodeData.constraints) {
            const constraints = [];
            if (nodeData.constraints.datatype) {
                constraints.push(`type: ${nodeData.constraints.datatype.split(':')[1] || nodeData.constraints.datatype}`);
            }
            if (nodeData.constraints.minLength || nodeData.constraints.maxLength) {
                const min = nodeData.constraints.minLength || '';
                const max = nodeData.constraints.maxLength || '';
                constraints.push(`length: ${min}..${max}`);
            }
            if (nodeData.constraints.pattern) {
                constraints.push('pattern');
            }
            
            if (constraints.length > 0) {
                group.append('text')
                    .attr('x', labelWidth - 5)
                    .attr('y', 0)
                    .attr('text-anchor', 'end')
                    .attr('dominant-baseline', 'middle')
                    .style('font-size', '9px')
                    .style('fill', '#666')
                    .style('font-style', 'italic')
                    .text(`{${constraints.join(', ')}}`);
            }
        }
        
        // Highlight selected node
        if (selectedNodeId === nodeData.id) {
            group.select('rect')
                .style('stroke-width', '3px')
                .style('filter', 'drop-shadow(0 0 5px rgba(0,0,0,0.3))');
        }
        
        // Highlight source node in connection mode
        if (xmlTreePendingConnection === nodeData.id) {
            group.select('rect')
                .style('stroke', '#ff6600')
                .style('stroke-width', '3px')
                .style('filter', 'drop-shadow(0 0 8px rgba(255, 102, 0, 0.6))');
        }
    });
}

// Handle edge click in XML tree
function handleTreeEdgeClick(event, d) {
    event.stopPropagation();
    
    // Don't handle edge clicks in connection mode
    if (xmlTreeConnectionMode) {
        return;
    }
    
    const edgeId = d.target.data.edgeId;
    
    if (!edgeId) {
        console.warn('No edge ID found for clicked connection');
        return;
    }
    
    console.log('Tree edge clicked:', edgeId);
    
    // Call the global selectEdge function
    if (window.selectEdge) {
        window.selectEdge(edgeId);
    }
    
    // Reload tree to show edge selection highlight
    loadXmlTree();
}

// Handle node click in XML tree
function handleXmlNodeClick(event, d) {
    event.stopPropagation();
    
    const nodeData = d.data;
    
    // Skip virtual root
    if (nodeData.type === 'virtual') {
        return;
    }
    
    // If in connection mode, handle connection logic
    if (xmlTreeConnectionMode) {
        if (!xmlTreePendingConnection) {
            // First click - set source
            xmlTreePendingConnection = nodeData.id;
            console.log('XML Tree: Connection source selected:', nodeData.id);
            
            // Update UI
            const connectionStatus = document.getElementById('connection-status');
            if (connectionStatus) {
                connectionStatus.innerHTML = '<small><strong>Connection Mode:</strong> Select target node to complete connection</small>';
            }
            
            // Reload to show source highlight
            loadXmlTree();
        } else if (xmlTreePendingConnection !== nodeData.id) {
            // Second click - create connection
            console.log('XML Tree: Creating connection from', xmlTreePendingConnection, 'to', nodeData.id);
            
            fetch('/api/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source: xmlTreePendingConnection,
                    target: nodeData.id
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('XML Tree: Connection created successfully');
                    // Reset connection mode
                    xmlTreeConnectionMode = false;
                    xmlTreePendingConnection = null;
                    
                    // Update UI
                    const connectionStatus = document.getElementById('connection-status');
                    const connectBtn = document.getElementById('connect-btn');
                    if (connectionStatus) {
                        connectionStatus.classList.remove('active');
                        connectionStatus.style.display = 'none';
                    }
                    if (connectBtn) {
                        connectBtn.classList.remove('btn-warning');
                        connectBtn.classList.add('btn-outline-dark');
                    }
                    
                    // Reload graph
                    loadXmlTree();
                } else {
                    alert('Error creating connection: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error creating connection:', error);
                alert('Error creating connection');
            });
        } else {
            // Clicked same node - cancel
            xmlTreePendingConnection = null;
            const connectionStatus = document.getElementById('connection-status');
            if (connectionStatus) {
                connectionStatus.innerHTML = '<small><strong>Connection Mode:</strong> Select source node to start connection</small>';
            }
            loadXmlTree();
        }
        return;
    }
    
    // Normal mode - select the node
    selectNode(nodeData.id);
    
    // Reload tree to show selection
    fetch('/api/graph')
        .then(response => response.json())
        .then(data => {
            renderXmlTree(data);
        });
}

// Toggle connection mode for XML tree
function toggleXmlTreeConnectionMode() {
    xmlTreeConnectionMode = !xmlTreeConnectionMode;
    xmlTreePendingConnection = null;
    
    console.log('XML Tree connection mode:', xmlTreeConnectionMode ? 'ENABLED' : 'DISABLED');
    
    // Update UI
    const connectionStatus = document.getElementById('connection-status');
    const connectBtn = document.getElementById('connect-btn');
    
    if (xmlTreeConnectionMode) {
        if (connectionStatus) {
            connectionStatus.classList.add('active');
            connectionStatus.style.display = 'block';
            connectionStatus.innerHTML = '<small><strong>Connection Mode:</strong> Click on source node to start connection</small>';
        }
        if (connectBtn) {
            connectBtn.classList.add('btn-warning');
            connectBtn.classList.remove('btn-outline-dark');
        }
    } else {
        if (connectionStatus) {
            connectionStatus.classList.remove('active');
            connectionStatus.style.display = 'none';
        }
        if (connectBtn) {
            connectBtn.classList.remove('btn-warning');
            connectBtn.classList.add('btn-outline-dark');
        }
        
        // Reload to remove highlights
        loadXmlTree();
    }
}

// Toggle connection mode for XML tree
function toggleXmlTreeConnectionMode() {
    xmlTreeConnectionMode = !xmlTreeConnectionMode;
    xmlTreePendingConnection = null;
    
    console.log('XML Tree connection mode:', xmlTreeConnectionMode ? 'ENABLED' : 'DISABLED');
    
    // Update UI
    const connectionStatus = document.getElementById('connection-status');
    const connectBtn = document.getElementById('connect-btn');
    
    if (xmlTreeConnectionMode) {
        if (connectionStatus) {
            connectionStatus.classList.add('active');
            connectionStatus.style.display = 'block';
            connectionStatus.innerHTML = '<small><strong>Connection Mode:</strong> Click on source node to start connection</small>';
        }
        if (connectBtn) {
            connectBtn.classList.add('btn-warning');
            connectBtn.classList.remove('btn-outline-dark');
        }
    } else {
        if (connectionStatus) {
            connectionStatus.classList.remove('active');
            connectionStatus.style.display = 'none';
        }
        if (connectBtn) {
            connectBtn.classList.remove('btn-warning');
            connectBtn.classList.add('btn-outline-dark');
        }
        
        // Reload to remove highlights
        loadXmlTree();
    }
}

// Export function to switch visualization
function switchToXmlTree() {
    if (typeof initializeXmlTreeVisualization === 'function') {
        initializeXmlTreeVisualization('graph-container');
        loadXmlTree();
    }
}

// Export function to refresh XML tree
function refreshXmlTree() {
    loadXmlTree();
}

// Make functions globally accessible
window.initializeXmlTreeVisualization = initializeXmlTreeVisualization;
window.loadXmlTree = loadXmlTree;
window.renderXmlTree = renderXmlTree;
window.switchToXmlTree = switchToXmlTree;
window.refreshXmlTree = refreshXmlTree;
window.toggleXmlTreeConnectionMode = toggleXmlTreeConnectionMode;
