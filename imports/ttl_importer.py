"""
TTL Import functionality for SHACL Creator
Handles parsing of Turtle RDF files and conversion to SHACL graph structures
"""

import uuid
from typing import Optional
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, DCTERMS, DCAT
from rdflib.namespace import RDF as RDF_NS


def parse_ttl_to_nodes(g: Graph, editor) -> bool:
    """Parse RDF graph back to SHACLNode objects
    
    Args:
        g: RDFLib Graph object parsed from TTL
        editor: FlaskSHACLGraphEditor instance to populate with nodes
        
    Returns:
        True if parsing was successful, False otherwise
    """
    try:
        from rdflib.namespace import QB
        
        # Define namespaces
        SH = Namespace("http://www.w3.org/ns/shacl#")
        OWL = Namespace("http://www.w3.org/2002/07/owl#")
        
        # Find NodeShapes (classes and dataset)
        node_shapes = list(g.subjects(RDF_NS.type, SH.NodeShape))
        dataset_node = None
        created_nodes = {}
        
        print(f"Found {len(node_shapes)} NodeShapes")
        
        # First identify which NodeShape is the dataset
        dataset_shape = None
        for shape in node_shapes:
            # Check for dataset-specific indicators
            is_dataset = False
            
            # Check for data structure definition
            if (shape, RDF_NS.type, QB.DataStructureDefinition) in g:
                is_dataset = True
            
            # Check for DCAT dataset type
            if (shape, RDF_NS.type, DCAT.Dataset) in g:
                is_dataset = True
                
            # Check for version information (typically only on datasets)
            if list(g.objects(shape, Namespace("http://purl.org/pav/").version)):
                is_dataset = True
                
            # Check if it has validFrom (typically only on datasets)
            if list(g.objects(shape, Namespace("https://schema.org/").validFrom)):
                is_dataset = True
                
            if is_dataset:
                dataset_shape = shape
                break
        
        def _collect_multilingual(literals, fallback_literals=None):
            """Collect all language-tagged literals into a dict; fall back to untagged as 'de'."""
            result = {}
            source = literals if literals else (fallback_literals or [])
            for lit in source:
                lang = getattr(lit, 'language', None)
                if lang:
                    result[lang] = str(lit)
            if not result:
                # No language tags — use first available as 'de' fallback
                if source:
                    result['de'] = str(source[0])
            return result

        # First pass: Create dataset and class nodes
        for shape in node_shapes:
            # Get basic properties
            titles = list(g.objects(shape, DCTERMS.title))
            labels = list(g.objects(shape, SH.name)) or list(g.objects(shape, RDFS.label))
            descriptions = list(g.objects(shape, DCTERMS.description)) or list(g.objects(shape, SH.description))

            # Collect all available language variants
            title = _collect_multilingual(titles, labels)
            description = _collect_multilingual(descriptions)
            
            # Determine if this is a dataset or class
            node_id = str(uuid.uuid4())
            node_type = 'dataset' if shape == dataset_shape else 'class'
            
            if not dataset_node and node_type == 'dataset':
                dataset_node = node_id
            
            # Create SHACLNode
            node_data = {
                'id': node_id,
                'type': node_type,
                'title': title,
                'description': description
            }
            
            from app import SHACLNode
            node = SHACLNode.from_dict(node_data)
            editor.nodes[node_id] = node
            created_nodes[str(shape)] = node_id
            
            display_title = title.get('de') or next(iter(title.values()), '') if isinstance(title, dict) else title
            print(f"Created {node_type}: {display_title}")
        
        # Second pass: Create data element nodes from PropertyShapes
        property_shapes = list(g.subjects(RDF_NS.type, SH.PropertyShape))
        
        for prop_shape in property_shapes:
            # Handle object properties (class-to-class relationship) separately
            is_object_property = (prop_shape, RDF_NS.type, OWL.ObjectProperty) in g
            
            # Get property details
            titles = list(g.objects(prop_shape, DCTERMS.title))
            labels = list(g.objects(prop_shape, SH.name)) or list(g.objects(prop_shape, RDFS.label))
            descriptions = list(g.objects(prop_shape, DCTERMS.description)) or list(g.objects(prop_shape, SH.description))

            # Collect all available language variants
            title = _collect_multilingual(titles, labels)
            description = _collect_multilingual(descriptions)
            
            # Extract constraints
            min_count = None
            max_count = None
            min_length = None
            max_length = None
            pattern = None
            datatype = None
            
            # Get cardinality constraints
            min_counts = list(g.objects(prop_shape, SH.minCount))
            if min_counts:
                min_count = int(min_counts[0])
                
            max_counts = list(g.objects(prop_shape, SH.maxCount))
            if max_counts:
                max_count = int(max_counts[0])
            
            # Get length constraints
            min_lengths = list(g.objects(prop_shape, SH.minLength))
            if min_lengths:
                min_length = int(min_lengths[0])
                
            max_lengths = list(g.objects(prop_shape, SH.maxLength))
            if max_lengths:
                max_length = int(max_lengths[0])
            
            # Get pattern
            patterns = list(g.objects(prop_shape, SH.pattern))
            if patterns:
                pattern = str(patterns[0])
            
            # Get datatype
            datatypes = list(g.objects(prop_shape, SH.datatype))
            if datatypes:
                datatype = str(datatypes[0])
                
            # Extract enumeration values (sh:in)
            in_values = []
            in_lists = list(g.objects(prop_shape, SH['in']))
            if in_lists:
                # Follow the RDF list structure
                current = in_lists[0]
                while current and current != RDF_NS.nil:
                    value_literals = list(g.objects(current, RDF_NS.first))
                    if value_literals:
                        in_values.append(str(value_literals[0]))
                    next_nodes = list(g.objects(current, RDF_NS.rest))
                    if next_nodes:
                        current = next_nodes[0]
                    else:
                        break
            
            # Read sh:order
            order = None
            order_vals = list(g.objects(prop_shape, SH.order))
            if order_vals:
                try:
                    order = int(order_vals[0])
                except (ValueError, TypeError):
                    pass

            # Check for conformsTo to identify data elements with concept links
            conforms_to_uris = list(g.objects(prop_shape, DCTERMS.conformsTo))
            conforms_to_uri = conforms_to_uris[0] if conforms_to_uris else None
                
            # Create data element node (not concept)
            node_id = str(uuid.uuid4())
            node_data = {
                'id': node_id,
                'type': 'data_element',  # Always create as data_element instead of concept
                'title': title,
                'description': description,
                'min_count': min_count,
                'max_count': max_count,
                'min_length': min_length,
                'max_length': max_length,
                'pattern': pattern,
                'datatype': datatype or 'xsd:string',
                'in_values': in_values,
                'order': order
            }
            
            # If this is an object property pointing to a class, handle it differently
            if is_object_property:
                # Extract the target class that this object property points to
                node_refs = list(g.objects(prop_shape, SH.node))
                if node_refs:
                    target_class_uri = str(node_refs[0])
                    if target_class_uri in created_nodes:
                        # The class has already been created, so just store the reference
                        # We'll create connections in the next pass
                        created_nodes[str(prop_shape)] = created_nodes[target_class_uri]
                        _dt = title.get('de') or next(iter(title.values()), '') if isinstance(title, dict) else title
                        print(f"Mapped object property {_dt} to class reference")
                        continue
            
            # Add the local_name for the data element (from path or extracted from shape URI)
            local_name = None
            paths = list(g.objects(prop_shape, SH.path))
            if paths:
                path_str = str(paths[0])
                local_name = path_str.split('/')[-1].replace('#', '')
                
            if not local_name:
                local_name = str(prop_shape).split('/')[-1].replace('#', '')
                
            node_data['local_name'] = local_name
                
            # If this data element has a conformsTo link, set it
            if conforms_to_uri:
                node_data['conforms_to_concept_uri'] = str(conforms_to_uri)
                node_data['is_linked_to_concept'] = True
            
            from app import SHACLNode
            node = SHACLNode.from_dict(node_data)
            editor.nodes[node_id] = node
            created_nodes[str(prop_shape)] = node_id
            
            # Log message based on whether it has a concept link
            _dt = title.get('de') or next(iter(title.values()), '') if isinstance(title, dict) else title
            if conforms_to_uri:
                print(f"Created data element with concept link: {_dt}")
            else:
                print(f"Created data element: {_dt}")
        
        # Third pass: Create connections based on sh:property relationships
        for shape in node_shapes:
            shape_node_id = created_nodes.get(str(shape))
            if not shape_node_id:
                continue
                
            # Find properties of this shape
            properties = list(g.objects(shape, SH.property))
            for prop in properties:
                prop_node_id = created_nodes.get(str(prop))
                if prop_node_id:
                    # Connect shape to property
                    editor.nodes[shape_node_id].connections.add(prop_node_id)
                    editor.nodes[prop_node_id].connections.add(shape_node_id)
                    
                    # Create edge with cardinality
                    cardinality = "1..1"  # Default
                    min_counts = list(g.objects(prop, SH.minCount))
                    max_counts = list(g.objects(prop, SH.maxCount))
                    
                    if min_counts or max_counts:
                        min_c = int(min_counts[0]) if min_counts else 0
                        max_c = int(max_counts[0]) if max_counts else None
                        
                        if max_c is None:
                            cardinality = f"{min_c}..n"
                        else:
                            cardinality = f"{min_c}..{max_c}"
                    
                    editor.create_edge(shape_node_id, prop_node_id, cardinality)
                    def _dt(t): return t.get('de') or next(iter(t.values()), '') if isinstance(t, dict) else t
                    print(f"Connected {_dt(editor.nodes[shape_node_id].title)} -> {_dt(editor.nodes[prop_node_id].title)} ({cardinality})")
        
        # Connect everything to dataset if we have one
        if dataset_node:
            for node_id, node in editor.nodes.items():
                if node_id != dataset_node and node.type in ['class', 'concept']:
                    # Only connect if not already connected to something else
                    if not node.connections:
                        editor.nodes[dataset_node].connections.add(node_id)
                        editor.nodes[node_id].connections.add(dataset_node)
                        editor.create_edge(dataset_node, node_id, "1..1")
        
        return True
        
    except Exception as e:
        print(f"Error in parse_ttl_to_nodes: {e}")
        return False


