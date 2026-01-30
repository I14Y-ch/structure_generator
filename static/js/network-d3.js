// D3.js Network Visualization for SHACL Creator

// Main visualization state
let simulation;
let svg;
let g;
let width, height;
let nodes = [];
let links = [];
let selectedNode = null;
let selectedLink = null;
let connectionMode = false;
let pendingConnection = null;
let zoom; // Zoom behavior

// Initialize the D3 visualization
function initializeD3Visualization(containerId) {
    console.log('Initializing D3 visualization in container:', containerId);
    
    const container = document.getElementById(containerId);
    if (!container) {
        console.error('Container not found:', containerId);
        return;
    }
    
    // Clear any existing content
    container.innerHTML = '';
    
    // Get container dimensions
    const containerRect = container.getBoundingClientRect();
    width = containerRect.width;
    height = containerRect.height;
    
    console.log('Container dimensions:', width, 'x', height);
    console.log('Container rect:', containerRect);
    console.log('Container style:', window.getComputedStyle(container));
    
    // If dimensions are 0, try to set them explicitly
    if (width === 0 || height === 0) {
        console.warn('Container has zero dimensions, setting explicitly');
        width = 800;
        height = 600;
        container.style.width = width + 'px';
        container.style.height = height + 'px';
    }
    // Define zoom behavior
    zoom = d3.zoom()
        .scaleExtent([0.1, 4])  // Allow zoom from 0.1x to 4x
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    
    // Create SVG element with zoom capability
    svg = d3.select('#' + containerId)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('style', 'border: 1px solid #ccc; background-color: #f9f9f9;')
        .call(zoom)
        .on('dblclick.zoom', null); // Disable zoom on double-click
    
    // Create a group for all elements that will be transformed by zoom
    g = svg.append('g');
    
    // Add a background rectangle for catching background clicks
    g.append('rect')
        .attr('width', width)
        .attr('height', height)
        .attr('fill', '#f9f9f9')
        .attr('fill-opacity', 0.01)
        .attr('stroke', '#ddd')
        .on('click', handleBackgroundClick);
    
    // Add zoom controls to the interface
    addZoomControls(containerId);
    
    console.log('D3 visualization initialized successfully with width:', width, 'height:', height);
    console.log('SVG element created:', svg);
    console.log('G element created:', g);
}

// Add zoom controls to the interface
function addZoomControls(containerId) {
    const container = document.getElementById(containerId);
    
    // Create a zoom controls div
    const zoomControls = document.createElement('div');
    zoomControls.className = 'zoom-controls';
    zoomControls.style.position = 'absolute';
    zoomControls.style.top = '10px';
    zoomControls.style.right = '10px';
    zoomControls.style.zIndex = '100';
    zoomControls.style.display = 'flex';
    zoomControls.style.flexDirection = 'column';
    zoomControls.style.gap = '5px';
    
    // Create zoom in button
    const zoomInBtn = document.createElement('button');
    zoomInBtn.innerHTML = '+';
    zoomInBtn.className = 'btn btn-sm btn-light';
    zoomInBtn.style.width = '30px';
    zoomInBtn.style.height = '30px';
    zoomInBtn.style.fontSize = '16px';
    zoomInBtn.style.padding = '0';
    zoomInBtn.style.textAlign = 'center';
    zoomInBtn.title = 'Zoom In';
    zoomInBtn.onclick = function() {
        zoom.scaleBy(svg.transition().duration(300), 1.3);
    };
    
    // Create zoom out button
    const zoomOutBtn = document.createElement('button');
    zoomOutBtn.innerHTML = '−'; // Using en dash
    zoomOutBtn.className = 'btn btn-sm btn-light';
    zoomOutBtn.style.width = '30px';
    zoomOutBtn.style.height = '30px';
    zoomOutBtn.style.fontSize = '16px';
    zoomOutBtn.style.padding = '0';
    zoomOutBtn.style.textAlign = 'center';
    zoomOutBtn.title = 'Zoom Out';
    zoomOutBtn.onclick = function() {
        zoom.scaleBy(svg.transition().duration(300), 0.7);
    };
    
    // Create reset zoom button
    const resetZoomBtn = document.createElement('button');
    resetZoomBtn.innerHTML = '⟲'; // Reset symbol
    resetZoomBtn.className = 'btn btn-sm btn-light';
    resetZoomBtn.style.width = '30px';
    resetZoomBtn.style.height = '30px';
    resetZoomBtn.style.fontSize = '16px';
    resetZoomBtn.style.padding = '0';
    resetZoomBtn.style.textAlign = 'center';
    resetZoomBtn.title = 'Reset View';
    resetZoomBtn.onclick = resetView;
    
    // Add buttons to controls
    zoomControls.appendChild(zoomInBtn);
    zoomControls.appendChild(zoomOutBtn);
    zoomControls.appendChild(resetZoomBtn);
    
    // Add controls to container
    container.style.position = 'relative';
    container.appendChild(zoomControls);
}

