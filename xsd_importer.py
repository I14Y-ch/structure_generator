"""
XSD to SHACL converter for I14Y Data Structure Editor
Adapted from the XSD2SHACL project, originally developed by Xuemin Duan, David Chaves-Fraga, and Anastasia Dimou.
Source: https://github.com/dtai-kg/XSD2SHACL
"""

from lxml import etree
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, XSD, OWL
import io
import os
from typing import Optional

# Define namespaces
SH = Namespace("http://www.w3.org/ns/shacl#")
DCT = Namespace("http://purl.org/dc/terms/")

def parse_xsd_content(xsd_content):
    """Parse XSD content string and return the root element."""
    try:
        parser = etree.XMLParser(resolve_entities=False)
        root = etree.fromstring(xsd_content.encode('utf-8'), parser=parser)
        return root
    except Exception as e:
        print(f"Error parsing XSD content: {e}")
        return None

def handle_enumeration(enumerations, subject, graph):
    """Handle XSD enumeration with sh:in."""
    if not enumerations:
        return
    
    # Create a list node for the enumeration values
    enum_list = BNode()
    current = enum_list
    
    for i, enum_value in enumerate(enumerations):
        graph.add((current, RDF.first, Literal(enum_value)))
        if i < len(enumerations) - 1:
            next_node = BNode()
            graph.add((current, RDF.rest, next_node))
            current = next_node
        else:
            graph.add((current, RDF.rest, RDF.nil))
    
    graph.add((subject, SH["in"], enum_list))

def translate_restriction(facet_name, facet_value, base_type=None, subject=None, graph=None):
    """Translates XSD restrictions to SHACL constraints."""
    # Numeric constraints
    numeric_facets = {
        'minInclusive': SH.minInclusive,
        'maxInclusive': SH.maxInclusive,
        'minExclusive': SH.minExclusive,
        'maxExclusive': SH.maxExclusive,
        'totalDigits': SH.totalDigits,
        'fractionDigits': SH.fractionDigits
    }
    
    # String constraints
    string_facets = {
        'minLength': SH.minLength,
        'maxLength': SH.maxLength,
        'length': (SH.minLength, SH.maxLength),
        'pattern': SH.pattern
    }
    
    # Convert value to appropriate type
    if facet_name in ['minLength', 'maxLength', 'length', 'totalDigits', 'fractionDigits']:
        value = Literal(int(facet_value), datatype=XSD.integer)
    elif facet_name in numeric_facets and base_type:
        value = Literal(facet_value, datatype=XSD[base_type])
    elif facet_name == 'pattern':
        value = Literal(facet_value.replace('\\\\', '\\\\\\\\'))
    else:
        value = Literal(facet_value)
    
    # Determine the predicate(s)
    if facet_name in numeric_facets:
        predicate = numeric_facets[facet_name]
    elif facet_name in string_facets:
        if facet_name == 'length':
            if graph and subject:
                graph.add((subject, SH.minLength, value))
                graph.add((subject, SH.maxLength, value))
                return None
            return (SH.minLength, value), (SH.maxLength, value)
        predicate = string_facets[facet_name]
    else:
        return None
    
    if graph and subject:
        graph.add((subject, predicate, value))
        return None
    return (predicate, value)

def translate_annotation(xsd_element, subject, graph):
    """Converts XSD annotations (documentation/appinfo) to SHACL descriptions."""
    annotations = xsd_element.find('.//{http://www.w3.org/2001/XMLSchema}annotation')
    if annotations is not None:
        # Handle documentation elements (descriptions)
        for doc in annotations.findall('.//{http://www.w3.org/2001/XMLSchema}documentation'):
            lang = doc.get('{http://www.w3.org/XML/1998/namespace}lang', 'en')
            if doc.text and doc.text.strip():
                graph.add((subject, DCT.description, Literal(doc.text.strip(), lang=lang)))
                graph.add((subject, RDFS.comment, Literal(doc.text.strip(), lang=lang)))
                graph.add((subject, SH.description, Literal(doc.text.strip(), lang=lang)))

