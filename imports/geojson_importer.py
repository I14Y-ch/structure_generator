"""
GeoJSON file import functionality for SHACL Creator
Extracts structural model from GeoJSON feature properties
"""

from typing import Dict, List, Any, Tuple
import re


def infer_geojson_datatype(values: List[Any]) -> str:
    """
    Infer an XSD datatype from sampled GeoJSON property values
    
    Args:
        values: List of sample values from a GeoJSON property
        
    Returns:
        XSD datatype string (e.g., 'xsd:string', 'xsd:integer')
    """
    non_null_values = [v for v in values if v is not None]
    if not non_null_values:
        return 'xsd:string'

    if all(isinstance(v, bool) for v in non_null_values):
        return 'xsd:boolean'

    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null_values):
        return 'xsd:integer'

    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null_values):
        return 'xsd:decimal'

    if all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) for v in non_null_values):
        return 'xsd:date'

    if all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", v.strip()) for v in non_null_values):
        return 'xsd:dateTime'

    return 'xsd:string'


def import_geojson_structure(editor, geojson_payload: Dict[str, Any], dataset_name: str, 
                             source_filename: str) -> Tuple[bool, str]:
    """
    Extract structural model from GeoJSON and store in editor graph
    
    Args:
        editor: FlaskSHACLGraphEditor instance
        geojson_payload: Parsed GeoJSON object
        dataset_name: Name for the dataset
        source_filename: Original filename
        
    Returns:
        Tuple of (success: bool, message: str)
        
    Raises:
        ValueError: If GeoJSON structure is invalid
    """
    # Import at function level to avoid circular dependency
    try:
        from app import SHACLNode, slug_identifier
    except ImportError:
        try:
            from .ttl_importer import SHACLNode, slug_identifier
        except ImportError:
            try:
                from ttl_importer import SHACLNode, slug_identifier
            except ImportError:
                # Create stub classes if needed
                raise ImportError("Cannot import SHACLNode and slug_identifier")

    if not isinstance(geojson_payload, dict):
        raise ValueError('GeoJSON content must be a JSON object.')

    geo_type = geojson_payload.get('type')
    if geo_type == 'FeatureCollection':
        features = geojson_payload.get('features', [])
    elif geo_type == 'Feature':
        features = [geojson_payload]
    else:
        raise ValueError('Unsupported GeoJSON type. Expected FeatureCollection or Feature.')

    if not isinstance(features, list) or not features:
        raise ValueError('GeoJSON does not contain any features.')

    feature_count = len(features)

    # Reset structure
    editor.reset_structure()

    # Get or create dataset node
    dataset_node = None
    for node in editor.nodes.values():
        if node.type == 'dataset':
            dataset_node = node
            break

    if not dataset_node:
        dataset_node = SHACLNode('dataset', title=dataset_name, description=f"Dataset imported from {source_filename}")
        editor.nodes[dataset_node.id] = dataset_node

    dataset_node.title = dataset_name
    dataset_node.description = {'de': f"Dataset imported from {source_filename}"}
    
    # Analyze properties from features and derive occurrence-based cardinality
    collected_properties = {}
    non_null_counts = {}
    for feature in features:
        props = feature.get('properties', {})
        if isinstance(props, dict):
            for key, value in props.items():
                if key not in collected_properties:
                    collected_properties[key] = []
                collected_properties[key].append(value)
                if value is not None:
                    non_null_counts[key] = non_null_counts.get(key, 0) + 1

    # Create data element nodes for each property
    for prop_name, values in collected_properties.items():
        datatype = infer_geojson_datatype(values)
        de_node = SHACLNode('data_element', title=prop_name, description=f"")
        de_node.datatype = datatype
        de_node.identifier = slug_identifier(prop_name)
        de_node.local_name = slug_identifier(prop_name)
        de_node.min_count = 1 if non_null_counts.get(prop_name, 0) == feature_count else 0
        de_node.max_count = 1
        editor.nodes[de_node.id] = de_node

        # Connect properties directly to dataset (no intermediate FeatureCollection class)
        edge_id = f"{dataset_node.id}-{de_node.id}"
        editor.edges[edge_id] = {
            'id': edge_id,
            'from': dataset_node.id,
            'to': de_node.id,
            'cardinality': f"{de_node.min_count}..1"
        }
        dataset_node.connections.add(de_node.id)
        de_node.connections.add(dataset_node.id)

    # Add geometry if present
    if features and 'geometry' in features[0]:
        geom = features[0]['geometry']
        if geom:
            geom_type = geom.get('type', 'Point')
            geom_node = SHACLNode('data_element', title='geometry', 
                                 description=f"GeoJSON geometry ({geom_type})")
            geom_node.datatype = 'xsd:string'
            geom_node.local_name = 'geometry'
            editor.nodes[geom_node.id] = geom_node

            edge_id = f"{dataset_node.id}-{geom_node.id}"
            editor.edges[edge_id] = {
                'id': edge_id,
                'from': dataset_node.id,
                'to': geom_node.id,
                'cardinality': '1..1'
            }
            dataset_node.connections.add(geom_node.id)
            geom_node.connections.add(dataset_node.id)

    return True, f"Imported {feature_count} GeoJSON features successfully"