// Load the graph data from the backend
function loadGraphWithD3() {
    console.log('Loading graph data for D3 visualization');
    
    const debugEl = document.getElementById('debug-info');
    if (debugEl) {
        debugEl.innerHTML = '<div>Loading graph data...</div>';
    }
    
    fetch('/api/graph')
        .then(response => response.json())
        .then(data => {
            console.log('Received graph data:', data);
            
            if (debugEl) {
                debugEl.innerHTML = `<div>Received ${data.nodes.length} nodes and ${data.edges.length} edges</div>`;
            }
            
            if (!data.nodes || !Array.isArray(data.nodes)) {
                console.error('Invalid graph data format:', data);
                if (debugEl) {
                    debugEl.innerHTML += '<div style="color: red;">Invalid graph data format</div>';
                }
                return;
            }
            
            console.log(`Processing ${data.nodes.length} nodes and ${data.edges.length} edges`);
            
            // Check if D3 visualization is initialized
            if (!svg || !g) {
                console.error('D3 visualization not initialized! svg:', svg, 'g:', g);
                if (debugEl) {
                    debugEl.innerHTML += '<div style="color: red;">D3 visualization not initialized</div>';
                }
                return;
            }
            
            if (debugEl) {
                debugEl.innerHTML += '<div>D3 visualization initialized, rendering...</div>';
            }
            
            // Process the nodes
            nodes = data.nodes.map(node => {
                // Assign colors based on node type
                let color = '#aaaaaa'; // Default gray
                
                switch (node.type) {
                    case 'dataset':
                        color = '#ffcc00'; // Yellow
                        break;
                    case 'class':
                        color = '#4d94ff'; // Blue
                        break;
                    case 'data_element':
                        color = '#a0a0a0'; // Gray
                        break;
                    case 'concept':
                        color = '#66cc66'; // Green
                        break;
                }
                
                // Ensure nodes start within visible area
                const margin = 50;
                const x = margin + Math.random() * (width - 2 * margin);
                const y = margin + Math.random() * (height - 2 * margin);
                
                return {
                    ...node,
                    color: color,
                    radius: node.type === 'dataset' || node.type === 'class' ? 30 : 20,
                    x: x,
                    y: y
                };
            });
            
            // Process the links (edges)
            links = data.edges.map(edge => {
                return {
                    ...edge,
                    source: edge.from,
                    target: edge.to,
                    color: '#848484',
                    width: 1
                };
            });
            
            console.log('Processed nodes:', nodes);
            console.log('Processed links:', links);
            
            // Render the visualization
            renderVisualization();
            
            if (debugEl) {
                debugEl.innerHTML += '<div>Visualization rendered</div>';
                setTimeout(() => {
                    debugEl.innerHTML += `<div>Nodes in DOM: ${g.selectAll('.node').size()}</div>`;
                    debugEl.innerHTML += `<div>Links in DOM: ${g.selectAll('.link').size()}</div>`;
                }, 1000);
            }
        })
        .catch(error => {
            console.error('Error loading graph data:', error);
            if (debugEl) {
                debugEl.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
            }
        });
}