def process_simple_type(simple_type, xsd_root, graph, type_name=None, I14Y=None):
    """Process a simpleType definition and create NodeShape if it's a global type."""
    restriction = simple_type.find('{http://www.w3.org/2001/XMLSchema}restriction')
    
    # If this is a global simpleType, create a PropertyShape for it
    if type_name and I14Y:
        node_shape = I14Y[type_name]
        graph.add((node_shape, RDF.type, SH.PropertyShape))
        graph.add((node_shape, SH.name, Literal(type_name, lang='en')))
        graph.add((node_shape, RDFS.label, Literal(type_name, lang='en')))
        
        # Add annotation
        translate_annotation(simple_type, node_shape, graph)
    
    facets = {}
    enumerations = []
    
    if restriction is not None:
        base = restriction.get('base')
        
        for facet in restriction:
            facet_name = facet.tag.split('}')[-1]
            facet_value = facet.get('value')
            if facet_value:
                if facet_name == 'enumeration':
                    enumerations.append(facet_value)
                else:
                    facets[facet_name] = facet_value
        
        if type_name and I14Y and base and ('xs:' in base or 'xsd:' in base):
            base_type = base.split(':')[-1]
            graph.add((node_shape, SH.datatype, XSD[base_type]))
            
            # Add facets
            for facet_name, facet_value in facets.items():
                translate_restriction(facet_name, facet_value, base_type, node_shape, graph)
            
            # Add enumeration
            if enumerations:
                handle_enumeration(enumerations, node_shape, graph)
        
        return ('simple', base.split(':')[-1] if base and ('xs:' in base or 'xsd:' in base) else 'string', {
            'facets': facets,
            'enumerations': enumerations
        })
    
    return ('simple', 'string', {})

def handle_sequence(sequence, xsd_root, graph, parent_shape, parent_type_name, I14Y, type_map=None):
    """Handle XSD sequence with order constraints."""
    if sequence is None:
        return
    
    # Keep XSD sequence position so UI display order and SHACL export remain stable.
    order = 1
    for element in sequence.findall('{http://www.w3.org/2001/XMLSchema}element'):
        element_name = element.get('name')
        if element_name:
            # Create unique property shape URI based on parent type and element name
            prop_shape = I14Y[f"{parent_type_name}/{element_name}"]
            graph.add((prop_shape, RDF.type, SH.PropertyShape))
            graph.add((prop_shape, SH.path, I14Y[f"{parent_type_name}/{element_name}"]))
            graph.add((prop_shape, SH.name, Literal(element_name, lang='en')))
            
            # Process element details
            process_element_details(element, xsd_root, graph, prop_shape, I14Y, type_map)
            graph.add((prop_shape, SH.order, Literal(order, datatype=XSD.integer)))
            
            graph.add((parent_shape, SH.property, prop_shape))
            order += 1

def handle_attribute(attribute, xsd_root, graph, parent_shape=None, parent_type_name=None, I14Y=None):
    """Handles XSD attribute definitions by creating PropertyShapes."""
    attr_name = attribute.get('name') or attribute.get('ref')
    if not attr_name or not I14Y:
        return None
    
    # Handle attribute references (ref="...")
    if attribute.get('ref'):
        attr_name = attribute.get('ref').split(':')[-1]
        # Look up the attribute definition
        attribute = xsd_root.find(f'.//{{http://www.w3.org/2001/XMLSchema}}attribute[@name="{attr_name}"]')
        if not attribute:
            return None
    
    # Create a PropertyShape for the attribute
    path_suffix = f"{parent_type_name}/{attr_name}" if parent_type_name else attr_name
    attr_shape = I14Y[path_suffix]
    graph.add((attr_shape, RDF.type, SH.PropertyShape))
    graph.add((attr_shape, RDF.type, OWL.DatatypeProperty))
    graph.add((attr_shape, SH.path, I14Y[path_suffix]))
    graph.add((attr_shape, SH.name, Literal(attr_name, lang='en')))
    
    # Handle attribute type
    attr_type = attribute.get('type')
    if attr_type:
        if 'xs:' in attr_type or 'xsd:' in attr_type:
            # Built-in type
            datatype = attr_type.split(':')[-1]
            graph.add((attr_shape, SH.datatype, XSD[datatype]))
            graph.add((attr_shape, RDFS.range, XSD[datatype]))
    
    # Handle use (required/optional)
    use = attribute.get('use', 'optional')
    if use == 'required':
        graph.add((attr_shape, SH.minCount, Literal(1, datatype=XSD.integer)))
    else:
        graph.add((attr_shape, SH.minCount, Literal(0, datatype=XSD.integer)))
    
    # Handle default and fixed values
    if attribute.get('default'):
        graph.add((attr_shape, SH.defaultValue, Literal(attribute.get('default'))))
    if attribute.get('fixed'):
        graph.add((attr_shape, SH.hasValue, Literal(attribute.get('fixed'))))
    
    # Handle annotations
    translate_annotation(attribute, attr_shape, graph)
    
    # If we have a parent shape, link the attribute to it
    if parent_shape:
        graph.add((parent_shape, SH.property, attr_shape))
    
    return attr_shape