def import_ttl_file(file_content: str, editor) -> bool:
    """Import a TTL file and populate the editor
    
    Args:
        file_content: String content of TTL file
        editor: FlaskSHACLGraphEditor instance to populate
        
    Returns:
        True if import was successful, False otherwise
    """
    try:
        # Parse TTL file using RDFLib
        g = Graph()
        g.parse(data=file_content, format='turtle')
        
        # Clear existing data
        editor.nodes.clear()
        editor.edges.clear()
        
        # Convert RDF graph back to SHACLNode objects
        success = parse_ttl_to_nodes(g, editor)
        
        return success
            
    except Exception as e:
        print(f"Failed to import TTL: {e}")
        return False


def process_csv_ttl_import(editor, ttl: str, source_filename: str, dataset_name: str):
    """Parse a CSV-generated TTL string and populate the editor with the resulting nodes.
    
    Args:
        editor: FlaskSHACLGraphEditor instance to populate
        ttl: TTL string content
        source_filename: Name of the source CSV file
        dataset_name: Name to assign to the dataset
    """
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, SH, RDFS, DCTERMS
    from app import SHACLNode
    
    g = Graph()
    g.parse(data=ttl, format='turtle')
    SUG = Namespace("https://www.i14y.admin.ch/vocab#")

    editor.reset_structure()

    dataset_node = None
    for node in editor.nodes.values():
        if node.type == 'dataset':
            dataset_node = node
            break

    if not dataset_node:
        dataset_node = SHACLNode('dataset', title=dataset_name)
        editor.nodes[dataset_node.id] = dataset_node

    dataset_node.title = dataset_name
    dataset_node.description = f"Dataset imported from {source_filename}"

    property_shapes = [s for s, _, _ in g.triples((None, RDF.type, SH.PropertyShape))]

    for shape in property_shapes:
        prop_name = None
        for _, _, name in g.triples((shape, SH.name, None)):
            prop_name = str(name)
            break
        if not prop_name:
            prop_name = ""

        datatype = None
        for _, _, dt in g.triples((shape, SH.datatype, None)):
            datatype = str(dt)
            break

        # Create data element from property shape
        data_element = SHACLNode('data_element', title=prop_name or "Unknown")
        
        # Set datatype
        if datatype:
            data_element.datatype = datatype
        
        # Extract min/max constraints
        min_counts = list(g.objects(shape, SH.minCount))
        if min_counts:
            data_element.min_count = int(min_counts[0])
            
        max_counts = list(g.objects(shape, SH.maxCount))
        if max_counts:
            data_element.max_count = int(max_counts[0])
        
        # Extract length constraints
        min_lengths = list(g.objects(shape, SH.minLength))
        if min_lengths:
            data_element.min_length = int(min_lengths[0])
            
        max_lengths = list(g.objects(shape, SH.maxLength))
        if max_lengths:
            data_element.max_length = int(max_lengths[0])
        
        # Extract pattern
        patterns = list(g.objects(shape, SH.pattern))
        if patterns:
            data_element.pattern = str(patterns[0])
        
        # Extract enumeration values
        in_lists = list(g.objects(shape, SH['in']))
        if in_lists:
            current = in_lists[0]
            while current and current != RDF.nil:
                value_literals = list(g.objects(current, RDF.first))
                if value_literals:
                    data_element.in_values.append(str(value_literals[0]))
                next_nodes = list(g.objects(current, RDF.rest))
                if next_nodes:
                    current = next_nodes[0]
                else:
                    break

        editor.nodes[data_element.id] = data_element
        dataset_node.connections.add(data_element.id)
        data_element.connections.add(dataset_node.id)
        editor.create_edge(dataset_node.id, data_element.id, "1..1")