// Render the visualization
function renderVisualization() {
    console.log('Rendering visualization');
    console.log('Nodes to render:', nodes.length);
    console.log('Links to render:', links.length);
    
    // Clear the SVG
    g.selectAll('*').remove();
    
    // Create force simulation
    simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(250)) // Increased from 150 to 250
        .force('charge', d3.forceManyBody().strength(-800)) // Increased from -500 to -800
        .force('center', d3.forceCenter(width / 2, height / 2));
    
    // Create links
    const link = g.selectAll('.link')
        .data(links)
        .enter()
        .append('line')
        .attr('class', 'link')
        .attr('stroke', d => d.color)
        .attr('stroke-width', d => d.width || 1)
        .style('cursor', 'pointer')  // Add pointer cursor
        .on('click', handleLinkClick); // Add click handler for links
    
    // Add invisible wider lines for easier clicking
    g.selectAll('.link-hitbox')
        .data(links)
        .enter()
        .append('line')
        .attr('class', 'link-hitbox')
        .attr('stroke', 'transparent')
        .attr('stroke-width', 10)  // Much wider for easier clicking
        .style('cursor', 'pointer')
        .on('click', handleLinkClick);
    
    // Add cardinality labels to links
    const linkLabels = g.selectAll('.link-label')
        .data(links)
        .enter()
        .append('text')
        .attr('class', 'link-label')
        .attr('dy', -5)
        .attr('text-anchor', 'middle')
        .attr('fill', '#666')
        .attr('font-size', '10px')
        .text(d => d.cardinality || '1..1');
    
    // Create nodes
    const node = g.selectAll('.node')
        .data(nodes)
        .enter()
        .append('g')
        .attr('class', 'node')
        .on('click', handleNodeClick);
    
    // Add rectangles to nodes
    node.append('rect')
        .attr('x', d => -getNodeWidth(d) / 2)
        .attr('y', d => -getNodeHeight(d) / 2)
        .attr('width', d => getNodeWidth(d))
        .attr('height', d => getNodeHeight(d))
        .attr('rx', 10)
        .attr('ry', 10)
        .attr('fill', d => getNodeColor(d))
        .attr('stroke', '#222')
        .attr('stroke-width', 2);

    // Add text labels to nodes (centered)
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '-0.1em')
        .attr('fill', '#222')
        .attr('font-size', '14px')
        .attr('font-weight', 'bold')
        .each(function(d) {
            const textElement = d3.select(this);
            const lines = getWrappedTitle(d);
            lines.forEach((line, i) => {
                textElement.append('tspan')
                    .attr('x', 0)
                    .attr('dy', i === 0 ? 0 : '1.2em')
                    .text(line);
            });
        });

    // Add type labels below the node
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', d => {
            const lines = getWrappedTitle(d);
            return (lines.length - 1) * 1.2 + 1.2 + 'em'; // position below the last title line
        })
        .attr('fill', '#444')
        .attr('font-size', '11px')
        .text(d => d.type);
// Helper to get node color based on type and I14Y connection
function getNodeColor(d) {
    // Dataset
    if (d.type === 'dataset') return '#87CEFA'; // btn-dataset - light blue
    // Class
    if (d.type === 'class') return '#99ff99'; // btn-class
    // Data element
    if (d.type === 'data_element') {
        if (d.is_linked_to_concept === true) {
            return '#f9cee7'; // I14Y linked - pink
        } else {
            return '#ffcc99'; // btn-data-element (unconnected)
        }
    }
    // Concept (not visualized as node)
    return '#cccccc';
}

// Helper to get node title (handle multilingual)
function getNodeTitle(d) {
    let title = d.title;
    if (typeof title === 'object') {
        title = title.de || title.en || title.fr || title.it || Object.values(title)[0] || '';
    }
    return title;
}

// Helper to get node width based on text length
function getNodeWidth(d) {
    const title = getNodeTitle(d);
    // Minimum width 90, scale with text length
    return Math.max(90, title.length * 9);
}

