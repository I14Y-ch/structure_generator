"""
CSV to SHACL Converter for I14Y Data Structure Editor
Based on https://github.com/I14Y-ch/shacl_importer_scripts/blob/main/csv_importer/src/csv2shacl.py
"""

import csv
import io
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD, SH, OWL, RDFS

class CSVToSHACL:
    """Enhanced CSV to SHACL transformer with better year detection and numeric constraints."""
    
    YEAR_KEYWORDS = {
        'en': ['year', 'yr'],
        'de': ['jahr', 'jahrgang'],
        'fr': ['année', 'an'],
        'it': ['anno', 'annata']
    }
    
    def __init__(self, base_uri, default_lang: str = None):
        self.g = Graph()
        self.base_uri = base_uri.rstrip('/') + '/'
        self.default_lang = default_lang

        # Namespaces
        self.SH = Namespace("http://www.w3.org/ns/shacl#")
        self.QB = Namespace("http://purl.org/linked-data/cube#")
        self.DCTERMS = Namespace("http://purl.org/dc/terms/")
        self.schema = Namespace("https://schema.org/")
        self.pav = Namespace("http://purl.org/pav/")
        self.rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
        self.OWL = Namespace("http://www.w3.org/2002/07/owl#")
        self.SUG = Namespace("https://www.i14y.admin.ch/vocab#")

        # Bind namespaces
        self.g.bind("sh", self.SH)
        self.g.bind("QB", self.QB)
        self.g.bind("dcterms", self.DCTERMS)
        self.g.bind("schema", self.schema)
        self.g.bind("pav", self.pav)
        self.g.bind("rdfs", self.rdfs)
        self.g.bind("owl", self.OWL)
        self.g.bind("i14y", self.SUG)

    def _generate_regex_for_values(self, values: List[str]) -> Optional[str]:
        """Generate a simple regex pattern describing the column values."""
        cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
        if not cleaned:
            return None

        if all(self._is_valid_date(v) for v in cleaned):
            return r"\d{4}-\d{2}-\d{2}"

        if all(re.fullmatch(r"[+-]?\d+", v) for v in cleaned):
            lengths = {len(v.lstrip('+-')) for v in cleaned}
            if lengths == {1} and all(not v.startswith(('+', '-')) for v in cleaned):
                return r"\d"
            if len(lengths) == 1:
                return rf"\d{{{next(iter(lengths))}}}"
            return r"\d+"

        if all(re.fullmatch(r"[+-]?\d+[\.,]\d+", v) for v in cleaned):
            return r"\d+(?:[\.,]\d+)"

        if all(re.fullmatch(r"[A-Z]+", v) for v in cleaned):
            return r"[A-Z]+"
        if all(re.fullmatch(r"[a-z]+", v) for v in cleaned):
            return r"[a-z]+"
        if all(re.fullmatch(r"[A-Za-z]+", v) for v in cleaned):
            return r"[A-Za-z]+"

        length_set = {len(v) for v in cleaned}
        if len(length_set) == 1:
            length = next(iter(length_set))
            tokens = []
            for idx in range(length):
                chars = {v[idx] for v in cleaned}
                if all(ch.isdigit() for ch in chars):
                    token = r"\d"
                elif all(ch.isalpha() and ch.isupper() for ch in chars):
                    token = r"[A-Z]"
                elif all(ch.isalpha() and ch.islower() for ch in chars):
                    token = r"[a-z]"
                elif all(ch.isalpha() for ch in chars):
                    token = r"[A-Za-z]"
                elif all(ch.isalnum() for ch in chars):
                    token = r"[A-Za-z0-9]"
                elif len(chars) == 1:
                    token = re.escape(next(iter(chars)))
                else:
                    escaped = ''.join(sorted(re.escape(ch) for ch in chars))
                    token = f"[{escaped}]"
                tokens.append(token)

            compressed = []
            last = None
            count = 0
            for token in tokens + [None]:
                if token == last:
                    count += 1
                    continue
                if last is not None:
                    compressed.append(last if count == 1 else f"{last}{{{count}}}")
                last = token
                count = 1
            return ''.join(compressed)

        unique_values = sorted(set(cleaned))
        if len(unique_values) <= 5:
            escaped = [re.escape(v) for v in unique_values]
            return "(?:" + "|".join(escaped) + ")"

        return None

    def _detect_enumeration_values(self, values: List[str]) -> Optional[List[str]]:
        """Detect enumeration values if same values appear at least 5 times."""
        cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
        if not cleaned:
            return None
        
        # Count occurrences of each value
        value_counts = {}
        for v in cleaned:
            value_counts[v] = value_counts.get(v, 0) + 1
        
        # Filter values that appear at least 5 times
        frequent_values = [v for v, count in value_counts.items() if count >= 5]
        
        # Return sorted list if we found any frequent values
        if frequent_values:
            return sorted(frequent_values)
        
        return None

    def _detect_length_constraints(self, values: List[str]) -> tuple[Optional[int], Optional[int]]:
        """Detect min and max length from column values."""
        cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
        if not cleaned:
            return None, None
        
        lengths = [len(v) for v in cleaned]
        return min(lengths), max(lengths)

    def _is_year_column(self, column_name: str) -> bool:
        """Check if column name suggests it contains years."""
        lower_name = column_name.lower()
        for keywords in self.YEAR_KEYWORDS.values():
            if any(keyword in lower_name for keyword in keywords):
                return True
        return False
    
    def _guess_property_type(self, values: List[str], column_name: str) -> URIRef:
        """Guess the data type based on the column values."""
        if not values:
            return XSD.string
            
        sample = values[0].strip() if values[0] else ""

        # Check for year columns first
        if self._is_year_column(column_name):
            if (len(sample) == 4 and sample.isdigit()) or self._is_valid_date(sample):
                return XSD.date
            
        # Check for integers
        if all(v.strip().isdigit() for v in values if v.strip()):
            return XSD.integer
            
        # Check for decimals
        decimal_count = 0
        for v in values:
            if v.strip():
                try:
                    float(v)
                    decimal_count += 1
                except ValueError:
                    pass
        if decimal_count == len([v for v in values if v.strip()]):
            return XSD.decimal
            
        # Check for booleans
        bool_values = {'true', 'false', 't', 'f', 'yes', 'no', '1', '0'}
        if all(v.strip().lower() in bool_values for v in values if v.strip()):
            return XSD.boolean
            
        # Check for dates
        if all(self._is_valid_date(v.strip()) for v in values if v.strip()):
            return XSD.date
            
        # Default to string
        return XSD.string
    
    @staticmethod
    def _is_valid_date(value: str) -> bool:
        """Check if the value is a valid date in YYYY-MM-DD format."""
        parts = value.split('-')
        return (len(parts) == 3 and 
                len(parts[0]) == 4 and 
                parts[0].isdigit() and
                parts[1].isdigit() and 
                parts[2].isdigit())
    
    def _add_numeric_constraints(self, prop_uri: URIRef, values: List[str], datatype: URIRef):
        """Add min/max constraints for numeric fields."""
        numeric_values = []
        for v in values:
            if v.strip():
                try:
                    num_val = float(v)
                    if datatype == XSD.integer and num_val.is_integer():
                        numeric_values.append(int(num_val))
                    else:
                        numeric_values.append(num_val)
                except ValueError:
                    continue
        
        if numeric_values:
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            
            self.g.add((prop_uri, SH.minInclusive, Literal(min_val, datatype=datatype)))
            self.g.add((prop_uri, SH.maxInclusive, Literal(max_val, datatype=datatype)))
    
    def _add_property_shape(self, node_shape: URIRef, property_name: str, property_type: URIRef, values: List[str], order: int, suggested_pattern: Optional[str], suggested_in_values: Optional[List[str]] = None, suggested_min_length: Optional[int] = None, suggested_max_length: Optional[int] = None) -> None:
        """Add a property shape to the graph."""
        safe_name = property_name.replace(' ', '_').replace('.', '_')
        prop_uri = URIRef(f"{node_shape}/{safe_name}")
        
        self.g.add((prop_uri, RDF.type, SH.PropertyShape))
        self.g.add((prop_uri, RDF.type, OWL.DatatypeProperty))
        self.g.add((prop_uri, SH.path, prop_uri))
        self.g.add((prop_uri, SH.datatype, property_type))  
        self.g.add((prop_uri, SH.order, Literal(order, datatype=XSD.integer)))
        if suggested_pattern:
            self.g.add((prop_uri, self.SUG.suggestedPattern, Literal(suggested_pattern)))
        if suggested_in_values:
            # Store as JSON array string for easy parsing
            import json
            self.g.add((prop_uri, self.SUG.suggestedInValues, Literal(json.dumps(suggested_in_values))))
        if suggested_min_length is not None:
            self.g.add((prop_uri, self.SUG.suggestedMinLength, Literal(suggested_min_length, datatype=XSD.integer)))
        if suggested_max_length is not None:
            self.g.add((prop_uri, self.SUG.suggestedMaxLength, Literal(suggested_max_length, datatype=XSD.integer)))
        
        if self.default_lang:
            self.g.add((prop_uri, SH.name, Literal(property_name, lang=self.default_lang)))
            self.g.add((prop_uri, RDFS.label, Literal(property_name, lang=self.default_lang)))
        else:
            self.g.add((prop_uri, SH.name, Literal(property_name)))
            self.g.add((prop_uri, RDFS.label, Literal(property_name)))
        
        if property_type in (XSD.integer, XSD.decimal):
            self._add_numeric_constraints(prop_uri, values, property_type)
        
        self.g.add((node_shape, SH.property, prop_uri))
    
    def transform_csv_to_shacl(self, 
                              csv_data: str, 
                              node_shape_name: Optional[str] = None, 
                              shape_identifier: Optional[str] = None,
                              delimiter: Optional[str] = None,
                              filename: Optional[str] = "imported_data") -> bool:
        """
        Transform CSV data to SHACL.
        
        Args:
            csv_data: CSV content as string
            node_shape_name: Name for the node shape
            shape_identifier: Identifier for the shape URI
            delimiter: CSV delimiter character
            filename: Original filename for fallback naming
        
        Returns:
            bool: Success status
        """
        try:
            # Use StringIO to work with the CSV data in memory
            f = io.StringIO(csv_data)
            
            # Read first line to detect delimiter
            first_line = f.readline()
            f.seek(0)
            
            # Use specified delimiter or auto-detect
            used_delimiter = delimiter if delimiter else (';' if ';' in first_line else ',')
            
            reader = csv.DictReader(f, delimiter=used_delimiter)
            rows = list(reader)
            
            if not rows:
                print("CSV data is empty")
                return False
            
            # Use provided shape name, or extract from filename, or use default
            shape_name = node_shape_name or Path(filename).stem
            shape_uri = URIRef(f"{self.base_uri}{shape_identifier or shape_name}")
            
            # Add node shape
            self.g.add((shape_uri, RDF.type, SH.NodeShape))
            self.g.add((shape_uri, RDF.type, self.rdfs.Class))
            self.g.add((shape_uri, SH.closed, Literal(True)))
            
            if self.default_lang:
                self.g.add((shape_uri, SH.name, Literal(shape_name, lang=self.default_lang)))
                self.g.add((shape_uri, self.rdfs.label, Literal(shape_name, lang=self.default_lang)))
            else:
                self.g.add((shape_uri, SH.name, Literal(shape_name)))
                self.g.add((shape_uri, self.rdfs.label, Literal(shape_name)))
            
            # Add property shapes for each column
            for index, column in enumerate(reader.fieldnames, start=0):
                clean_col = column.strip('\ufeff')
                values = [row[clean_col] for row in rows if clean_col in row and row[clean_col]]
                prop_type = self._guess_property_type(values, clean_col)
                suggested_pattern = self._generate_regex_for_values(values)
                suggested_in_values = self._detect_enumeration_values(values)
                suggested_min_length, suggested_max_length = self._detect_length_constraints(values)
                self._add_property_shape(shape_uri, clean_col, prop_type, values, index * 10, suggested_pattern, suggested_in_values, suggested_min_length, suggested_max_length)
            
            return True
        
        except Exception as e:
            print(f"Error processing CSV: {e}")
            return False
    
    def get_ttl(self) -> str:
        """Get the TTL content as a string."""
        return self.g.serialize(format='turtle')

def csv_to_ttl(csv_data: str, dataset_name: str, default_lang: str = "de") -> Optional[str]:
    """
    Convert CSV data to TTL.
    
    Args:
        csv_data: CSV content as string
        dataset_name: Name for the dataset
        default_lang: Default language for labels
    
    Returns:
        str: TTL content or None if conversion failed
    """
    # Create safe dataset identifier
    dataset_identifier = dataset_name.replace(' ', '_').replace('-', '_')
    
    # Base URI for I14Y
    base_uri = f"https://www.i14y.admin.ch/resources/datasets/{dataset_identifier}/structure/"
    
    # Create transformer
    transformer = CSVToSHACL(base_uri, default_lang=default_lang)
    
    # Transform CSV to SHACL
    if transformer.transform_csv_to_shacl(csv_data, node_shape_name=dataset_name, shape_identifier=dataset_identifier):
        return transformer.get_ttl()
    
    return None