def _apply_simple_type_constraints(type_info, prop_shape, graph):
    """Apply constraints extracted from process_simple_type() onto a PropertyShape."""
    if type_info[0] != 'simple':
        return
    base_type = type_info[1]
    graph.add((prop_shape, SH.datatype, XSD[base_type]))
    graph.add((prop_shape, RDF.type, OWL.DatatypeProperty))
    graph.add((prop_shape, RDFS.range, XSD[base_type]))
    for facet_name, facet_value in type_info[2].get('facets', {}).items():
        translate_restriction(facet_name, facet_value, base_type, prop_shape, graph)
    if type_info[2].get('enumerations'):
        handle_enumeration(type_info[2]['enumerations'], prop_shape, graph)


def process_element_details(element, xsd_root, graph, prop_shape, I14Y, type_map=None):
    """Process element details and add to property shape."""
    translate_annotation(element, prop_shape, graph)

    ns = '{http://www.w3.org/2001/XMLSchema}'
    element_type = element.get('type')
    if element_type:
        if 'xs:' in element_type or 'xsd:' in element_type:
            # Built-in type
            base_type = element_type.split(':')[-1]
            graph.add((prop_shape, SH.datatype, XSD[base_type]))
            graph.add((prop_shape, RDF.type, OWL.DatatypeProperty))
            graph.add((prop_shape, RDFS.range, XSD[base_type]))
        else:
            # Named custom type - distinguish simpleType (inline constraints) vs complexType (sh:node)
            type_name = element_type.split(':')[-1]
            simple_type_def = xsd_root.find(f'.//{ns}simpleType[@name="{type_name}"]')
            if simple_type_def is not None:
                # Named simpleType: inline the datatype and all facets directly
                type_info = process_simple_type(simple_type_def, xsd_root, graph, None, None)
                _apply_simple_type_constraints(type_info, prop_shape, graph)
            else:
                # Complex type: use sh:node reference with element-name identifier
                identifier = (type_map or {}).get(type_name, type_name)
                graph.add((prop_shape, SH['node'], I14Y[identifier]))
                graph.add((prop_shape, RDF.type, OWL.ObjectProperty))
    else:
        # No type attribute - check for inline type definitions
        inline_simple = element.find(f'{ns}simpleType')
        inline_complex = element.find(f'{ns}complexType')

        if inline_simple is not None:
            # Inline simpleType: extract restriction and apply constraints
            type_info = process_simple_type(inline_simple, xsd_root, graph, None, None)
            _apply_simple_type_constraints(type_info, prop_shape, graph)
        elif inline_complex is not None:
            # Inline complexType: process its content into this shape directly
            element_name = element.get('name', 'anonymous')
            process_complex_type_content(inline_complex, xsd_root, graph, prop_shape, element_name, I14Y, type_map)

    # Handle minOccurs and maxOccurs
    min_occurs = element.get('minOccurs', '1')
    max_occurs = element.get('maxOccurs', '1')

    graph.add((prop_shape, SH.minCount, Literal(int(min_occurs), datatype=XSD.integer)))
    if max_occurs != "unbounded":
        graph.add((prop_shape, SH.maxCount, Literal(int(max_occurs), datatype=XSD.integer)))