// Helper to get node height
function getNodeHeight(d) {
    const lines = getWrappedTitle(d);
    return 20 + lines.length * 16; // base 20 + 16 per line
}
function getWrappedTitle(d) {
    let title = getNodeTitle(d);
    if (title.length <= 50) return [title];
    
    // Split into words
    const words = title.split(' ');
    const lines = [];
    let currentLine = '';
    
    for (const word of words) {
        if ((currentLine + ' ' + word).length <= 25) { // approx 25 chars per line
            currentLine += (currentLine ? ' ' : '') + word;
        } else {
            if (currentLine) lines.push(currentLine);
            currentLine = word;
            if (lines.length >= 2) { // max 3 lines total
                break;
            }
        }
    }
    if (currentLine) lines.push(currentLine);
    
    // If still too long, truncate last line
    if (lines.length > 0 && lines[lines.length - 1].length > 25) {
        lines[lines.length - 1] = lines[lines.length - 1].substring(0, 22) + '...';
    }
    
    return lines;
}
    
    // Update positions on simulation tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        // Update hitboxes
        d3.selectAll('.link-hitbox')
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        linkLabels
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2);
        
        node
            .attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    // Enable drag behavior
    node.call(d3.drag()
        .on('start', dragStart)
        .on('drag', dragMove)
        .on('end', dragEnd));
    
    console.log('Visualization rendered successfully');
    console.log('Simulation created:', simulation);
    console.log('Nodes in DOM:', g.selectAll('.node').size());
    console.log('Links in DOM:', g.selectAll('.link').size());
    
    // Debug: Check if nodes have positions
    console.log('Node positions:');
    nodes.forEach(node => {
        console.log(`  ${node.title}: (${node.x}, ${node.y})`);
    });
    
    // Debug: Check SVG structure
    console.log('SVG structure:', g.node());
}

// Drag functions
function dragStart(event, d) {
    // Stop propagation to prevent zoom behavior
    event.sourceEvent.stopPropagation();
    
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragMove(event, d) {
    // Account for zoom scale
    const transform = d3.zoomTransform(svg.node());
    d.fx = (event.x / transform.k) - (transform.x / transform.k);
    d.fy = (event.y / transform.k) - (transform.y / transform.k);
}

function dragEnd(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    
    // Keep the node fixed at its final position
    // (don't set fx/fy to null to prevent unwanted movement)
    // This makes the graph more stable after dragging
    
    // Save node position to server
    fetch('/api/nodes/' + d.id + '/position', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            x: d.x / width,
            y: d.y / height
        })
    });
}

// Global array to store selected nodes
let selectedNodes = [];

