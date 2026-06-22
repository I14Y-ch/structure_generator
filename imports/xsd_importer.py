"""
XSD file import functionality for SHACL Creator
Handles conversion of XSD schema files to SHACL TTL format
"""

from typing import Tuple
from rdflib import Graph, URIRef, RDF, RDFS, SH, DCTERMS


def import_xsd_file(file_content: bytes, dataset_name: str, filename: str = "schema.xsd", 
                    editor=None) -> Tuple[bool, str]:
    """
    Import an XSD schema file and convert to SHACL structure
    
    Args:
        file_content: Binary content of XSD file
        dataset_name: Name for the imported dataset
        filename: Original XSD filename
        editor: FlaskSHACLGraphEditor instance for updating structure
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Import here to avoid circular dependency
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from xsd_importer import xsd_to_ttl
        except ImportError:
            try:
                from xsd_importer import xsd_to_ttl
            except ImportError:
                return False, "Cannot import xsd_to_ttl function"
        
        # Decode XSD content
        xsd_data = file_content.decode('utf-8')
        
        # Convert to TTL using existing xsd_importer
        ttl = xsd_to_ttl(xsd_data, dataset_name)
        
        if not ttl:
            return False, "Failed to convert XSD to TTL"
        
        # If editor is provided, process the TTL to extract structure
        if editor:
            try:
                success, message = _process_xsd_structure(editor, ttl, dataset_name, filename)
                return success, message
            except Exception as e:
                # Continue with basic import even if advanced processing fails
                return False, f"Failed to process XSD structure: {str(e)}"
        
        return True, "XSD file converted to TTL successfully"
        
    except UnicodeDecodeError:
        return False, "Failed to decode XSD file - check encoding"
    except Exception as e:
        return False, f"Failed to import XSD file: {str(e)}"


def _process_xsd_structure(editor, ttl: str, dataset_name: str, filename: str) -> Tuple[bool, str]:
    """
    Process TTL from XSD and extract structure into editor
    
    Args:
        editor: FlaskSHACLGraphEditor instance
        ttl: TTL content generated from XSD
        dataset_name: Dataset name
        filename: Original filename
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Import at function level to avoid circular dependency
    try:
        from app import SHACLNode
    except ImportError:
        try:
            from .ttl_importer import SHACLNode
        except ImportError:
            try:
                from ttl_importer import SHACLNode
            except ImportError:
                raise ImportError("Cannot import SHACLNode")
    
    # Parse the TTL
    g = Graph()
    g.parse(data=ttl, format='turtle')
    
    # Reset full structure for clean import
    editor.reset_structure()
    
    # Get or create dataset node
    dataset_node = None
    for node in editor.nodes.values():
        if node.type == 'dataset':
            dataset_node = node
            break
    
    if not dataset_node:
        dataset_node = SHACLNode('dataset', title=dataset_name, description=f"Dataset imported from {filename}")
        editor.nodes[dataset_node.id] = dataset_node
    
    dataset_node.title = dataset_name
    dataset_node.description = f"Dataset imported from {filename}"
    
    # Track processed node shapes for edge creation
    processed_nodes = {}  # str(shape_uri) -> SHACLNode
    
    # Helper functions
    def _get_name(uri):
        for _, _, v in g.triples((uri, SH.name, None)):
            return str(v)
        for _, _, v in g.triples((uri, RDFS.label, None)):
            return str(v)
        return ""
    
    def _get_identifier(uri):
        return str(uri).split('/')[-1].split('#')[-1]
    
    def _get_desc(uri):
        for prop in [SH.description, RDFS.comment, DCTERMS.description]:
            for _, _, v in g.triples((uri, prop, None)):
                return str(v)
        return ""
    
    def _apply_prop_constraints(node, uri):
        for _, _, v in g.triples((uri, SH.datatype, None)):
            dt = str(v)
            if 'XMLSchema#' in dt:
                dt = 'xsd:' + dt.split('#')[-1]
            node.datatype = dt
            break
        for _, _, v in g.triples((uri, SH.order, None)):
            try:
                node.order = int(v)
            except (ValueError, TypeError):
                node.order = None
            break
        for _, _, v in g.triples((uri, SH.minCount, None)):
            try:
                node.min_count = int(v)
            except (ValueError, TypeError):
                pass
        for _, _, v in g.triples((uri, SH.maxCount, None)):
            try:
                node.max_count = int(v)
            except (ValueError, TypeError):
                pass
        for _, _, v in g.triples((uri, SH.minLength, None)):
            try:
                node.min_length = int(v)
            except (ValueError, TypeError):
                pass
        for _, _, v in g.triples((uri, SH.maxLength, None)):
            try:
                node.max_length = int(v)
            except (ValueError, TypeError):
                pass
        for _, _, v in g.triples((uri, SH.pattern, None)):
            node.pattern = str(v)
        for _, _, v in g.triples((uri, SH.minInclusive, None)):
            node.min_inclusive = str(v)
        for _, _, v in g.triples((uri, SH.maxInclusive, None)):
            node.max_inclusive = str(v)
        for _, _, v in g.triples((uri, SH.minExclusive, None)):
            node.min_exclusive = str(v)
        for _, _, v in g.triples((uri, SH.maxExclusive, None)):
            node.max_exclusive = str(v)
        
        # sh:in enumeration
        in_values = []
        for _, _, head in g.triples((uri, SH['in'], None)):
            cur = head
            while cur and cur != RDF.nil:
                for _, _, first in g.triples((cur, RDF.first, None)):
                    in_values.append(str(first))
                nexts = list(g.objects(cur, RDF.rest))
                cur = nexts[0] if nexts else None
        if in_values:
            node.in_values = in_values
    
    # Pass 1: Create class nodes for all NodeShapes
    node_shapes = [s for s, _, _ in g.triples((None, RDF.type, SH.NodeShape))]
    
    for shape_uri in node_shapes:
        node_name = _get_name(shape_uri)
        node_identifier = _get_identifier(shape_uri)
        description = _get_desc(shape_uri)
        shacl_node = SHACLNode('class', title=node_name, description=description)
        shacl_node.local_name = node_identifier
        shacl_node.identifier = node_identifier
        editor.nodes[shacl_node.id] = shacl_node
        processed_nodes[str(shape_uri)] = shacl_node
    
    # Pass 2: Create data_element nodes for PropertyShapes inside each class
    for shape_uri in node_shapes:
        class_node = processed_nodes[str(shape_uri)]
        
        for _, _, prop_uri in g.triples((shape_uri, SH.property, None)):
            prop_name = _get_name(prop_uri)
            prop_identifier = _get_identifier(prop_uri)
            description = _get_desc(prop_uri)
            
            # Check if this PropertyShape has sh:node pointing to a known class
            node_targets = list(g.objects(prop_uri, SH.node))
            if node_targets and str(node_targets[0]) in processed_nodes:
                target_class = processed_nodes[str(node_targets[0])]
                edge_id = f"{class_node.id}-{target_class.id}"
                if edge_id not in editor.edges:
                    editor.edges[edge_id] = {
                        'id': edge_id,
                        'from': class_node.id,
                        'to': target_class.id,
                        'cardinality': '1..1'
                    }
                    class_node.connections.add(target_class.id)
                    target_class.connections.add(class_node.id)
                continue
            
            # Create regular data element
            de_node = SHACLNode('data_element', title=prop_name, description=description)
            de_node.local_name = prop_identifier
            _apply_prop_constraints(de_node, prop_uri)
            
            editor.nodes[de_node.id] = de_node
            
            # Determine cardinality from constraints
            cardinality = "1..1"
            min_counts = list(g.objects(prop_uri, SH.minCount))
            max_counts = list(g.objects(prop_uri, SH.maxCount))
            if min_counts or max_counts:
                min_c = int(min_counts[0]) if min_counts else 0
                max_c = int(max_counts[0]) if max_counts else None
                cardinality = f"{min_c}..{'n' if max_c is None else max_c}"
            
            # Connect to class
            edge_id = f"{class_node.id}-{de_node.id}"
            editor.edges[edge_id] = {
                'id': edge_id,
                'from': class_node.id,
                'to': de_node.id,
                'cardinality': cardinality
            }
            class_node.connections.add(de_node.id)
            de_node.connections.add(class_node.id)
    
    # Pass 3: Connect top-level class nodes to the dataset
    # A class is "top-level" when no other class references it via sh:node
    referenced_classes = set()
    for _, prop_uri, _ in g.triples((None, SH.property, None)):
        for _, _, node_ref in g.triples((prop_uri, SH.node, None)):
            if str(node_ref) in processed_nodes:
                referenced_classes.add(str(node_ref))
    
    for shape_uri, class_node in processed_nodes.items():
        if shape_uri not in referenced_classes:
            edge_id = f"{dataset_node.id}-{class_node.id}"
            if edge_id not in editor.edges:
                editor.edges[edge_id] = {
                    'id': edge_id,
                    'from': dataset_node.id,
                    'to': class_node.id,
                    'cardinality': '1..1'
                }
                dataset_node.connections.add(class_node.id)
                class_node.connections.add(dataset_node.id)
    
    return True, f"XSD structure imported successfully ({len(processed_nodes)} classes)"