def process_complex_type_content(complex_type, xsd_root, graph, node_shape, type_name, I14Y, type_map=None):
    """Process the content of a complex type."""
    # Handle simple content
    simple_content = complex_type.find('{http://www.w3.org/2001/XMLSchema}simpleContent')
    if simple_content is not None:
        extension = simple_content.find('{http://www.w3.org/2001/XMLSchema}extension')
        restriction = simple_content.find('{http://www.w3.org/2001/XMLSchema}restriction')
        
        if extension is not None:
            base = extension.get('base')
            if base and ('xs:' in base or 'xsd:' in base):
                base_type = base.split(':')[-1]
                graph.add((node_shape, SH.datatype, XSD[base_type]))
            
            # Process attributes
            for attr in extension.findall('{http://www.w3.org/2001/XMLSchema}attribute'):
                handle_attribute(attr, xsd_root, graph, node_shape, type_name, I14Y)
        
        elif restriction is not None:
            base = restriction.get('base')
            if base and ('xs:' in base or 'xsd:' in base):
                base_type = base.split(':')[-1]
                graph.add((node_shape, SH.datatype, XSD[base_type]))
                
                # Process restriction facets
                for facet in restriction:
                    facet_name = facet.tag.split('}')[-1]
                    facet_value = facet.get('value')
                    if facet_value:
                        translate_restriction(facet_name, facet_value, base_type, node_shape, graph)
    
    # Process content model (sequence, choice, all)
    sequence = complex_type.find('{http://www.w3.org/2001/XMLSchema}sequence')
    
    if sequence is not None:
        handle_sequence(sequence, xsd_root, graph, node_shape, type_name, I14Y, type_map)
    
    # Process attributes
    for attr in complex_type.findall('{http://www.w3.org/2001/XMLSchema}attribute'):
        handle_attribute(attr, xsd_root, graph, node_shape, type_name, I14Y)
    
    graph.add((node_shape, SH.closed, Literal(True)))

def _element_has_complex_type(element, xsd_root):
    """Return True if element resolves to a complex type, False if simple/built-in."""
    element_type = element.get('type')
    if element_type:
        if 'xs:' in element_type or 'xsd:' in element_type:
            return False  # Built-in XSD type → simple
        # Named type reference – look it up
        type_name = element_type.split(':')[-1]
        ns = '{http://www.w3.org/2001/XMLSchema}'
        if xsd_root.find(f'.//{ns}complexType[@name="{type_name}"]') is not None:
            return True
        return False  # simpleType reference → simple
    # Inline type
    if element.find('{http://www.w3.org/2001/XMLSchema}complexType') is not None:
        return True
    return False


def process_global_element(element, xsd_root, graph, I14Y, type_map=None):
    """Process a global element definition.

    A class (complex type) becomes sh:NodeShape.
    A data element (simple / built-in type) becomes sh:PropertyShape.
    The identifier is always the xs:element name attribute.
    """
    element_name = element.get('name')
    if not element_name:
        return

    is_class = _element_has_complex_type(element, xsd_root)
    node_shape = I14Y[element_name]

    if is_class:
        graph.add((node_shape, RDF.type, SH.NodeShape))
        graph.add((node_shape, RDF.type, RDFS.Class))
    else:
        graph.add((node_shape, RDF.type, SH.PropertyShape))
        graph.add((node_shape, SH.path, node_shape))

    graph.add((node_shape, SH.name, Literal(element_name, lang='en')))
    graph.add((node_shape, RDFS.label, Literal(element_name, lang='en')))

    # Add annotation
    translate_annotation(element, node_shape, graph)

    # Process type
    element_type = element.get('type')
    if element_type:
        if 'xs:' in element_type or 'xsd:' in element_type:
            # Built-in type → data element
            base_type = element_type.split(':')[-1]
            graph.add((node_shape, SH.datatype, XSD[base_type]))
            graph.add((node_shape, RDF.type, OWL.DatatypeProperty))
            graph.add((node_shape, RDFS.range, XSD[base_type]))
        else:
            # Named type reference
            type_name = element_type.split(':')[-1]
            if is_class:
                graph.add((node_shape, SH['node'], I14Y[type_name]))
            else:
                graph.add((node_shape, SH.datatype, I14Y[type_name]))
    else:
        # Check for inline type definition
        simple_type = element.find('{http://www.w3.org/2001/XMLSchema}simpleType')
        complex_type = element.find('{http://www.w3.org/2001/XMLSchema}complexType')

        if simple_type is not None:
            type_info = process_simple_type(simple_type, xsd_root, graph, None, None)
            if type_info[0] == 'simple':
                graph.add((node_shape, SH.datatype, XSD[type_info[1]]))
                for facet_name, facet_value in type_info[2].get('facets', {}).items():
                    translate_restriction(facet_name, facet_value, type_info[1], node_shape, graph)
                if type_info[2].get('enumerations'):
                    handle_enumeration(type_info[2]['enumerations'], node_shape, graph)

        elif complex_type is not None:
            process_complex_type_content(complex_type, xsd_root, graph, node_shape, element_name, I14Y, type_map)

    # Handle default and fixed values
    if element.get('default'):
        graph.add((node_shape, SH.defaultValue, Literal(element.get('default'))))
    if element.get('fixed'):
        graph.add((node_shape, SH.hasValue, Literal(element.get('fixed'))))