def import_geojson_file(file_content: bytes, dataset_name: str, editor=None) -> Tuple[bool, str]:
    """
    Import a GeoJSON file and extract structural model
    
    Args:
        file_content: Raw file bytes
        dataset_name: Name for the imported dataset
        editor: Optional FlaskSHACLGraphEditor instance
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    import json
    
    try:
        # Decode file content
        try:
            text_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            return False, "File is not valid UTF-8"
        
        # Parse JSON
        try:
            geojson_data = json.loads(text_content)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
        
        # Process structure if editor provided
        if editor:
            success, message = import_geojson_structure(editor, geojson_data, dataset_name, "imported.geojson")
            return success, message
        else:
            return True, "GeoJSON parsed successfully"
            
    except Exception as e:
        return False, f"Error importing GeoJSON: {str(e)}"

    # Create feature class
    feature_class_name = geojson_payload.get('name') or dataset_name or Path(source_filename).stem or 'Feature'
    class_node = SHACLNode('class', title=feature_class_name, description='Feature class extracted from GeoJSON')
    class_node.identifier = slug_identifier(feature_class_name, fallback='feature')
    class_node.local_name = class_node.identifier
    editor.nodes[class_node.id] = class_node

    # Connect dataset to class
    dataset_edge_id = f"{dataset_node.id}-{class_node.id}"
    editor.edges[dataset_edge_id] = {
        'id': dataset_edge_id,
        'from': dataset_node.id,
        'to': class_node.id,
        'cardinality': '1..1'
    }
    dataset_node.connections.add(class_node.id)
    class_node.connections.add(dataset_node.id)

    # Analyze properties
    property_values: Dict[str, List[Any]] = {}
    present_count: Dict[str, int] = {}
    non_null_count: Dict[str, int] = {}
    geometry_types = set()
    geometry_present_count = 0

    for feature in features:
        if not isinstance(feature, dict):
            continue

        properties = feature.get('properties')
        if not isinstance(properties, dict):
            properties = {}

        for key, value in properties.items():
            property_values.setdefault(key, []).append(value)
            present_count[key] = present_count.get(key, 0) + 1
            if value is not None:
                non_null_count[key] = non_null_count.get(key, 0) + 1

        geometry = feature.get('geometry')
        if isinstance(geometry, dict):
            geometry_type = geometry.get('type')
            if geometry_type:
                geometry_types.add(str(geometry_type))
                geometry_present_count += 1

    # Create data elements for properties
    order = 0
    for property_name in sorted(property_values.keys()):
        values = property_values[property_name]
        data_node = SHACLNode('data_element', title=property_name, description=f"GeoJSON property: {property_name}")
        data_node.identifier = slug_identifier(property_name, fallback='field')
        data_node.local_name = property_name
        data_node.datatype = infer_geojson_datatype(values)
        data_node.min_count = 1 if non_null_count.get(property_name, 0) == feature_count else 0
        data_node.max_count = 1
        data_node.order = order

        # Extract enumeration values
        text_values = sorted({str(v).strip() for v in values if isinstance(v, str) and str(v).strip()})
        if 0 < len(text_values) <= 20:
            data_node.in_values = text_values

        editor.nodes[data_node.id] = data_node

        # Connect class to data element
        edge_id = f"{class_node.id}-{data_node.id}"
        editor.edges[edge_id] = {
            'id': edge_id,
            'from': class_node.id,
            'to': data_node.id,
            'cardinality': f"{data_node.min_count}..1"
        }
        class_node.connections.add(data_node.id)
        data_node.connections.add(class_node.id)
        order += 10

    # Add geometry type as a data element if present
    if geometry_types:
        geometry_node = SHACLNode('data_element', title='geometry_type', 
                                  description='Geometry type observed in GeoJSON features')
        geometry_node.identifier = 'geometry_type'
        geometry_node.local_name = 'geometry_type'
        geometry_node.datatype = 'xsd:string'
        geometry_node.min_count = 1 if geometry_present_count == feature_count else 0
        geometry_node.max_count = 1
        geometry_node.order = order
        geometry_node.in_values = sorted(geometry_types)

        editor.nodes[geometry_node.id] = geometry_node

        edge_id = f"{class_node.id}-{geometry_node.id}"
        editor.edges[edge_id] = {
            'id': edge_id,
            'from': class_node.id,
            'to': geometry_node.id,
            'cardinality': f"{geometry_node.min_count}..1"
        }
        class_node.connections.add(geometry_node.id)
        geometry_node.connections.add(class_node.id)

    return True, f"GeoJSON structure imported successfully ({feature_count} features)"


def import_geojson_file(file_content: bytes, dataset_name: str, editor=None) -> Tuple[bool, str]:
    """
    Import a GeoJSON file and extract structural model
    
    Args:
        file_content: Binary content of GeoJSON file
        dataset_name: Name for the dataset
        editor: FlaskSHACLGraphEditor instance
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    import json
    
    try:
        # Decode file content
        try:
            text_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            return False, "File is not valid UTF-8"
        
        # Parse JSON
        try:
            geojson_payload = json.loads(text_content)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
        
        # Process structure if editor provided
        if editor:
            success, message = import_geojson_structure(
                editor, geojson_payload, dataset_name, f"{dataset_name}.geojson"
            )
            return success, message
        
        return True, "GeoJSON parsed successfully"
        
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Failed to import GeoJSON file: {str(e)}"