// Handle node click
function handleNodeClick(event, d) {
    event.stopPropagation();
    console.log('Node clicked:', d);
    
    // Check if Shift key is pressed for multi-select
    if (event.shiftKey) {
        // If node is already selected, unselect it
        const index = selectedNodes.findIndex(node => node.id === d.id);
        if (index !== -1) {
            selectedNodes.splice(index, 1);
            // Remove highlight
            d3.select(event.currentTarget)
                .classed('selected', false)
                .select('rect')
                .transition()
                .duration(300)
                .attr('stroke-width', 2)
                .attr('stroke', '#222');
            // Reset text styling
            d3.select(event.currentTarget)
                .select('text')
                .attr('font-weight', 'bold')
                .attr('fill', '#222');
        } else {
            // If we already have 2 nodes selected, remove the first one
            if (selectedNodes.length >= 2) {
                const oldestNode = selectedNodes.shift();
                // Remove highlight from oldest node
                d3.selectAll('.node')
                    .filter(n => n.id === oldestNode.id)
                    .classed('selected', false)
                    .select('rect')
                    .transition()
                    .duration(300)
                    .attr('stroke-width', 2)
                    .attr('stroke', '#222');
                // Reset text styling
                d3.selectAll('.node')
                    .filter(n => n.id === oldestNode.id)
                    .select('text')
                    .attr('font-weight', 'bold')
                    .attr('fill', '#222');
            }
            
            // Add the new node to selection
            selectedNodes.push(d);
            
            // Add highlight
            d3.select(event.currentTarget)
                .classed('selected', true)
                .select('rect')
                .transition()
                .duration(300)
                .attr('stroke-width', 4)
                .attr('stroke', '#ff9900');
            // Make text bold and change color
            d3.select(event.currentTarget)
                .select('text')
                .attr('font-weight', 'bolder')
                .attr('fill', '#000');
        }
        
        // Update selection status
        updateSelectionStatus();
        
        // Enable/disable connect button based on selection count
        document.getElementById('connect-selected-btn').style.display = 
            selectedNodes.length === 2 ? 'block' : 'none';
            
        return;
    }
    
    // Normal mode - select the node
    
    // Clear existing selection if clicking a different node
    if (selectedNode !== d.id) {
        // Clear existing selected nodes array
        selectedNodes = [];
        
        // Clear existing node highlighting
        d3.selectAll('.node')
            .classed('selected', false)
            .select('rect')
            .attr('stroke', '#222')
            .attr('stroke-width', 2);
        
        // Reset text styling for all nodes
        d3.selectAll('.node text')
            .attr('font-weight', 'bold')
            .attr('fill', '#222');
        
        // Clear existing edge highlighting
        d3.selectAll('.link')
            .classed('selected', false);
            
        // Hide edge UI if showing
        document.getElementById('detach-btn').style.display = 'none';
        document.getElementById('edge-status').style.display = 'none';
        
        // Add to selected nodes array
        selectedNodes.push(d);
        
        // Update selection status
        updateSelectionStatus();
        
        // Set the selected node
        selectedNode = d.id;
        selectedLink = null;
        
        // Highlight the selected node with enhanced visual feedback
        d3.select(event.currentTarget)
            .classed('selected', true)
            .select('rect')
            .attr('stroke', '#ff0000')
            .attr('stroke-width', 4)
            .style('filter', 'drop-shadow(0 0 6px rgba(255, 0, 0, 0.5))');
        
        // Make text bolder and change color
        d3.select(event.currentTarget)
            .select('text')
            .attr('font-weight', 'bolder')
            .attr('fill', '#000')
            .style('text-shadow', '1px 1px 2px rgba(255, 255, 255, 0.8)');
    } else {
        // Clicked same node again - clear selection
        selectedNode = null;
        selectedNodes = [];
        
        // Clear highlighting
        d3.select(event.currentTarget)
            .classed('selected', false)
            .select('rect')
            .attr('stroke', '#222')
            .attr('stroke-width', 2)
            .style('filter', null);
        
        // Reset text styling
        d3.select(event.currentTarget)
            .select('text')
            .attr('font-weight', 'bold')
            .attr('fill', '#222')
            .style('text-shadow', null);
        
        // Update selection status
        updateSelectionStatus();
    }
    
    // Call the global selectNode function to update UI
    if (window.selectNode) {
        window.selectNode(d.id);
    }
    
    // Hide the connect selected button
    document.getElementById('connect-selected-btn').style.display = 
        selectedNodes.length === 2 ? 'block' : 'none';
}

// Add handle for link click
function handleLinkClick(event, d) {
    event.stopPropagation();
    console.log('Link clicked:', d);
    
    // Clear any node selection
    selectedNode = null;
    selectedNodes = [];
    
    // Update selection status
    updateSelectionStatus();
    
    // Hide the connect selected button
    document.getElementById('connect-selected-btn').style.display = 'none';
    
    // Select the link
    selectedLink = d.id;
    
    // Highlight the selected link
    d3.selectAll('.link')
        .classed('selected', l => l.id === d.id);
    
    // Unhighlight any selected node
    d3.selectAll('.node')
        .classed('selected', false)
        .select('rect')
        .attr('stroke', '#222')
        .attr('stroke-width', 2)
        .style('filter', null);
    
    // Reset text styling for all nodes
    d3.selectAll('.node text:first-of-type')
        .attr('font-weight', 'bold')
        .attr('fill', '#222')
        .style('text-shadow', null);
    
    // Show the detach button
    document.getElementById('detach-btn').style.display = 'block';
    document.getElementById('edge-status').style.display = 'block';
    document.getElementById('selected-node-section').style.display = 'none';
    document.getElementById('no-node-selected').style.display = 'none';
    document.getElementById('selected-edge-section').style.display = 'block';
    
    // Call the global selectEdge function to update UI
    if (window.selectEdge) {
        window.selectEdge(d.id);
    }
}