def build_type_to_element_map(xsd_root):
    """Build a mapping from xs:complexType name → xs:element name.

    When multiple elements reference the same complex type, the first occurrence wins.
    This ensures NodeShape identifiers use the xs:element name, not the xs:complexType name.
    """
    ns = '{http://www.w3.org/2001/XMLSchema}'
    type_map = {}
    for element in xsd_root.iter(f'{ns}element'):
        elem_name = element.get('name')
        elem_type = element.get('type')
        if elem_name and elem_type:
            local_type = elem_type.split(':')[-1]
            if local_type not in type_map:
                if xsd_root.find(f'.//{ns}complexType[@name="{local_type}"]') is not None:
                    type_map[local_type] = elem_name
    return type_map


def generate_shacl(xsd_root, dataset_identifier):
    """Generate comprehensive SHACL shapes from the XSD schema."""
    g = Graph()
    
    # Define I14Y namespace based on dataset identifier - URL encode the dataset identifier to avoid invalid URIs
    import urllib.parse
    encoded_dataset_identifier = urllib.parse.quote(dataset_identifier)
    i14y_base_path = f"https://www.i14y.admin.ch/resources/datasets/{encoded_dataset_identifier}/structure/"
    I14Y = Namespace(i14y_base_path)
    
    # Bind namespaces
    g.bind("sh", SH)
    g.bind("i14y", I14Y)
    g.bind("dct", DCT)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    
    # Build mapping from xs:complexType name → xs:element name (identifier rule)
    type_map = build_type_to_element_map(xsd_root)
    
    # Process global simple types
    for simple_type in xsd_root.findall('.//{http://www.w3.org/2001/XMLSchema}simpleType'):
        type_name = simple_type.get('name')
        if type_name:  # Only process global simple types
            process_simple_type(simple_type, xsd_root, g, type_name, I14Y)
    
    # Process global complex types
    for complex_type in xsd_root.findall('.//{http://www.w3.org/2001/XMLSchema}complexType'):
        type_name = complex_type.get('name')
        if type_name:  # Only process global complex types
            # Use the xs:element name as identifier if an element references this type
            identifier = type_map.get(type_name, type_name)
            node_shape = I14Y[identifier]
            g.add((node_shape, RDF.type, SH.NodeShape))
            g.add((node_shape, RDF.type, RDFS.Class))
            g.add((node_shape, SH.name, Literal(identifier, lang='en')))
            g.add((node_shape, RDFS.label, Literal(identifier, lang='en')))
            
            # Add annotation
            translate_annotation(complex_type, node_shape, g)
            
            # Process complex type content (property paths use the identifier too)
            process_complex_type_content(complex_type, xsd_root, g, node_shape, identifier, I14Y, type_map)
    
    # Process global elements
    for element in xsd_root.findall('.//{http://www.w3.org/2001/XMLSchema}element'):
        # Only process top-level elements (direct children of schema)
        if element.getparent().tag != '{http://www.w3.org/2001/XMLSchema}schema':
            continue
        # Skip document-root wrapper elements that have an inline xs:complexType
        # but no type= attribute — these are container/wrapper shapes (e.g. "nomenclature"),
        # not meaningful data classes. Named complex types are already handled above.
        if (element.get('type') is None and
                element.find('{http://www.w3.org/2001/XMLSchema}complexType') is not None):
            continue
        process_global_element(element, xsd_root, g, I14Y, type_map)
    
    return g

def xsd_to_ttl(xsd_content: str, dataset_identifier: str = "dataset_identifier") -> Optional[str]:
    """
    Convert XSD content to TTL format.
    
    Args:
        xsd_content (str): The XSD content as a string
        dataset_identifier (str): The dataset identifier for namespace generation
        
    Returns:
        str: TTL content or None if conversion failed
    """
    try:
        # Parse XSD content
        xsd_root = parse_xsd_content(xsd_content)
        if not xsd_root:
            return None
        
        # Generate SHACL graph
        shacl_graph = generate_shacl(xsd_root, dataset_identifier)
        
        # Serialize to TTL string
        ttl_content = shacl_graph.serialize(format='turtle')
        if isinstance(ttl_content, bytes):
            ttl_content = ttl_content.decode('utf-8')
        
        return ttl_content
    except Exception as e:
        print(f"Error converting XSD to TTL: {e}")
        import traceback
        print(traceback.format_exc())
        return None
