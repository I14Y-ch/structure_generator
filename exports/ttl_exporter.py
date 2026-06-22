"""
TTL Export functionality for SHACL Creator
Handles generation and export of Turtle RDF files from SHACL graph structures
"""

import re
import unicodedata
from typing import Dict, Optional, Tuple
from rdflib import Graph, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, XSD, SH, OWL, RDFS, DCTERMS
from datetime import datetime


def parse_cardinality(cardinality_str: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse cardinality string like '1..1', '0..n', '1..n', etc.
    
    Returns:
        Tuple of (min_count, max_count) where None means unlimited
    """
    if not cardinality_str:
        return None, None
    
    try:
        if '..' in cardinality_str:
            min_str, max_str = cardinality_str.split('..', 1)
            
            # Parse minimum
            min_count = int(min_str.strip()) if min_str.strip().isdigit() else None
            
            # Parse maximum
            max_str = max_str.strip()
            if max_str in ['n', '*', 'unlimited']:
                max_count = None  # Unlimited
            elif max_str.isdigit():
                max_count = int(max_str)
            else:
                max_count = None
                
            return min_count, max_count
        else:
            # Single number like "1" means exactly that count
            if cardinality_str.strip().isdigit():
                count = int(cardinality_str.strip())
                return count, count
    except (ValueError, AttributeError):
        pass
    
    # Default fallback
    return None, None


def get_unique_lang_values(multilang_dict, sanitize_literal_func):
    """Only keep one language per unique content value to avoid SHACL violations"""
    seen_values = {}
    unique_values = {}
    for lang, value in multilang_dict.items():
        if lang in ['de', 'fr', 'it', 'en'] and value:
            cleaned_value = sanitize_literal_func(value)
            if cleaned_value not in seen_values:
                seen_values[cleaned_value] = lang
                unique_values[lang] = value
            # If content is identical, prefer 'de', then 'en', then others
            elif seen_values[cleaned_value] not in ['de'] and lang in ['de']:
                # Replace with German if we had a non-German version
                old_lang = seen_values[cleaned_value]
                if old_lang in unique_values:
                    del unique_values[old_lang]
                seen_values[cleaned_value] = lang
                unique_values[lang] = value
    return unique_values


def generate_full_ttl(nodes: Dict, base_uri: str, edges: Dict = None) -> str:
    """Generate full TTL using the RDF-based approach directly
    
    Args:
        nodes: Dictionary of SHACLNode objects keyed by node ID
        base_uri: Base URI for the dataset namespace
        edges: Optional dictionary of edge definitions with cardinality
        
    Returns:
        TTL content as string
    """
    
    # Find dataset node  
    dataset_node = None
    for node in nodes.values():
        if node.type == 'dataset':
            dataset_node = node
            break
    
    if not dataset_node:
        raise ValueError("No dataset node found")
    
    # Helper function to extract text from multilingual objects or strings
    def get_text_value(value, lang='de'):
        """Extract text from a value that might be a string or multilingual dict"""
        if value is None:
            return ""
        if isinstance(value, dict):
            # Try requested language first, then fallback chain
            return (value.get(lang) or 
                   value.get('de') or 
                   value.get('en') or 
                   value.get('fr') or 
                   value.get('it') or 
                   next(iter(value.values()), ""))
        return str(value)
    
    def slug_id(value: str, fallback: str = "property") -> str:
        """Build a lowercase ASCII-safe identifier for use in the dataset namespace prefix."""
        raw = (value or "").strip()
        if not raw:
            return fallback

        normalized = unicodedata.normalize("NFKD", raw)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"\s+", "_", ascii_text)
        slug = re.sub(r"[^A-Za-z0-9_-]", "", slug)
        slug = re.sub(r"_+", "_", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("_-")
        return slug.lower() or fallback

    def preserve_id(value: str, fallback: str = "property") -> str:
        """ASCII-safe identifier preserving original casing, used for class/property IRI segments."""
        raw = (value or "").strip()
        if not raw:
            return fallback

        normalized = unicodedata.normalize("NFKD", raw)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"\s+", "_", ascii_text)
        slug = re.sub(r"[^A-Za-z0-9_-]", "", slug)
        slug = re.sub(r"_+", "_", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("_-")
        return slug or fallback

    # Generate a normalized ASCII dataset ID from title
    dataset_title_str = get_text_value(dataset_node.title, 'de')
    dataset_id = slug_id(dataset_title_str, fallback="dataset")

    # Create RDF graph
    g = Graph()

    # Bind namespaces
    i14y_ns = Namespace(f"https://www.i14y.admin.ch/resources/datasets/{dataset_id}/structure/")
    QB = Namespace("http://purl.org/linked-data/cube#")
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)
    g.bind("dcterms", DCTERMS)
    g.bind("sh", SH)
    g.bind("owl", OWL)
    g.bind("QB", QB)
    g.bind("i14y", i14y_ns)

    # Global tracking to prevent duplicate language tags for the same URI and property
    uri_lang_tracker = {}  # Format: {(uri, property, lang): content}
    
    def safe_add_multilingual_property(uri, property_type, content, lang):
        """Safely add a multilingual property, preventing duplicates for same URI+property+lang"""
        if not content or lang not in ['de', 'fr', 'it', 'en']:
            return False
            
        # Sanitize content before using as key
        sanitized_content = sanitize_literal(content)
        key = (str(uri), str(property_type), lang)
        
        if key in uri_lang_tracker:
            # Check if content is the same - if different, log a warning
            existing_content = uri_lang_tracker[key]
            if existing_content != sanitized_content:
                print(f"WARNING: Different content for same URI+property+lang: {key}")
                print(f"  Existing: {existing_content}")
                print(f"  Attempted: {sanitized_content}")
            return False
        
        # Add to graph and track
        g.add((uri, property_type, Literal(sanitized_content, lang=lang)))
        uri_lang_tracker[key] = sanitized_content
        return True
    
    def normalize_concept_uri(uri_str: str) -> str:
        """Normalize any i14y concept URI to the canonical form used in exports.
        Target format: https://www.i14y.admin.ch/en/catalog/concepts/{uuid}
        """
        uuid_match = re.search(
            r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
            uri_str, re.IGNORECASE
        )
        if uuid_match:
            return f"https://www.i14y.admin.ch/en/catalog/concepts/{uuid_match.group(1)}"
        return uri_str

    def safe_add_conforms_to(uri, node):
        """Safely add dcterms:conformsTo if node has concept reference"""
        conforms_to_uri = None
        
        # For data elements, use the conformsTo URI
        if hasattr(node, 'conforms_to_concept_uri') and node.conforms_to_concept_uri:
            conforms_to_uri = node.conforms_to_concept_uri
        # For concepts with I14Y URI, use that
        elif hasattr(node, 'i14y_concept_uri') and node.i14y_concept_uri:
            conforms_to_uri = node.i14y_concept_uri
            
        if conforms_to_uri:
            # Normalize to canonical example format
            conforms_to_uri = normalize_concept_uri(conforms_to_uri)
            # Check if already exists to prevent duplicates
            existing = list(g.triples((uri, DCTERMS.conformsTo, URIRef(conforms_to_uri))))
            if not existing:
                g.add((uri, DCTERMS.conformsTo, URIRef(conforms_to_uri)))
                return True
        return False

    # Helper functions
    def sanitize_literal(text: str) -> str:
        if text is None:
            return ""
        # Collapse whitespace/newlines and escape quotes
        cleaned = " ".join(str(text).split())
        return cleaned.replace('"', '\\"')

    def norm_id(label) -> str:
        """Normalize a label (string or multilingual dict) to a valid ID, preserving original casing."""
        if isinstance(label, dict):
            base = get_text_value(label, 'de')
        else:
            base = (label or "").strip()

        return preserve_id(base, fallback="property")

    def node_export_id(node) -> str:
        """Resolve URI segment from explicit identifier only."""
        identifier = getattr(node, 'identifier', None)
        if isinstance(identifier, dict):
            identifier = get_text_value(identifier, 'de')

        text = str(identifier).strip() if identifier is not None else ""
        if not text:
            node_type = getattr(node, 'type', 'unknown')
            node_title = getattr(node, 'title', '')
            if isinstance(node_title, dict):
                node_title = get_text_value(node_title, 'de')
            raise ValueError(
                f"Missing identifier for node type '{node_type}' with title '{node_title}'. "
                "Identifier is required for URI generation."
            )

        return norm_id(text)

    # Create dataset NodeShape
    dataset_shape = URIRef(f"{i14y_ns}{dataset_id}")
    g.add((dataset_shape, RDF.type, SH.NodeShape))
    g.add((dataset_shape, RDF.type, RDFS.Class))
    QB_dsd = Namespace("http://purl.org/linked-data/cube#")
    g.add((dataset_shape, RDF.type, QB_dsd.DataStructureDefinition))

    # Add dataset metadata with multilingual support
    dataset_titles = dataset_node.get_multilingual_title()
    dataset_descriptions = dataset_node.get_multilingual_description()

    unique_dataset_titles = get_unique_lang_values(dataset_titles, sanitize_literal)
    unique_dataset_descriptions = get_unique_lang_values(dataset_descriptions, sanitize_literal)

    for lang, title in unique_dataset_titles.items():
        sanitized_title = sanitize_literal(title)
        safe_add_multilingual_property(dataset_shape, DCTERMS.title, sanitized_title, lang)
        safe_add_multilingual_property(dataset_shape, RDFS.label, sanitized_title, lang)

    for lang, desc in unique_dataset_descriptions.items():
        sanitized_desc = sanitize_literal(desc)
        safe_add_multilingual_property(dataset_shape, DCTERMS.description, sanitized_desc, lang)
        safe_add_multilingual_property(dataset_shape, RDFS.comment, sanitized_desc, lang)

    # Add version and schema information (following I14Y pattern)
    PAV = Namespace("http://purl.org/pav/")
    SCHEMA = Namespace("https://schema.org/")
    g.bind("pav", PAV)
    g.bind("schema", SCHEMA)
    
    g.add((dataset_shape, PAV.version, Literal("1.0.0")))
    g.add((dataset_shape, SCHEMA.version, Literal("1.0.0")))
    
    # Add current date as validFrom
    current_date = datetime.now().strftime("%Y-%m-%d")
    g.add((dataset_shape, SCHEMA.validFrom, Literal(current_date, datatype=XSD.date)))

    # Collect concepts, classes, and data elements connected to dataset
    connected_concepts = []
    connected_classes = []
    connected_data_elements = []

    for conn_id in dataset_node.connections:
        if conn_id in nodes:
            connected_node = nodes[conn_id]
            if connected_node.type == 'concept':
                connected_concepts.append(connected_node)
            elif connected_node.type == 'class':
                connected_classes.append(connected_node)
            elif connected_node.type == 'data_element':
                connected_data_elements.append(connected_node)

    # First, create all class NodeShapes and collect their properties
    class_properties = {}  # Maps class_id to list of concept property URIs
    rdf_list_counter = 0  # For generating unique RDF list IDs

    for class_node in connected_classes:
        class_id = node_export_id(class_node)
        # Append 'Type' suffix if not already present (case-insensitive check)
        class_type_id = class_id if class_id.lower().endswith("type") else f"{class_id}Type"
        class_uri = URIRef(f"{i14y_ns}{class_type_id}")

        # Create NodeShape for the class
        g.add((class_uri, RDF.type, RDFS.Class))
        g.add((class_uri, RDF.type, SH.NodeShape))
        g.add((class_uri, SH.targetClass, class_uri))

        # Add class metadata with multilingual support
        class_titles = class_node.get_multilingual_title()
        class_descriptions = class_node.get_multilingual_description()

        unique_class_titles = get_unique_lang_values(class_titles, sanitize_literal)
        unique_class_descriptions = get_unique_lang_values(class_descriptions, sanitize_literal)

        for lang, title in unique_class_titles.items():
            sanitized_title = sanitize_literal(title)
            safe_add_multilingual_property(class_uri, SH.name, sanitized_title, lang)

        for lang, desc in unique_class_descriptions.items():
            sanitized_desc = sanitize_literal(desc)
            safe_add_multilingual_property(class_uri, DCTERMS.description, sanitized_desc, lang)
            safe_add_multilingual_property(class_uri, RDFS.comment, sanitized_desc, lang)

        # Collect concepts and data elements connected to this class
        class_concepts = []
        class_data_elements = []
        for conn_id in class_node.connections:
            if conn_id in nodes:
                connected_node = nodes[conn_id]
                if connected_node.type == 'concept':
                    class_concepts.append(connected_node)
                elif connected_node.type == 'data_element':
                    class_data_elements.append(connected_node)

        # Create property shapes for concepts belonging to this class
        class_property_uris = []
        for concept in class_concepts:
            concept_id = node_export_id(concept)
            property_uri = URIRef(f"{i14y_ns}{class_type_id}/{concept_id}")

            # Create PropertyShape
            g.add((property_uri, RDF.type, SH.PropertyShape))
            g.add((property_uri, RDF.type, OWL.DatatypeProperty))
            g.add((property_uri, SH.path, property_uri))
            
            # Fix datatype syntax - use XSD namespace properly
            if concept.datatype:
                if concept.datatype.startswith('xsd:'):
                    datatype_name = concept.datatype.split(':')[1]
                    g.add((property_uri, SH.datatype, getattr(XSD, datatype_name)))
                else:
                    g.add((property_uri, SH.datatype, URIRef(concept.datatype)))
            else:
                g.add((property_uri, SH.datatype, XSD.string))  # Default to string

            # Add I14Y concept reference if available
            safe_add_conforms_to(property_uri, concept)

            # Add advanced SHACL constraints
            if concept.min_count is not None:
                g.add((property_uri, SH.minCount, Literal(concept.min_count, datatype=XSD.integer)))
            if concept.max_count is not None:
                g.add((property_uri, SH.maxCount, Literal(concept.max_count, datatype=XSD.integer)))
            if concept.min_length is not None:
                g.add((property_uri, SH.minLength, Literal(concept.min_length, datatype=XSD.integer)))
            if concept.max_length is not None:
                g.add((property_uri, SH.maxLength, Literal(concept.max_length, datatype=XSD.integer)))
            if concept.pattern:
                g.add((property_uri, SH.pattern, Literal(concept.pattern)))
            if concept.range:
                g.add((property_uri, RDFS.range, URIRef(concept.range)))

            # Add enumeration values (sh:in)
            if concept.in_values:
                # Add QB:CodedProperty for enumerated values
                g.add((property_uri, RDF.type, QB.CodedProperty))
                
                # Create RDF list for enumeration values using proper blank node references
                list_items = []
                for i, value in enumerate(concept.in_values):
                    blank_node = BNode(f"autos{rdf_list_counter}")
                    list_items.append(blank_node)
                    rdf_list_counter += 1
                
                # Build the list from end to beginning
                if list_items:
                    # Set the head for sh:in
                    g.add((property_uri, SH['in'], list_items[0]))
                    
                    # Create the list structure
                    for i, current in enumerate(list_items):
                        g.add((current, RDF.first, Literal(concept.in_values[i])))
                        if i < len(list_items) - 1:
                            g.add((current, RDF.rest, list_items[i + 1]))
                        else:
                            g.add((current, RDF.rest, RDF.nil))

            # Add class reference (sh:node)
            if concept.node_reference:
                g.add((property_uri, SH.node, URIRef(concept.node_reference)))

            # Add multilingual titles and descriptions
            titles = concept.get_multilingual_title()
            descriptions = concept.get_multilingual_description()

            unique_titles = get_unique_lang_values(titles, sanitize_literal)
            unique_descriptions = get_unique_lang_values(descriptions, sanitize_literal)

            for lang, title in unique_titles.items():
                sanitized_title = sanitize_literal(title)
                safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
                safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
                safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

            for lang, desc in unique_descriptions.items():
                sanitized_desc = sanitize_literal(desc)
                safe_add_multilingual_property(property_uri, DCTERMS.description, sanitized_desc, lang)
                safe_add_multilingual_property(property_uri, RDFS.comment, sanitized_desc, lang)
                safe_add_multilingual_property(property_uri, SH.description, sanitized_desc, lang)

            class_property_uris.append(property_uri)

        # Create property shapes for data elements belonging to this class
        # Sort data elements by order field (if set), then by title
        class_data_elements_sorted = sorted(
            class_data_elements,
            key=lambda de: (de.order if de.order is not None else float('inf'), de.title)
        )
        
        for data_element in class_data_elements_sorted:
            element_id = node_export_id(data_element)
            property_uri = URIRef(f"{i14y_ns}{class_type_id}/{element_id}")

            # Create PropertyShape
            g.add((property_uri, RDF.type, SH.PropertyShape))
            g.add((property_uri, RDF.type, OWL.DatatypeProperty))
            g.add((property_uri, SH.path, property_uri))
            
            # Fix datatype syntax - use XSD namespace properly
            if data_element.datatype:
                if data_element.datatype.startswith('xsd:'):
                    datatype_name = data_element.datatype.split(':')[1]
                    g.add((property_uri, SH.datatype, getattr(XSD, datatype_name)))
                else:
                    g.add((property_uri, SH.datatype, URIRef(data_element.datatype)))
            else:
                g.add((property_uri, SH.datatype, XSD.string))  # Default to string

            # Add I14Y concept reference if the data element is linked to a concept
            safe_add_conforms_to(property_uri, data_element)

            # Get cardinality from edge if available
            edge_id = f"{class_node.id}-{data_element.id}"
            min_count = None
            max_count = None
            
            if edges and edge_id in edges:
                cardinality = edges[edge_id].get('cardinality', '1..1')
                min_count, max_count = parse_cardinality(cardinality)
            else:
                # Try reverse edge
                reverse_edge_id = f"{data_element.id}-{class_node.id}"
                if edges and reverse_edge_id in edges:
                    cardinality = edges[reverse_edge_id].get('cardinality', '1..1')
                    min_count, max_count = parse_cardinality(cardinality)
                else:
                    # Fallback to node attributes
                    min_count = data_element.min_count
                    max_count = data_element.max_count
                    
            # Add cardinality constraints
            if min_count is not None:
                g.add((property_uri, SH.minCount, Literal(min_count)))
            else:
                g.add((property_uri, SH.minCount, Literal(1)))  # Default minCount for data elements
                
            if max_count is not None:
                g.add((property_uri, SH.maxCount, Literal(max_count)))
            if data_element.min_length is not None:
                g.add((property_uri, SH.minLength, Literal(data_element.min_length)))
            if data_element.max_length is not None:
                g.add((property_uri, SH.maxLength, Literal(data_element.max_length)))
            if data_element.pattern:
                g.add((property_uri, SH.pattern, Literal(data_element.pattern)))
            if data_element.range:
                g.add((property_uri, RDFS.range, URIRef(data_element.range)))

            # Add enumeration values (sh:in)
            if data_element.in_values:
                # Add QB:CodedProperty for enumerated values
                g.add((property_uri, RDF.type, QB.CodedProperty))
                
                # Create RDF list for enumeration values using proper blank node references
                list_items = []
                for i, value in enumerate(data_element.in_values):
                    blank_node = BNode(f"autos{rdf_list_counter}")
                    list_items.append(blank_node)
                    rdf_list_counter += 1
                
                # Build the list from end to beginning
                if list_items:
                    # Set the head for sh:in
                    g.add((property_uri, SH['in'], list_items[0]))
                    
                    # Create the list structure
                    for i, current in enumerate(list_items):
                        g.add((current, RDF.first, Literal(data_element.in_values[i])))
                        if i < len(list_items) - 1:
                            g.add((current, RDF.rest, list_items[i + 1]))
                        else:
                            g.add((current, RDF.rest, RDF.nil))

            # Add class reference (sh:node)
            if data_element.node_reference:
                g.add((property_uri, SH.node, URIRef(data_element.node_reference)))

            # Add order property (sh:order) for sorting
            if data_element.order is not None:
                g.add((property_uri, SH.order, Literal(data_element.order)))

            # Add multilingual titles and descriptions
            element_titles = data_element.get_multilingual_title()
            element_descriptions = data_element.get_multilingual_description()

            unique_element_titles = get_unique_lang_values(element_titles, sanitize_literal)
            unique_element_descriptions = get_unique_lang_values(element_descriptions, sanitize_literal)

            for lang, title in unique_element_titles.items():
                sanitized_title = sanitize_literal(title)
                safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
                safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
                safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

            for lang, desc in unique_element_descriptions.items():
                sanitized_desc = sanitize_literal(desc)
                safe_add_multilingual_property(property_uri, DCTERMS.description, sanitized_desc, lang)
                safe_add_multilingual_property(property_uri, RDFS.comment, sanitized_desc, lang)
                safe_add_multilingual_property(property_uri, SH.description, sanitized_desc, lang)

            class_property_uris.append(property_uri)

        # Add properties to the class NodeShape
        for property_uri in class_property_uris:
            g.add((class_uri, SH.property, property_uri))

        # Store for dataset reference creation
        class_properties[class_node.id] = class_uri

    # Add property references for concepts directly connected to dataset
    for concept in connected_concepts:
        concept_id = node_export_id(concept)
        property_uri = URIRef(f"{i14y_ns}{dataset_id}/{concept_id}")

        # Create PropertyShape
        g.add((property_uri, RDF.type, SH.PropertyShape))
        g.add((property_uri, RDF.type, OWL.DatatypeProperty))
        g.add((property_uri, RDF.type, QB.AttributeProperty))
        g.add((property_uri, SH.path, property_uri))
        # Fix datatype syntax - use XSD namespace properly
        if concept.datatype:
            if concept.datatype.startswith('xsd:'):
                datatype_name = concept.datatype.split(':')[1]
                g.add((property_uri, SH.datatype, getattr(XSD, datatype_name)))
            else:
                g.add((property_uri, SH.datatype, URIRef(concept.datatype)))
        else:
            g.add((property_uri, SH.datatype, XSD.string))  # Default to string

        # Add I14Y concept reference if available
        safe_add_conforms_to(property_uri, concept)

        # Add advanced SHACL constraints
        if concept.min_count is not None:
            g.add((property_uri, SH.minCount, Literal(concept.min_count)))
        if concept.max_count is not None:
            g.add((property_uri, SH.maxCount, Literal(concept.max_count)))
        if concept.min_length is not None:
            g.add((property_uri, SH.minLength, Literal(concept.min_length)))
        if concept.max_length is not None:
            g.add((property_uri, SH.maxLength, Literal(concept.max_length)))
        if concept.pattern:
            g.add((property_uri, SH.pattern, Literal(concept.pattern)))
        if concept.range:
            g.add((property_uri, RDFS.range, URIRef(concept.range)))

        # Add enumeration values (sh:in)
        if concept.in_values:
            # Add QB:CodedProperty for enumerated values
            g.add((property_uri, RDF.type, QB.CodedProperty))
            
            # Create RDF list for enumeration values using proper blank node references
            list_items = []
            for i, value in enumerate(concept.in_values):
                blank_node = BNode(f"autos{rdf_list_counter}")
                list_items.append(blank_node)
                rdf_list_counter += 1
            
            # Build the list from end to beginning
            if list_items:
                # Set the head for sh:in
                g.add((property_uri, SH['in'], list_items[0]))
                
                # Create the list structure
                for i, current in enumerate(list_items):
                    g.add((current, RDF.first, Literal(concept.in_values[i])))
                    if i < len(list_items) - 1:
                        g.add((current, RDF.rest, list_items[i + 1]))
                    else:
                        g.add((current, RDF.rest, RDF.nil))

        # Add class reference (sh:node)
        if concept.node_reference:
            g.add((property_uri, SH.node, URIRef(concept.node_reference)))

        # Add multilingual titles and descriptions
        titles = concept.get_multilingual_title()
        descriptions = concept.get_multilingual_description()

        unique_titles = get_unique_lang_values(titles, sanitize_literal)
        unique_descriptions = get_unique_lang_values(descriptions, sanitize_literal)

        for lang, title in unique_titles.items():
            sanitized_title = sanitize_literal(title)
            safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
            safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
            safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

        for lang, desc in unique_descriptions.items():
            sanitized_desc = sanitize_literal(desc)
            safe_add_multilingual_property(property_uri, DCTERMS.description, sanitized_desc, lang)
            safe_add_multilingual_property(property_uri, RDFS.comment, sanitized_desc, lang)
            safe_add_multilingual_property(property_uri, SH.description, sanitized_desc, lang)

        # Add to dataset properties
        g.add((dataset_shape, SH.property, property_uri))
    
    # Sort data elements by order field (if set), then by title
    connected_data_elements_sorted = sorted(
        connected_data_elements,
        key=lambda de: (de.order if de.order is not None else float('inf'), de.title)
    )
    
    for data_element in connected_data_elements_sorted:
        element_id = node_export_id(data_element)
        property_uri = URIRef(f"{i14y_ns}{dataset_id}/{element_id}")

        # Create PropertyShape
        g.add((property_uri, RDF.type, SH.PropertyShape))
        g.add((property_uri, RDF.type, OWL.DatatypeProperty))
        g.add((property_uri, SH.path, property_uri))
        
        # Fix datatype syntax - use XSD namespace properly
        if data_element.datatype:
            if data_element.datatype.startswith('xsd:'):
                datatype_name = data_element.datatype.split(':')[1]
                g.add((property_uri, SH.datatype, getattr(XSD, datatype_name)))
            else:
                g.add((property_uri, SH.datatype, URIRef(data_element.datatype)))
        else:
            g.add((property_uri, SH.datatype, XSD.string))  # Default to string

        # Add I14Y concept reference if the data element is linked to a concept
        safe_add_conforms_to(property_uri, data_element)

        # Get cardinality from edge if available
        edge_id = f"{dataset_node.id}-{data_element.id}"
        min_count = None
        max_count = None
        
        if edges and edge_id in edges:
            cardinality = edges[edge_id].get('cardinality', '1..1')
            min_count, max_count = parse_cardinality(cardinality)
        else:
            # Try reverse edge
            reverse_edge_id = f"{data_element.id}-{dataset_node.id}"
            if edges and reverse_edge_id in edges:
                cardinality = edges[reverse_edge_id].get('cardinality', '1..1')
                min_count, max_count = parse_cardinality(cardinality)
            else:
                # Fallback to node attributes
                min_count = data_element.min_count
                max_count = data_element.max_count
                
        # Add cardinality constraints
        if min_count is not None:
            g.add((property_uri, SH.minCount, Literal(min_count)))
        else:
            g.add((property_uri, SH.minCount, Literal(1)))  # Default minCount for data elements
            
        if max_count is not None:
            g.add((property_uri, SH.maxCount, Literal(max_count)))
        if data_element.min_length is not None:
            g.add((property_uri, SH.minLength, Literal(data_element.min_length)))
        if data_element.max_length is not None:
            g.add((property_uri, SH.maxLength, Literal(data_element.max_length)))
        if data_element.pattern:
            g.add((property_uri, SH.pattern, Literal(data_element.pattern)))
        if data_element.range:
            g.add((property_uri, RDFS.range, URIRef(data_element.range)))

        # Add enumeration values (sh:in)
        if data_element.in_values:
            # Add QB:CodedProperty for enumerated values
            g.add((property_uri, RDF.type, QB.CodedProperty))
            
            # Create RDF list for enumeration values using proper blank node references
            list_items = []
            for i, value in enumerate(data_element.in_values):
                blank_node = BNode(f"autos{rdf_list_counter}")
                list_items.append(blank_node)
                rdf_list_counter += 1
            
            # Build the list from end to beginning
            if list_items:
                # Set the head for sh:in
                g.add((property_uri, SH['in'], list_items[0]))
                
                # Create the list structure
                for i, current in enumerate(list_items):
                    g.add((current, RDF.first, Literal(data_element.in_values[i])))
                    if i < len(list_items) - 1:
                        g.add((current, RDF.rest, list_items[i + 1]))
                    else:
                        g.add((current, RDF.rest, RDF.nil))

        # Add class reference (sh:node)
        if data_element.node_reference:
            g.add((property_uri, SH.node, URIRef(data_element.node_reference)))

        # Add order property (sh:order) for sorting
        if data_element.order is not None:
            g.add((property_uri, SH.order, Literal(data_element.order)))

        # Add multilingual titles and descriptions for data elements
        element_titles = data_element.get_multilingual_title()
        element_descriptions = data_element.get_multilingual_description()

        unique_element_titles = get_unique_lang_values(element_titles, sanitize_literal)
        unique_element_descriptions = get_unique_lang_values(element_descriptions, sanitize_literal)

        for lang, title in unique_element_titles.items():
            sanitized_title = sanitize_literal(title)
            safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
            safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
            safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

        for lang, desc in unique_element_descriptions.items():
            sanitized_desc = sanitize_literal(desc)
            safe_add_multilingual_property(property_uri, DCTERMS.description, sanitized_desc, lang)
            safe_add_multilingual_property(property_uri, RDFS.comment, sanitized_desc, lang)
            safe_add_multilingual_property(property_uri, SH.description, sanitized_desc, lang)

        # Add to dataset properties
        g.add((dataset_shape, SH.property, property_uri))
    
    for class_node in connected_classes:
        class_id = node_export_id(class_node)
        class_type_id = class_id if class_id.lower().endswith("type") else f"{class_id}Type"
        class_uri = class_properties[class_node.id]
        # Create a property shape that references the class
        property_uri = URIRef(f"{i14y_ns}{dataset_id}/{class_id}")

        # Create PropertyShape for class
        g.add((property_uri, RDF.type, SH.PropertyShape))
        g.add((property_uri, RDF.type, OWL.ObjectProperty))
        # Object-property path points to the class resource path in i14y namespace.
        g.add((property_uri, SH.path, URIRef(f"{i14y_ns}{class_id}")))

        # Add advanced SHACL constraints for classes
        if class_node.min_count is not None:
            g.add((property_uri, SH.minCount, Literal(class_node.min_count)))
        else:
            # Add default minCount 1 for class references to indicate 1:1 relationship
            g.add((property_uri, SH.minCount, Literal(1)))
            
        if class_node.max_count is not None:
            g.add((property_uri, SH.maxCount, Literal(class_node.max_count)))
        else:
            # Add default maxCount 1 for class references to indicate 1:1 relationship
            g.add((property_uri, SH.maxCount, Literal(1)))

        # Link to the class NodeShape using sh:node (recommended for I14Y)
        g.add((property_uri, SH.node, class_uri))

        # Add multilingual titles and labels for the class property reference
        titles = class_node.get_multilingual_title() if hasattr(class_node, 'get_multilingual_title') else {}
        # fallback: use class_node.title for all languages if no multilingual
        if not titles or not any(titles.values()):
            titles = {lang: class_node.title for lang in ['de', 'fr', 'it', 'en']}
        
        unique_titles = get_unique_lang_values(titles, sanitize_literal)
        for lang, title in unique_titles.items():
            sanitized_title = sanitize_literal(title)
            safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
            safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
            safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

        # Add to dataset properties
        g.add((dataset_shape, SH.property, property_uri))

    # Serialize to TTL format with custom prefixes
    ttl_content = g.serialize(format='turtle', encoding='utf-8').decode('utf-8')

    # Clean up duplicate prefixes and organize the output
    lines = ttl_content.split('\n')
    seen_prefixes = set()
    cleaned_lines = []
    data_lines = []

    for line in lines:
        if line.startswith('@prefix'):
            prefix_name = line.split(':')[0].replace('@prefix ', '')
            if prefix_name not in seen_prefixes:
                seen_prefixes.add(prefix_name)
                cleaned_lines.append(line)
        elif line.strip():
            data_lines.append(line)

    # Add our custom prefixes first
    custom_prefixes = f"""@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>.
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
@prefix xsd: <http://www.w3.org/2001/XMLSchema#>.
@prefix xml: <http://www.w3.org/XML/1998/namespace>.
@prefix QB: <http://purl.org/linked-data/cube#>.
@prefix dcterms: <http://purl.org/dc/terms/>.
@prefix i14y: <https://www.i14y.admin.ch/resources/datasets/{dataset_id}/structure/>.
@prefix owl: <http://www.w3.org/2002/07/owl#>.
@prefix pav: <http://purl.org/pav/>.
@prefix schema: <https://schema.org/>.
@prefix sh: <http://www.w3.org/ns/shacl#>.

"""

    return custom_prefixes + '\n'.join(data_lines) + '\n'


def export_ttl_content(nodes: Dict, base_uri: str, edges: Dict = None) -> str:
    """Wrapper function for generating TTL content
    
    Args:
        nodes: Dictionary of SHACLNode objects keyed by node ID
        base_uri: Base URI for the dataset namespace
        edges: Optional dictionary of edge definitions with cardinality
        
    Returns:
        TTL content as string
    """
    return generate_full_ttl(nodes, base_uri, edges)