// Update the selection status display
function updateSelectionStatus() {
    const selectionStatus = document.getElementById('selection-status');
    if (!selectionStatus) return;
    
    if (selectedNodes.length === 0) {
        selectionStatus.style.display = 'none';
        return;
    }
    
    selectionStatus.style.display = 'block';
    
    if (selectedNodes.length === 1) {
        selectionStatus.innerHTML = `<small><strong>Selected:</strong> ${selectedNodes[0].title}</small>`;
    } else if (selectedNodes.length === 2) {
        selectionStatus.innerHTML = `<small><strong>Selected:</strong> ${selectedNodes[0].title} and ${selectedNodes[1].title}</small>`;
    } else {
        selectionStatus.innerHTML = `<small><strong>Selected:</strong> ${selectedNodes.length} nodes</small>`;
    }
}

// Connect selected nodes
function connectSelectedNodes() {
    if (selectedNodes.length !== 2) {
        alert('Please select exactly 2 nodes to connect (hold Shift while clicking)');
        return;
    }
    
    const sourceId = selectedNodes[0].id;
    const targetId = selectedNodes[1].id;
    
    console.log('Connecting selected nodes:', sourceId, 'to', targetId);
    
    // Show a temporary connecting indicator
    const statusMessage = document.getElementById('selection-status');
    if (statusMessage) {
        statusMessage.innerHTML = '<small><strong>Status:</strong> Creating connection...</small>';
    }
    
    // Make API call to create connection
    fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            source: sourceId,
            target: targetId
        })
    })
    .then(response => {
        console.log('Connection API response status:', response.status);
        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Connection created successfully');
            
            // Show success message
            if (statusMessage) {
                statusMessage.innerHTML = '<small><strong>Success:</strong> Connection created!</small>';
                setTimeout(() => {
                    statusMessage.style.display = 'none';
                }, 3000);
            }
            
            // Clear selection
            selectedNodes = [];
            selectedNode = null;
            
            // Hide the connect button
            document.getElementById('connect-selected-btn').style.display = 'none';
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            console.error('Error creating connection:', data.error);
            alert('Error creating connection: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error creating connection:', error);
        alert('Error creating connection: ' + error.message);
    });
}

// Function to create a connection between nodes
function createConnection(sourceId, targetId) {
    console.log('Creating connection from', sourceId, 'to', targetId);
    
    // Show a temporary connecting indicator
    const statusMessage = document.getElementById('connection-status');
    if (statusMessage) {
        statusMessage.innerHTML = '<small><strong>Status:</strong> Creating connection...</small>';
    }
    
    // Make API call to create connection
    fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            source: sourceId,
            target: targetId
        })
    })
    .then(response => {
        console.log('Connection API response status:', response.status);
        if (!response.ok) {
            throw new Error(`Server responded with status ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Connection created successfully');
            
            // Show success message
            if (statusMessage) {
                statusMessage.innerHTML = '<small><strong>Success:</strong> Connection created!</small>';
                setTimeout(() => {
                    if (!connectionMode) {
                        statusMessage.style.display = 'none';
                    }
                }, 3000);
            }
            
            // Reload the graph
            loadGraphWithD3();
        } else {
            console.error('Error creating connection:', data.error);
            alert('Error creating connection: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error creating connection:', error);
        alert('Error creating connection: ' + error.message);
    });
}

// Reset view to center graph
function resetView() {
    console.log('Resetting view');
    
    // Reset zoom to default scale and position
    svg.transition()
       .duration(750)
       .call(zoom.transform, d3.zoomIdentity);
    
    // Clear selections
    selectedNode = null;
    selectedLink = null;
    
    // Reset node styles
    d3.selectAll('.node')
        .classed('selected', false)
        .select('rect')
        .attr('stroke', '#222')
        .attr('stroke-width', 2)
        .style('filter', null);
    
    // Reset text styling for all nodes
    d3.selectAll('.node text:first-of-type')
        .attr('font-weight', 'bold')
        .attr('fill', '#222')
        .style('text-shadow', null);
    
    // Request layout from server
    fetch('/api/graph/layout')
        .then(response => response.json())
        .then(data => {
            if (data.positions) {
                // Apply positions
                nodes.forEach(node => {
                    if (data.positions[node.id]) {
                        node.x = data.positions[node.id].x * width;
                        node.y = data.positions[node.id].y * height;
                    }
                });
                
                // Update visualization
                simulation.alpha(0.3).restart();
            }
        })
        .catch(error => {
            console.error('Error applying layout:', error);
        });
}

// Connect nodes in connection mode
function toggleConnectionMode() {
    connectionMode = !connectionMode;
    pendingConnection = null;
    
    console.log('Connection mode:', connectionMode ? 'ENABLED' : 'DISABLED');
    
    // Update connection mode UI
    const connectionStatus = document.getElementById('connection-status');
    const connectBtn = document.getElementById('connect-btn');
    
    if (connectionMode) {
        // Visual feedback for connection mode
        connectionStatus.classList.add('active');
        connectionStatus.style.display = 'block';
        connectBtn.classList.add('btn-warning');
        connectBtn.classList.remove('btn-outline-dark');
        connectionStatus.innerHTML = '<small><strong>Connection Mode:</strong> Select source node to start connection</small>';
    } else {
        connectionStatus.classList.remove('active');
        connectionStatus.style.display = 'none';
        connectBtn.classList.remove('btn-warning');
        connectBtn.classList.add('btn-outline-dark');
        
        // Remove source-node class from all nodes
        g.selectAll('.node').classed('source-node', false);
    }
}

// Function to handle background clicks
function handleBackgroundClick(event) {
    // This check prevents the background click from triggering on drag events
    if (event && event.defaultPrevented) return;
    
    console.log('Background clicked');
    
    // If in connection mode, cancel it
    if (connectionMode) {
        connectionMode = false;
        pendingConnection = null;
        
        // Reset connection mode UI
        const connectionStatus = document.getElementById('connection-status');
        const connectBtn = document.getElementById('connect-btn');
        
        connectionStatus.classList.remove('active');
        connectBtn.classList.remove('btn-warning');
        connectBtn.classList.add('btn-outline-dark');
        
        // Remove source-node class from all nodes
        g.selectAll('.node').classed('source-node', false);
        
        console.log('Connection mode canceled');
    }
    
    // Clear selections
    selectedNode = null;
    selectedLink = null;
    selectedNodes = []; // Clear the selected nodes array
    
    // Hide the connect selected button
    document.getElementById('connect-selected-btn').style.display = 'none';
    
    // Clear selection status
    updateSelectionStatus();
    
    // Unhighlight all nodes and links
    d3.selectAll('.node')
        .classed('selected', false)
        .select('rect')
        .attr('stroke', '#222')
        .attr('stroke-width', 2)
        .style('filter', null);
    
    // Reset text styling for all nodes
    d3.selectAll('.node text')
        .attr('font-weight', 'bold')
        .attr('fill', '#222')
        .style('text-shadow', null);
    
    d3.selectAll('.link')
        .classed('selected', false);
    
    // Hide node and edge panels, show the no-selection message
    if (window.clearNodeSelection) {
        window.clearNodeSelection();
    }
}

// Export functions for global access
window.initializeD3Visualization = initializeD3Visualization;
window._loadGraphWithD3Original = loadGraphWithD3; // Store original for wrapper
window.loadGraphWithD3 = loadGraphWithD3;
window._networkToggleConnectionMode = toggleConnectionMode; // Store original for switching visualizations
window.toggleConnectionMode = toggleConnectionMode;
window.resetView = resetView;
window.connectSelectedNodes = connectSelectedNodes;
window.updateSelectionStatus = updateSelectionStatus;

// Create a smart wrapper that will support multiple visualizations when available
// This allows external JS files to call loadGraphWithD3() which will work with any active visualization
setTimeout(() => {
    if (window.loadGraph && window.currentVisualization !== undefined) {
        window.loadGraphWithD3 = window.loadGraph;
    }
}, 100);

