#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify, send_file, redirect
import json
import os
import tempfile
import requests
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import csv
import io
from pathlib import Path
from rdflib import Graph, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, XSD, SH, OWL, RDFS, DCTERMS

# Import CSV converter 
from csv_converter import csv_to_ttl

class I14YAPIClient:
    """Client for interacting with I14Y API"""
    
    def __init__(self):
        self.base_url = "https://input.i14y.admin.ch/api/Catalog"
        
    def search_concepts(self, query='', page=1, page_size=20):
        """Search for concepts using the I14Y API
        
        Args:
            query: Search query string
            page: Page number (1-based) - Note: new endpoint doesn't use pagination
            page_size: Number of results per page - Note: new endpoint doesn't use pagination
            
        Returns:
            List of concept dictionaries
        """
        print(f"I14Y client searching for concepts with query: '{query}'")
        
        # Ensure page and page_size are integers with defaults
        if page is None:
            page = 1
        if page_size is None:
            page_size = 20
            
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        
        url = f"{self.base_url}/search"
        params = {
            'types': 'Concept'
        }
        
        if query.strip():
            params['query'] = query.strip()
        
        print(f"Making request to {url} with params: {params}")
        
        try:
            response = requests.get(url, params=params, timeout=10)
            print(f"API response status code: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            print(f"API response type: {type(data)}")
            print(f"API response content: {str(data)[:500]}...")
            
            # The new endpoint returns a list directly, not wrapped in a 'data' field
            if isinstance(data, list):
                print(f"Raw data contains {len(data)} items")
                # Apply manual pagination since the endpoint doesn't support it
                start = (page - 1) * page_size
                end = start + page_size
                result = data[start:end]
                print(f"Returning {len(result)} results after pagination")
                return result
                
            print("Data is not a list, returning empty list")
            return []
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return []
        except ValueError as e:
            print(f"JSON decode failed: {e}")
            return []
    
    def get_concept_details(self, concept_id: str) -> Optional[Dict]:
        """Get detailed information about a specific concept"""
        # Use the public API endpoint instead of the input API
        url = f"https://api.i14y.admin.ch/api/public/v1/concepts/{concept_id}"
        print(f"Fetching concept details from: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            print(f"API response status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Received valid concept data with keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
                
                # Handle the case where the API returns data wrapped in a 'data' key
                if isinstance(data, dict) and 'data' in data:
                    print("Extracting concept from 'data' field")
                    concept_data = data['data']
                    print(f"Extracted concept data with keys: {concept_data.keys() if isinstance(concept_data, dict) else 'not a dict'}")
                    
                    # Log the title-related fields for debugging
                    title_fields = ['title', 'name', 'label', 'identifier', 'identifiers']
                    for field in title_fields:
                        if field in concept_data:
                            print(f"Found {field}: {concept_data[field]}")
                    
                    return concept_data
                else:
                    # Return data directly if it's not wrapped
                    print(f"Data not wrapped, using direct response with keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
                    
                    # Log the title-related fields for debugging
                    title_fields = ['title', 'name', 'label', 'identifier', 'identifiers']
                    for field in title_fields:
                        if field in data:
                            print(f"Found {field}: {data[field]}")
                    
                    return data
            elif response.status_code == 404:
                print(f"Concept not found: {concept_id}")
                return None
            else:
                print(f"API returned unexpected status code: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error response: {error_data}")
                except:
                    print(f"Could not parse error response: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"Error getting concept details: {e}")
            return None
    
    def get_codelist_entries(self, concept_id: str) -> Optional[List[Dict]]:
        """Get codelist entries for a concept if it has a codelist"""
        try:
            # Use the public API endpoint for codelist entries
            url = f"https://api.i14y.admin.ch/api/public/v1/concepts/{concept_id}/codelist-entries/exports/json"
            print(f"Fetching codelist from: {url}")
            response = requests.get(url, timeout=10)
            print(f"Codelist response status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                # The API returns a file download, so we need to parse the content as JSON
                try:
                    # Try to parse the response content as JSON
                    data = response.json()
                    print(f"Successfully parsed JSON data")
                    print(f"Data structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Handle different possible response structures
                    entries = None
                    if isinstance(data, dict):
                        entries = data.get('entries') or data.get('items') or data.get('data') or data.get('codelistEntries')
                        # If no nested structure, check if the root object contains entries directly
                        if not entries and 'code' in str(data) or 'value' in str(data):
                            # Check if data itself contains entry-like structures
                            if all(isinstance(v, (dict, str, int)) for v in data.values()):
                                entries = [data] if any(k in data for k in ['code', 'value', 'identifier']) else None
                    elif isinstance(data, list):
                        entries = data
                    
                    if entries:
                        print(f"Found {len(entries)} codelist entries")
                        if len(entries) > 0:
                            print(f"First entry: {entries[0]}")
                    else:
                        print("No entries found in codelist response")
                        print(f"Full response: {str(data)[:500]}")
                    
                    return entries
                except ValueError as e:
                    print(f"Failed to parse JSON: {e}")
                    # Try to parse as text and see if it's a different format
                    content = response.text[:500]
                    print(f"Response content preview: {content}")
                    return None
            else:
                print(f"Codelist API returned status code: {response.status_code}")
                if response.status_code == 404:
                    print("No codelist available for this concept")
                else:
                    print(f"Error response: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"Error getting codelist entries: {e}")
            return None
    
    def test_codelist_api(self, concept_id: str = "08d93fc7-6bb5-5585-a5a3-32a1d8ea7496"):
        """Test function to debug codelist API response"""
        url = f"https://api.i14y.admin.ch/api/public/v1/concepts/{concept_id}/codelist-entries/exports/json"
        print(f"Testing codelist API: {url}")
        
    def search_datasets(self, query='', page=1, page_size=20):
        """Search for datasets using the I14Y API
        
        Args:
            query: Search query string
            page: Page number (1-based)
            page_size: Number of results per page
            
        Returns:
            List of dataset dictionaries
        """
        print(f"I14Y client searching for datasets with query: '{query}'")
        
        # Ensure page and page_size are integers with defaults
        if page is None:
            page = 1
        if page_size is None:
            page_size = 20
            
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        
        url = f"{self.base_url}/search"
        params = {
            'types': 'Dataset'
        }
        
        if query.strip():
            params['query'] = query.strip()
        
        print(f"Making request to {url} with params: {params}")
        
        try:
            response = requests.get(url, params=params, timeout=10)
            print(f"API response status code: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            print(f"API response type: {type(data)}")
            print(f"API response content: {str(data)[:500]}...")
            
            # The new endpoint returns a list directly, not wrapped in a 'data' field
            if isinstance(data, list):
                print(f"Raw data contains {len(data)} items")
                # Apply manual pagination since the endpoint doesn't support it
                start = (page - 1) * page_size
                end = start + page_size
                result = data[start:end]
                print(f"Returning {len(result)} results after pagination")
                return result
                
            print("Data is not a list, returning empty list")
            return []
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return []
        except ValueError as e:
            print(f"JSON decode failed: {e}")
            return []
    
    def get_dataset_details(self, dataset_id: str) -> Optional[Dict]:
        """Get detailed information about a specific dataset
        
        Args:
            dataset_id: The UUID of the dataset
            
        Returns:
            Dataset details or None if not found
        """
        url = f"{self.base_url}/datasets/{dataset_id}"
        print(f"Fetching dataset details from: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            print(f"API response status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Received valid dataset data with keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
                return data
            elif response.status_code == 404:
                print(f"Dataset not found: {dataset_id}")
                return None
            else:
                print(f"API returned unexpected status code: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error response: {error_data}")
                except:
                    print(f"Could not parse error response: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"Error getting dataset details: {e}")
            return None
        try:
            response = requests.get(url, timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Content length: {len(response.content)} bytes")
            print(f"Content type: {response.headers.get('content-type')}")
            
            if response.status_code == 200:
                print("Raw content preview:")
                print(response.text[:1000])
                print("---")
                
                try:
                    data = response.json()
                    print(f"JSON parsed successfully: {type(data)}")
                    if isinstance(data, dict):
                        print(f"Keys: {list(data.keys())}")
                        for key, value in data.items():
                            print(f"  {key}: {type(value)} - {str(value)[:100]}")
                    elif isinstance(data, list):
                        print(f"List with {len(data)} items")
                        if data:
                            print(f"First item: {data[0]}")
                    return data
                except Exception as e:
                    print(f"JSON parse error: {e}")
                    return None
            else:
                print(f"Error response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def extract_constraints_from_concept(self, concept_data: Dict) -> Dict:
        """Extract SHACL constraints from I14Y concept data"""
        constraints = {}
        
        # Extract pattern from concept if available
        if 'pattern' in concept_data:
            pattern = concept_data['pattern']
            if pattern and isinstance(pattern, str):
                constraints['pattern'] = pattern
        
        # Extract enumeration from codelist if concept has one
        concept_id = concept_data.get('id')
        if concept_id:
            codelist_entries = self.get_codelist_entries(concept_id)
            if codelist_entries:
                # Extract values from codelist entries
                enum_values = []
                for entry in codelist_entries:
                    print(f"Processing codelist entry: {entry}")
                    # Try different possible value fields in order of preference
                    value = None
                    
                    # Check for common field names
                    for field_name in ['code', 'value', 'identifier', 'id', 'key', 'Code', 'Value']:
                        if field_name in entry and entry[field_name]:
                            value = str(entry[field_name])
                            break
                    
                    # If no direct value found, check for multilingual values
                    if not value:
                        for field_name in ['name', 'title', 'label', 'Name', 'Title', 'Label']:
                            if field_name in entry:
                                field_value = entry[field_name]
                                if isinstance(field_value, dict):
                                    # Multilingual field - try different languages
                                    value = (field_value.get('de') or 
                                            field_value.get('en') or 
                                            field_value.get('fr') or 
                                            field_value.get('it'))
                                elif field_value:
                                    value = str(field_value)
                                
                                if value:
                                    break
                    
                    if value:
                        enum_values.append(value)
                        print(f"Added enum value: {value}")
                
                if enum_values:
                    constraints['in_values'] = enum_values
                    print(f"Found {len(enum_values)} codelist entries for concept {concept_id}: {enum_values}")
                else:
                    print(f"No usable values found in codelist entries for concept {concept_id}")
        
        # Extract datatype constraints from I14Y concept data
        datatype = self._extract_datatype_from_i14y(concept_data)
        if datatype:
            constraints['datatype'] = datatype
            print(f"Extracted datatype from I14Y: {datatype}")
        
        # Extract length constraints if available
        if 'minLength' in concept_data:
            try:
                constraints['min_length'] = int(concept_data['minLength'])
            except (ValueError, TypeError):
                pass
        
        if 'maxLength' in concept_data:
            try:
                constraints['max_length'] = int(concept_data['maxLength'])
            except (ValueError, TypeError):
                pass
        
        return constraints
    
    def _extract_datatype_from_i14y(self, concept_data: Dict) -> Optional[str]:
        """Extract XSD datatype from I14Y concept data"""
        # Check direct datatype field
        if 'datatype' in concept_data:
            datatype = concept_data['datatype']
            if datatype:
                # Map I14Y datatypes to XSD datatypes
                datatype_lower = str(datatype).lower()
                if 'string' in datatype_lower or 'text' in datatype_lower:
                    return 'xsd:string'
                elif 'int' in datatype_lower or 'number' in datatype_lower:
                    return 'xsd:decimal'
                elif 'date' in datatype_lower:
                    return 'xsd:date'
                elif 'datetime' in datatype_lower:
                    return 'xsd:dateTime'
                elif 'boolean' in datatype_lower or 'bool' in datatype_lower:
                    return 'xsd:boolean'
                elif 'decimal' in datatype_lower or 'float' in datatype_lower:
                    return 'xsd:decimal'
                elif 'uri' in datatype_lower or 'url' in datatype_lower:
                    return 'xsd:anyURI'
        
        # Check conceptValueType
        concept_type = concept_data.get('conceptValueType', '').lower()
        if concept_type:
            if 'date' in concept_type:
                if 'time' in concept_type:
                    return 'xsd:dateTime'
                else:
                    return 'xsd:date'
            elif 'number' in concept_type or 'integer' in concept_type or 'numeric' in concept_type:
                return 'xsd:decimal'
            elif 'boolean' in concept_type or 'bool' in concept_type:
                return 'xsd:boolean'
            elif 'string' in concept_type or 'text' in concept_type:
                return 'xsd:string'
            elif 'uri' in concept_type or 'url' in concept_type:
                return 'xsd:anyURI'
        
        # Check for format hints
        if 'format' in concept_data:
            format_hint = str(concept_data['format']).lower()
            if 'date' in format_hint:
                return 'xsd:date'
            elif 'uri' in format_hint or 'url' in format_hint:
                return 'xsd:anyURI'
            elif 'email' in format_hint:
                return 'xsd:string'  # Could be more specific with pattern
        
        # Fallback: analyze title and description for datatype hints
        title_lower = concept_data.get('title', {})
        if isinstance(title_lower, dict):
            title_text = ' '.join(str(v) for v in title_lower.values()).lower()
        else:
            title_text = str(title_lower).lower()
            
        description_lower = concept_data.get('description', {})
        if isinstance(description_lower, dict):
            desc_text = ' '.join(str(v) for v in description_lower.values()).lower()
        else:
            desc_text = str(description_lower).lower()
        
        combined_text = f"{title_text} {desc_text}"
        
        # Pattern-based detection
        if any(word in combined_text for word in ['date', 'datum', 'birth', 'geburt', 'naissance', 'nascita']):
            if any(word in combined_text for word in ['time', 'zeit', 'heure', 'ora']):
                return 'xsd:dateTime'
            else:
                return 'xsd:date'
        elif any(word in combined_text for word in ['number', 'nummer', 'numéro', 'numero', 'age', 'alter', 'âge', 'età', 'count', 'anzahl']):
            return 'xsd:decimal'
        elif any(word in combined_text for word in ['yes', 'no', 'ja', 'nein', 'oui', 'non', 'sì', 'boolean']):
            return 'xsd:boolean'
        elif any(word in combined_text for word in ['url', 'uri', 'link', 'website', 'webpage']):
            return 'xsd:anyURI'
        
        return None
    
    def get_concept_schemes(self) -> List[Dict]:
        """Get all concept schemes from I14Y API"""
        try:
            url = f"{self.base_url}/concept-schemes"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API returned status code: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting concept schemes: {e}")
            return []

class SHACLNode:
    """Represents a node in the SHACL graph"""
    
    def __init__(self, node_type: str, node_id: str = None, title: str = "", description: str = ""):
        self.id = node_id or str(uuid.uuid4())
        self.type = node_type  # 'dataset', 'concept', 'class'
        self.title = title
        self.description = description
        self.i14y_id = None  # For concepts from I14Y (the concept UUID)
        self.i14y_data = None  # Full I14Y concept/dataset data
        self.i14y_concept_uri = None  # The I14Y concept URI
        self.i14y_dataset_uri = None  # The I14Y dataset URI
        self.connections = set()
        self.property_order = None  # For ordering in TTL export
        self.datatype = "xsd:string"  # Default datatype for concepts

        # Advanced SHACL constraints
        self.min_count = None  # sh:minCount
        self.max_count = None  # sh:maxCount
        self.min_length = None  # sh:minLength
        self.max_length = None  # sh:maxLength
        self.pattern = None  # sh:pattern (regex)
        self.in_values = []  # sh:in enumeration values
        self.node_reference = None  # sh:node class reference
        self.xone_groups = []  # sh:xone exclusive groups
        self.range = None  # rdfs:range
    
    def set_i14y_concept(self, concept_data: Dict):
        """Set I14Y concept information from API response"""
        self.i14y_data = concept_data
        self.i14y_id = concept_data.get('id')
        
        # Try multiple possible title fields from the I14Y API response
        title_obj = None
        
        # Try different field names that might contain the title
        for field_name in ['title', 'name', 'label', 'identifier', 'identifiers']:
            if field_name in concept_data:
                title_obj = concept_data[field_name]
                print(f"Found title field '{field_name}': {title_obj}")
                break
        
        if isinstance(title_obj, dict):
            # Handle multilingual titles
            self.title = (title_obj.get('de') or 
                         title_obj.get('en') or 
                         title_obj.get('fr') or 
                         title_obj.get('it') or 
                         title_obj.get('rm') or 
                         'Unknown')
        elif isinstance(title_obj, list):
            # Handle array of identifiers/titles
            self.title = title_obj[0] if title_obj else 'Unknown'
        elif title_obj:
            # Handle simple string
            self.title = str(title_obj)
        else:
            # Final fallback - use the concept ID or 'Unknown'
            self.title = concept_data.get('id', 'Unknown')
        
        print(f"Extracted title: {self.title}")
        
        # Add concept type info if available
        concept_type = concept_data.get('conceptValueType', '')
        if concept_type:
            self.title = f"{self.title} ({concept_type})"
        
        # Extract multilingual descriptions from 'description' field
        desc_obj = concept_data.get('description', {})
        if isinstance(desc_obj, dict):
            # Use German description as primary, fallback to other languages  
            self.description = (desc_obj.get('de') or 
                               desc_obj.get('en') or 
                               desc_obj.get('fr') or 
                               desc_obj.get('it') or 
                               desc_obj.get('rm') or 
                               '')
        else:
            self.description = str(desc_obj) if desc_obj else ''
        
        # Set the concept URI for TTL export
        if self.i14y_id:
            self.i14y_concept_uri = f"https://www.i14y.admin.ch/catalog/concepts/{self.i14y_id}/description"
        
        # Determine appropriate datatype based on concept metadata
        self._determine_datatype()
        
        # Extract and apply SHACL constraints from I14Y data
        self._apply_i14y_constraints()
    
    def set_i14y_dataset(self, dataset_data: Dict):
        """Set I14Y dataset information from API response"""
        self.i14y_data = dataset_data
        self.i14y_id = dataset_data.get('id')
        
        # Extract title from dataset data
        title_obj = dataset_data.get('title', {})
        if isinstance(title_obj, dict):
            self.title = (title_obj.get('de') or 
                          title_obj.get('en') or 
                          title_obj.get('fr') or 
                          title_obj.get('it') or 
                          title_obj.get('rm') or 
                          'Unknown Dataset')
        else:
            self.title = str(title_obj) if title_obj else 'Unknown Dataset'
        
        # Extract description from dataset data
        desc_obj = dataset_data.get('description', {})
        if isinstance(desc_obj, dict):
            self.description = (desc_obj.get('de') or 
                                desc_obj.get('en') or 
                                desc_obj.get('fr') or 
                                desc_obj.get('it') or 
                                desc_obj.get('rm') or 
                                '')
        else:
            self.description = str(desc_obj) if desc_obj else ''
        
        # Set the dataset URI for references
        if self.i14y_id:
            self.i14y_dataset_uri = f"https://www.i14y.admin.ch/catalog/datasets/{self.i14y_id}/description"
    
    def _apply_i14y_constraints(self):
        """Apply SHACL constraints extracted from I14Y concept data"""
        if not self.i14y_data:
            return
        
        # Create API client to extract constraints
        api_client = I14YAPIClient()
        
        # Extract constraints
        constraints = api_client.extract_constraints_from_concept(self.i14y_data)
        
        # Apply extracted constraints
        if 'pattern' in constraints:
            self.pattern = constraints['pattern']
            print(f"Applied pattern constraint: {self.pattern}")
        
        if 'in_values' in constraints:
            self.in_values = constraints['in_values']
            print(f"Applied enumeration constraint with {len(self.in_values)} values")
        
        if 'min_length' in constraints:
            self.min_length = constraints['min_length']
            print(f"Applied min_length constraint: {self.min_length}")
        
        if 'max_length' in constraints:
            self.max_length = constraints['max_length']
            print(f"Applied max_length constraint: {self.max_length}")
        
        if 'datatype' in constraints:
            self.datatype = constraints['datatype']
            print(f"Applied datatype constraint: {self.datatype}")
    
    def _determine_datatype(self):
        """Determine appropriate XSD datatype based on concept information"""
        if not self.i14y_data:
            return
        
        # Check concept category or keywords to determine datatype
        title_lower = self.title.lower()
        desc_lower = self.description.lower()
        
        # Date-related concepts
        if any(word in title_lower for word in ['date', 'datum', 'birth', 'geburt', 'naissance', 'nascita']):
            if any(word in title_lower for word in ['year', 'jahr', 'année', 'anno']):
                self.datatype = "xsd:decimal"
            else:
                self.datatype = "xsd:date"
        # Numeric concepts
        elif any(word in title_lower for word in ['number', 'nummer', 'numéro', 'numero', 'age', 'alter', 'âge', 'età']):
            self.datatype = "xsd:decimal"
        # Boolean concepts
        elif any(word in title_lower for word in ['over', 'älter', 'plus', 'superiore', 'boolean']):
            self.datatype = "xsd:boolean"
        else:
            self.datatype = "xsd:string"
    
    def get_multilingual_title(self) -> Dict[str, str]:
        """Get multilingual titles from I14Y data or fallback to single title"""
        if self.i14y_data and 'title' in self.i14y_data:
            title_obj = self.i14y_data['title']
            if isinstance(title_obj, dict):
                # Use available titles, fallback to base title for missing languages
                base_title = (title_obj.get('de') or 
                             title_obj.get('en') or 
                             title_obj.get('fr') or 
                             title_obj.get('it') or 
                             title_obj.get('rm') or 
                             self.title)
                return {
                    'de': title_obj.get('de', base_title),
                    'en': title_obj.get('en', base_title),
                    'fr': title_obj.get('fr', base_title),
                    'it': title_obj.get('it', base_title)
                }
        
        # Return same title for all languages as fallback
        return {
            'de': self.title,
            'en': self.title,
            'fr': self.title,
            'it': self.title
        }
    
    def get_multilingual_description(self) -> Dict[str, str]:
        """Get multilingual descriptions from I14Y data or fallback to single description"""
        if self.i14y_data and 'description' in self.i14y_data:
            desc_obj = self.i14y_data['description']
            if isinstance(desc_obj, dict):
                # Fill in missing languages with available ones
                available_desc = (desc_obj.get('de') or 
                                desc_obj.get('en') or 
                                desc_obj.get('fr') or 
                                desc_obj.get('it') or 
                                self.description)
                return {
                    'de': desc_obj.get('de', available_desc),
                    'en': desc_obj.get('en', available_desc),
                    'fr': desc_obj.get('fr', available_desc),
                    'it': desc_obj.get('it', available_desc)
                }
        
        # Return same description for all languages as fallback
        desc = self.description or self.title
        return {
            'de': desc,
            'en': desc,
            'fr': desc,
            'it': desc
        }
    
    def to_dict(self) -> Dict:
        connections_list = list(self.connections)
        
        # Debug log for connections
        if connections_list:
            print(f"Node {self.id} ({self.title}) has {len(connections_list)} connections")
        
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'description': self.description,
            'i14y_id': self.i14y_id,
            'i14y_data': self.i14y_data,
            'i14y_concept_uri': self.i14y_concept_uri,
            'i14y_dataset_uri': self.i14y_dataset_uri,
            'connections': connections_list,
            'property_order': self.property_order,
            'datatype': self.datatype,
            # Advanced SHACL constraints
            'min_count': self.min_count,
            'max_count': self.max_count,
            'min_length': self.min_length,
            'max_length': self.max_length,
            'pattern': self.pattern,
            'in_values': self.in_values,
            'node_reference': self.node_reference,
            'xone_groups': self.xone_groups,
            'range': self.range
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SHACLNode':
        node = cls(data['type'], data['id'], data['title'], data['description'])
        node.i14y_id = data.get('i14y_id')
        node.i14y_data = data.get('i14y_data')
        node.i14y_concept_uri = data.get('i14y_concept_uri')
        node.i14y_dataset_uri = data.get('i14y_dataset_uri')
        node.connections = set(data.get('connections', []))
        node.property_order = data.get('property_order')
        node.datatype = data.get('datatype', 'xsd:string')
        # Advanced SHACL constraints
        node.min_count = data.get('min_count')
        node.max_count = data.get('max_count')
        node.min_length = data.get('min_length')
        node.max_length = data.get('max_length')
        node.pattern = data.get('pattern')
        node.in_values = data.get('in_values', [])
        node.node_reference = data.get('node_reference')
        node.xone_groups = data.get('xone_groups', [])
        node.range = data.get('range')
        return node

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

def generate_full_ttl(nodes: Dict[str, SHACLNode], base_uri: str, edges: Dict[str, Dict] = None) -> str:
    """Generate full TTL using the RDF-based approach directly"""
    
    # Find dataset node  
    dataset_node = None
    for node in nodes.values():
        if node.type == 'dataset':
            dataset_node = node
            break
    
    if not dataset_node:
        raise ValueError("No dataset node found")
    
    # Generate a normalized dataset ID from title
    dataset_id = dataset_node.title.lower().replace(' ', '_').replace('-', '_')
    for ch in "()":
        dataset_id = dataset_id.replace(ch, "")
    while "__" in dataset_id:
        dataset_id = dataset_id.replace("__", "_")
    dataset_id = dataset_id.strip("_") or "dataset"

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
    
    def safe_add_conforms_to(uri, concept):
        """Safely add dcterms:conformsTo if concept has i14y_concept_uri"""
        if hasattr(concept, 'i14y_concept_uri') and concept.i14y_concept_uri:
            # Check if already exists to prevent duplicates
            existing = list(g.triples((uri, DCTERMS.conformsTo, URIRef(concept.i14y_concept_uri))))
            if not existing:
                g.add((uri, DCTERMS.conformsTo, URIRef(concept.i14y_concept_uri)))
                return True
        return False

    # Helper functions
    def sanitize_literal(text: str) -> str:
        if text is None:
            return ""
        # Collapse whitespace/newlines and escape quotes
        cleaned = " ".join(str(text).split())
        return cleaned.replace('"', '\\"')

    def norm_id(label: str) -> str:
        base = (label or "").strip()
        if not base:
            base = "property"
        base = base.replace(" ", "_").replace("-", "_")
        # remove parentheses and duplicate underscores
        for ch in "()":
            base = base.replace(ch, "")
        while "__" in base:
            base = base.replace("__", "_")
        return base.strip("_") or "property"

    # Create dataset NodeShape
    dataset_shape = URIRef(f"{i14y_ns}{dataset_id}")
    g.add((dataset_shape, RDF.type, SH.NodeShape))
    g.add((dataset_shape, RDF.type, RDFS.Class))
    g.add((dataset_shape, RDF.type, QB.DataStructureDefinition))

    # Add dataset metadata with multilingual support
    ds_title = sanitize_literal(dataset_node.title)
    ds_desc = sanitize_literal(dataset_node.description)

    # Add multilingual titles and descriptions (following I14Y pattern)
    # Only add one language tag to avoid duplicates
    if ds_title:
        safe_add_multilingual_property(dataset_shape, DCTERMS.title, ds_title, 'de')
        safe_add_multilingual_property(dataset_shape, RDFS.label, ds_title, 'de')
    if ds_desc:  # Primary language for description
        safe_add_multilingual_property(dataset_shape, DCTERMS.description, ds_desc, 'de')
        safe_add_multilingual_property(dataset_shape, RDFS.comment, ds_desc, 'de')

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

    # Collect concepts and classes connected to dataset
    connected_concepts = []
    connected_classes = []

    for conn_id in dataset_node.connections:
        if conn_id in nodes:
            connected_node = nodes[conn_id]
            if connected_node.type == 'concept':
                connected_concepts.append(connected_node)
            elif connected_node.type == 'class':
                connected_classes.append(connected_node)

    # First, create all class NodeShapes and collect their properties
    class_properties = {}  # Maps class_id to list of concept property URIs
    rdf_list_counter = 0  # For generating unique RDF list IDs

    for class_node in connected_classes:
        class_id = norm_id(class_node.title)
        class_uri = URIRef(f"{i14y_ns}{class_id}Type")  # Following I14Y pattern with "Type" suffix

        # Create NodeShape for the class
        g.add((class_uri, RDF.type, RDFS.Class))
        g.add((class_uri, RDF.type, SH.NodeShape))
        g.add((class_uri, SH.closed, Literal(True)))

        # Add class metadata
        class_title = sanitize_literal(class_node.title)
        class_desc = sanitize_literal(class_node.description)

        if class_title:
            safe_add_multilingual_property(class_uri, SH.name, class_title + "Type", "en")

        if class_desc:
            safe_add_multilingual_property(class_uri, DCTERMS.description, class_desc, "de")
            safe_add_multilingual_property(class_uri, RDFS.comment, class_desc, "de")

        # Collect concepts connected to this class
        class_concepts = []
        for conn_id in class_node.connections:
            if conn_id in nodes and nodes[conn_id].type == 'concept':
                class_concepts.append(nodes[conn_id])

        # Create property shapes for concepts belonging to this class
        class_property_uris = []
        for concept in class_concepts:
            concept_id = norm_id(concept.title)
            # Use the full I14Y URI pattern
            property_uri = URIRef(f"{i14y_ns}{concept_id}/{concept_id}")

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

        # Add properties to the class NodeShape
        for property_uri in class_property_uris:
            g.add((class_uri, SH.property, property_uri))

        # Store for dataset reference creation
        class_properties[class_node.id] = class_uri

    # Add property references for concepts directly connected to dataset
    property_order = 0
    for concept in connected_concepts:
        concept_id = norm_id(concept.title)
        # Use the full I14Y URI pattern with dataset_id path
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
        g.add((property_uri, SH.order, Literal(property_order, datatype=XSD.integer)))

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
        property_order += 1

    # Create PropertyShapes for classes and add them to the dataset
    for class_node in connected_classes:
        class_id = norm_id(class_node.title)
        class_uri = class_properties[class_node.id]
        # Create a property shape that references the class
        property_uri = URIRef(f"{i14y_ns}{dataset_id}/{class_id}")

        # Create PropertyShape for class
        g.add((property_uri, RDF.type, SH.PropertyShape))
        g.add((property_uri, RDF.type, OWL.ObjectProperty))
        g.add((property_uri, SH.path, property_uri))
        g.add((property_uri, SH.order, Literal(property_order, datatype=XSD.integer)))

        # Add advanced SHACL constraints for classes
        if class_node.min_count is not None:
            g.add((property_uri, SH.minCount, Literal(class_node.min_count, datatype=XSD.integer)))
        if class_node.max_count is not None:
            g.add((property_uri, SH.maxCount, Literal(class_node.max_count, datatype=XSD.integer)))

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
        property_order += 1

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
    
    def add_custom_concept(self, title, description):
        """Add a custom concept node (Flask version) - returns node_id"""
        concept_node = SHACLNode('concept', title=title, description=description or "")
        self.nodes[concept_node.id] = concept_node
        
        # Only connect to dataset if no parent is specified (handled in Flask app)
        # This prevents automatic dataset connection when adding to a class
        return concept_node.id
    
    def add_i14y_concept(self, concept_data):
        """Add an I14Y concept node (Flask version) - returns node_id"""
        if not concept_data:
            raise ValueError("No concept data provided")
        
        concept_id = concept_data.get('id')
        if not concept_id:
            raise ValueError("Concept ID is required")
        
        # Extract title from multilingual data
        title_data = concept_data.get('title', {})
        if isinstance(title_data, dict):
            title = title_data.get('de') or title_data.get('fr') or title_data.get('it') or title_data.get('en') or str(title_data)
        else:
            title = str(title_data) if title_data else f"Concept {concept_id}"
        
        # Extract description from multilingual data
        desc_data = concept_data.get('description', {})
        if isinstance(desc_data, dict):
            description = desc_data.get('de') or desc_data.get('fr') or desc_data.get('it') or desc_data.get('en') or ""
        else:
            description = str(desc_data) if desc_data else ""
        
        # Create SHACL node
        shacl_node = SHACLNode('concept', title=title, description=description, i14y_id=concept_id)
        
        # Extract constraints from I14Y concept
        try:
            constraints = self.api_client.extract_constraints_from_concept(concept_data)
            if constraints:
                # Apply constraints to the node
                if 'pattern' in constraints:
                    shacl_node.pattern = constraints['pattern']
                if 'in_values' in constraints:
                    shacl_node.in_values = constraints['in_values']
                if 'min_length' in constraints:
                    shacl_node.min_length = constraints['min_length']
                if 'max_length' in constraints:
                    shacl_node.max_length = constraints['max_length']
                if 'datatype' in constraints:
                    shacl_node.datatype = constraints['datatype']
        except Exception as e:
            print(f"Warning: Could not extract constraints from I14Y concept: {e}")
        
        self.nodes[shacl_node.id] = shacl_node
        
        # Only connect to dataset if no parent is specified (handled in Flask app)
        # This prevents automatic dataset connection when adding to a class
        return shacl_node.id
    
    def update_graph(self):
        """Update the graph visualization"""
        self.ax.clear()
        
        if not self.nodes:
            self.canvas.draw()
            return
        
        # Create NetworkX graph
        G = nx.Graph()
        
        # Add nodes
        for node in self.nodes.values():
            G.add_node(node.id, label=node.title, type=node.type)
        
        # Add edges
        for node in self.nodes.values():
            for conn_id in node.connections:
                if conn_id in self.nodes:
                    G.add_edge(node.id, conn_id)
        
        # Calculate layout
        if len(G.nodes()) > 0:
            pos = nx.spring_layout(G, k=2, iterations=50)
        else:
            pos = {}
        
        # Define colors for different node types
        node_colors = []
        for node_id in G.nodes():
            node = self.nodes[node_id]
            if node.type == 'dataset':
                color = '#ff9999'  # Light red
            elif node.type == 'concept':
                color = '#99ccff'  # Light blue
            elif node.type == 'class':
                color = '#99ff99'  # Light green
            else:
                color = '#ffffff'
            
            # Highlight selected nodes
            if node_id in self.selected_nodes:
                color = '#ffff00'  # Yellow for selected
            
            node_colors.append(color)
        
        # Draw the graph
        if pos:
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                                 node_size=1000, ax=self.ax)
            nx.draw_networkx_edges(G, pos, ax=self.ax)
            
            # Draw labels
            labels = {node_id: self.nodes[node_id].title[:15] + ('...' if len(self.nodes[node_id].title) > 15 else '') 
                     for node_id in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, font_size=8, ax=self.ax)
        
        self.ax.set_title("SHACL Graph Structure")
        self.ax.axis('off')
        
        # Store positions for click detection
        self.node_positions = pos
        
        self.canvas.draw()
    
    def on_node_click(self, event):
        """Handle node clicks"""
        if event.inaxes != self.ax or not self.node_positions:
            return
        
        # Find closest node
        click_x, click_y = event.xdata, event.ydata
        if click_x is None or click_y is None:
            return
        
        min_dist = float('inf')
        closest_node = None
        
        for node_id, (x, y) in self.node_positions.items():
            dist = ((click_x - x) ** 2 + (click_y - y) ** 2) ** 0.5
            if dist < min_dist and dist < 0.1:  # Threshold for node selection
                min_dist = dist
                closest_node = node_id
        
        if closest_node:
            if event.button == 1:  # Left click
                if closest_node in self.selected_nodes:
                    self.selected_nodes.remove(closest_node)
                else:
                    self.selected_nodes.add(closest_node)
                
                self.update_graph()
                self.update_info_panel()
    
    def update_info_panel(self):
        """Update the info panel with selected node information"""
        self.info_text.delete('1.0', 'end')
        
        if not self.selected_nodes:
            self.info_text.insert('end', "No node selected")
            # Clear constraint fields
            self.clear_constraint_fields()
            return
        
        for node_id in self.selected_nodes:
            node = self.nodes[node_id]
            info = f"Type: {node.type.capitalize()}\n"
            info += f"Title: {node.title}\n"
            info += f"Description: {node.description}\n"
            
            if node.i14y_id:
                info += f"I14Y ID: {node.i14y_id}\n"
            
            if node.connections:
                info += f"Connections: {len(node.connections)}\n"
            
            info += "\n" + "-" * 30 + "\n\n"
            
            self.info_text.insert('end', info)
        
        # Update constraint fields if a single node is selected
        if len(self.selected_nodes) == 1:
            node_id = list(self.selected_nodes)[0]
            node = self.nodes[node_id]
            self.update_constraint_fields(node)
        else:
            self.clear_constraint_fields()
    
    def update_constraint_fields(self, node):
        """Update constraint input fields with node values"""
        # Cardinality
        self.min_count_var.set(str(node.min_count) if node.min_count is not None else "")
        self.max_count_var.set(str(node.max_count) if node.max_count is not None else "")
        
        # Length
        self.min_length_var.set(str(node.min_length) if node.min_length is not None else "")
        self.max_length_var.set(str(node.max_length) if node.max_length is not None else "")
        
        # Pattern
        self.pattern_var.set(node.pattern or "")
        
        # Enumeration values
        self.in_values_var.set(", ".join(node.in_values) if node.in_values else "")
        
        # Class reference
        self.node_ref_var.set(node.node_reference or "")
        
        # Range
        self.range_var.set(node.range or "")
    
    def clear_constraint_fields(self):
        """Clear all constraint input fields"""
        self.min_count_var.set("")
        self.max_count_var.set("")
        self.min_length_var.set("")
        self.max_length_var.set("")
        self.pattern_var.set("")
        self.in_values_var.set("")
        self.node_ref_var.set("")
        self.range_var.set("")
    
    def apply_constraints(self):
        """Apply constraint changes to selected node"""
        if len(self.selected_nodes) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one node to apply constraints.")
            return
        
        node_id = list(self.selected_nodes)[0]
        node = self.nodes[node_id]
        
        try:
            # Apply cardinality constraints
            min_count_text = self.min_count_var.get().strip()
            max_count_text = self.max_count_var.get().strip()
            
            node.min_count = int(min_count_text) if min_count_text else None
            node.max_count = int(max_count_text) if max_count_text else None
            
            # Apply length constraints
            min_length_text = self.min_length_var.get().strip()
            max_length_text = self.max_length_var.get().strip()
            
            node.min_length = int(min_length_text) if min_length_text else None
            node.max_length = int(max_length_text) if max_length_text else None
            
            # Apply pattern
            node.pattern = self.pattern_var.get().strip() or None
            
            # Apply enumeration values
            in_values_text = self.in_values_var.get().strip()
            if in_values_text:
                # Split by comma and strip whitespace
                node.in_values = [v.strip() for v in in_values_text.split(",") if v.strip()]
            else:
                node.in_values = []
            
            # Apply class reference
            node.node_reference = self.node_ref_var.get().strip() or None
            
            # Apply range
            node.range = self.range_var.get().strip() or None
            
            messagebox.showinfo("Success", "SHACL constraints applied successfully!")
            
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid numeric value: {str(e)}")
    
    def clear_constraints(self):
        """Clear all constraints from selected node"""
        if len(self.selected_nodes) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one node to clear constraints.")
            return
        
        node_id = list(self.selected_nodes)[0]
        node = self.nodes[node_id]
        
        # Clear all constraints
        node.min_count = None
        node.max_count = None
        node.min_length = None
        node.max_length = None
        node.pattern = None
        node.in_values = []
        node.node_reference = None
        node.range = None
        
        # Update UI
        self.clear_constraint_fields()
        
        messagebox.showinfo("Success", "All SHACL constraints cleared!")
    
    def remove_selected(self):
        """Remove selected nodes"""
        if not self.selected_nodes:
            messagebox.showwarning("No Selection", "Please select nodes to remove.")
            return
        
        # Don't allow removing the dataset node
        dataset_nodes = [node_id for node_id in self.selected_nodes 
                        if self.nodes[node_id].type == 'dataset']
        if dataset_nodes:
            messagebox.showwarning("Cannot Remove", "Cannot remove the dataset node.")
            return
        
        # Remove connections first
        for node_id in self.selected_nodes:
            node = self.nodes[node_id]
            for conn_id in list(node.connections):
                if conn_id in self.nodes:
                    self.nodes[conn_id].connections.discard(node_id)
        
        # Remove nodes
        for node_id in self.selected_nodes:
            del self.nodes[node_id]
        
        self.selected_nodes.clear()
        self.update_graph()
        self.update_info_panel()
    
    def connect_nodes(self):
        """Connect selected nodes"""
        if len(self.selected_nodes) != 2:
            messagebox.showwarning("Invalid Selection", "Please select exactly 2 nodes to connect.")
            return
        
        node_ids = list(self.selected_nodes)
        node1, node2 = self.nodes[node_ids[0]], self.nodes[node_ids[1]]
        
        node1.connections.add(node2.id)
        node2.connections.add(node1.id)
        
        self.update_graph()
    
    def disconnect_nodes(self):
        """Disconnect selected nodes"""
        if len(self.selected_nodes) != 2:
            messagebox.showwarning("Invalid Selection", "Please select exactly 2 connected nodes to disconnect.")
            return
        
        node_ids = list(self.selected_nodes)
        node1, node2 = self.nodes[node_ids[0]], self.nodes[node_ids[1]]
        
        node1.connections.discard(node2.id)
        node2.connections.discard(node1.id)
        
        self.update_graph()
    
    def export_ttl(self):
        """Export the graph as TTL file"""
        if not self.nodes:
            messagebox.showwarning("No Data", "No data to export.")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".ttl",
            filetypes=[("Turtle files", "*.ttl"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        ttl_content = self.generate_ttl()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(ttl_content)
            messagebox.showinfo("Export Successful", f"TTL file exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting TTL file: {str(e)}")
    
    def generate_ttl(self) -> str:
        """Generate TTL content from the current graph in I14Y format using RDF graph approach"""
        # Find dataset node
        dataset_node = None
        for node in self.nodes.values():
            if node.type == 'dataset':
                dataset_node = node
                break

        if not dataset_node:
            return "# No dataset found"

        # Generate proper I14Y dataset ID - normalize
        raw_ds = dataset_node.title.strip() or "dataset"
        dataset_id = raw_ds.upper().replace(" ", "_").replace("-", "_")

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
                
            key = (str(uri), str(property_type), lang)
            if key in uri_lang_tracker:
                # Already exists for this URI+property+language - skip
                return False
            
            # Add to graph and track
            g.add((uri, property_type, Literal(content, lang=lang)))
            uri_lang_tracker[key] = content
            return True

        # Helper functions
        def sanitize_literal(text: str) -> str:
            if text is None:
                return ""
            # Collapse whitespace/newlines and escape quotes
            cleaned = " ".join(str(text).split())
            return cleaned.replace('"', '\\"')

        def norm_id(label: str) -> str:
            base = (label or "").strip()
            if not base:
                base = "property"
            base = base.replace(" ", "_").replace("-", "_")
            # remove parentheses and duplicate underscores
            for ch in "()":
                base = base.replace(ch, "")
            while "__" in base:
                base = base.replace("__", "_")
            return base.strip("_") or "property"

        # Create dataset NodeShape
        dataset_shape = URIRef(f"{i14y_ns}{dataset_id}")
        g.add((dataset_shape, RDF.type, SH.NodeShape))
        g.add((dataset_shape, RDF.type, RDFS.Class))
        g.add((dataset_shape, RDF.type, QB.DataStructureDefinition))
        g.add((dataset_shape, SH.closed, Literal(True)))

        # Add dataset metadata
        ds_title = sanitize_literal(dataset_node.title)
        ds_desc = sanitize_literal(dataset_node.description)

        if ds_title:
            safe_add_multilingual_property(dataset_shape, DCTERMS.title, ds_title, "de")
            safe_add_multilingual_property(dataset_shape, RDFS.label, ds_title, "de")
            safe_add_multilingual_property(dataset_shape, SH.name, ds_title, "de")

        if ds_desc:
            safe_add_multilingual_property(dataset_shape, DCTERMS.description, ds_desc, "de")
            safe_add_multilingual_property(dataset_shape, RDFS.comment, ds_desc, "de")
            g.add((dataset_shape, SH.description, Literal(ds_desc, lang="de")))

        # Collect concepts and classes connected to dataset
        connected_concepts = []
        connected_classes = []

        for conn_id in dataset_node.connections:
            if conn_id in self.nodes:
                connected_node = self.nodes[conn_id]
                if connected_node.type == 'concept':
                    connected_concepts.append(connected_node)
                elif connected_node.type == 'class':
                    connected_classes.append(connected_node)

        # Add property references and create property shapes
        property_order = 0
        rdf_list_counter = 0  # For generating unique RDF list IDs

        for concept in connected_concepts:
            concept_id = norm_id(concept.title)
            property_uri = URIRef(f"{i14y_ns}{concept_id}")

            # Create PropertyShape
            g.add((property_uri, RDF.type, SH.PropertyShape))
            g.add((property_uri, RDF.type, OWL.DatatypeProperty))
            g.add((property_uri, RDF.type, QB.AttributeProperty))
            g.add((property_uri, SH.path, property_uri))
            g.add((property_uri, SH.datatype, URIRef(concept.datatype)))
            g.add((property_uri, SH.order, Literal(property_order, datatype=XSD.integer)))

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
                
                # Create RDF list for enumeration values
                list_head = URIRef(f"_:autos{rdf_list_counter}")
                rdf_list_counter += 1
                g.add((property_uri, SH['in'], list_head))

                # Create RDF list items
                current = list_head
                for i, value in enumerate(concept.in_values[:-1]):
                    next_item = URIRef(f"_:autos{rdf_list_counter}")
                    rdf_list_counter += 1
                    g.add((current, RDF.first, Literal(value)))
                    g.add((current, RDF.rest, next_item))
                    current = next_item

                # Last item
                if concept.in_values:
                    g.add((current, RDF.first, Literal(concept.in_values[-1])))
                    g.add((current, RDF.rest, RDF.nil))

            # Add class reference (sh:node)
            if concept.node_reference:
                g.add((property_uri, SH.node, URIRef(concept.node_reference)))

            # Add multilingual titles and descriptions
            titles = concept.get_multilingual_title()
            descriptions = concept.get_multilingual_description()

            for lang, title in titles.items():
                if title and lang in ['de', 'fr', 'it', 'en']:
                    # Use safe method to prevent duplicates
                    sanitized_title = sanitize_literal(title)
                    safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
                    safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
                    safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

            for lang, desc in descriptions.items():
                # Only add the first value per language for each property
                if desc and lang in ['de', 'fr', 'it', 'en']:
                    sanitized_desc = sanitize_literal(desc)
                    # Use safe method to prevent duplicates
                    safe_add_multilingual_property(property_uri, DCTERMS.description, sanitized_desc, lang)
                    safe_add_multilingual_property(property_uri, RDFS.comment, sanitized_desc, lang)
                    safe_add_multilingual_property(property_uri, SH.description, sanitized_desc, lang)

            # Add to dataset properties
            g.add((dataset_shape, SH.property, property_uri))
            property_order += 1

        # Generate property shapes for classes
        for class_node in connected_classes:
            class_id = norm_id(class_node.title)
            class_uri = URIRef(f"{i14y_ns}{class_id}Type")  # Must match the class definition with Type suffix
            # Property URI should be in the dataset namespace
            property_uri = URIRef(f"{i14y_ns}{dataset_id}/{class_id}")

            # Create PropertyShape for class reference in dataset
            g.add((property_uri, RDF.type, SH.PropertyShape))
            g.add((property_uri, RDF.type, OWL.ObjectProperty))
            g.add((property_uri, SH.path, property_uri))
            g.add((property_uri, SH.order, Literal(property_order, datatype=XSD.integer)))

            # Add advanced SHACL constraints for classes
            if class_node.min_count is not None:
                g.add((property_uri, SH.minCount, Literal(class_node.min_count, datatype=XSD.integer)))
            if class_node.max_count is not None:
                g.add((property_uri, SH.maxCount, Literal(class_node.max_count, datatype=XSD.integer)))

            # Link to the class NodeShape
            g.add((property_uri, SH.node, class_uri))

            # Add multilingual titles and descriptions
            titles = class_node.get_multilingual_title()
            descriptions = class_node.get_multilingual_description()

            # Ensure we always have at least a basic label
            class_title = sanitize_literal(class_node.title)
            if class_title:
                # Add basic German label as fallback (required for I14Y visualization)
                safe_add_multilingual_property(property_uri, RDFS.label, class_title, "de")
                safe_add_multilingual_property(property_uri, DCTERMS.title, class_title, "de")
                safe_add_multilingual_property(property_uri, SH.name, class_title, "de")

            # Filter out duplicate content across languages
            unique_titles = get_unique_lang_values(titles, sanitize_literal)
            unique_descriptions = get_unique_lang_values(descriptions, sanitize_literal)

            for lang, title in unique_titles.items():
                if title and lang in ['de', 'fr', 'it', 'en']:
                    # Use safe method to prevent duplicates
                    sanitized_title = sanitize_literal(title)
                    safe_add_multilingual_property(property_uri, DCTERMS.title, sanitized_title, lang)
                    safe_add_multilingual_property(property_uri, RDFS.label, sanitized_title, lang)
                    safe_add_multilingual_property(property_uri, SH.name, sanitized_title, lang)

            for lang, desc in unique_descriptions.items():
                if desc and lang in ['de', 'fr', 'it', 'en']:
                    # Use safe_add_multilingual_property instead of direct addition
                    sanitized_desc = sanitize_literal(desc)
                    safe_add_multilingual_property(property_uri, DCTERMS.description, sanitized_desc, lang)
                    safe_add_multilingual_property(property_uri, RDFS.comment, sanitized_desc, lang)
                    safe_add_multilingual_property(property_uri, SH.description, sanitized_desc, lang)

            # Find concepts and classes connected to this class
            connected_class_concepts = []
            connected_class_classes = []
            for conn_id in class_node.connections:
                if conn_id in self.nodes:
                    connected_node = self.nodes[conn_id]
                    if connected_node.type == 'concept':
                        connected_class_concepts.append(connected_node)
                    elif connected_node.type == 'class':
                        connected_class_classes.append(connected_node)

            # Add property shapes for concepts connected to this class
            for concept in connected_class_concepts:
                concept_id = norm_id(concept.title)
                concept_property_uri = URIRef(f"{i14y_ns}{concept_id}")

                # Create PropertyShape for the concept
                g.add((concept_property_uri, RDF.type, SH.PropertyShape))
                g.add((concept_property_uri, RDF.type, OWL.DatatypeProperty))
                g.add((concept_property_uri, RDF.type, QB.AttributeProperty))
                g.add((concept_property_uri, SH.path, concept_property_uri))
                g.add((concept_property_uri, SH.datatype, URIRef(concept.datatype)))
                g.add((concept_property_uri, SH.order, Literal(property_order, datatype=XSD.integer)))

                # Add I14Y concept reference if available
                safe_add_conforms_to(concept_property_uri, concept)

                # Add advanced SHACL constraints
                if concept.min_count is not None:
                    g.add((concept_property_uri, SH.minCount, Literal(concept.min_count, datatype=XSD.integer)))
                if concept.max_count is not None:
                    g.add((concept_property_uri, SH.maxCount, Literal(concept.max_count, datatype=XSD.integer)))
                if concept.min_length is not None:
                    g.add((concept_property_uri, SH.minLength, Literal(concept.min_length, datatype=XSD.integer)))
                if concept.max_length is not None:
                    g.add((concept_property_uri, SH.maxLength, Literal(concept.max_length, datatype=XSD.integer)))
                if concept.pattern:
                    g.add((concept_property_uri, SH.pattern, Literal(concept.pattern)))
                if concept.range:
                    g.add((concept_property_uri, RDFS.range, URIRef(concept.range)))

                # Add enumeration values (sh:in)
                if concept.in_values:
                    # Add QB:CodedProperty for enumerated values
                    g.add((concept_property_uri, RDF.type, QB.CodedProperty))
                    
                    # Create RDF list for enumeration values
                    list_head = URIRef(f"_:autos{rdf_list_counter}")
                    rdf_list_counter += 1
                    g.add((concept_property_uri, SH['in'], list_head))

                    # Create RDF list items
                    current = list_head
                    for i, value in enumerate(concept.in_values[:-1]):
                        next_item = URIRef(f"_:autos{rdf_list_counter}")
                        rdf_list_counter += 1
                        g.add((current, RDF.first, Literal(value)))
                        g.add((current, RDF.rest, next_item))
                        current = next_item

                    # Last item
                    if concept.in_values:
                        g.add((current, RDF.first, Literal(concept.in_values[-1])))
                        g.add((current, RDF.rest, RDF.nil))

                # Add class reference (sh:node)
                if concept.node_reference:
                    g.add((concept_property_uri, SH.node, URIRef(concept.node_reference)))

                # Add multilingual titles and descriptions
                titles = concept.get_multilingual_title()
                descriptions = concept.get_multilingual_description()

                for lang, title in titles.items():
                    if title and lang in ['de', 'fr', 'it', 'en']:
                        # Use safe method to prevent duplicates
                        sanitized_title = sanitize_literal(title)
                        safe_add_multilingual_property(concept_property_uri, DCTERMS.title, sanitized_title, lang)
                        safe_add_multilingual_property(concept_property_uri, RDFS.label, sanitized_title, lang)
                        safe_add_multilingual_property(concept_property_uri, SH.name, sanitized_title, lang)

                for lang, desc in descriptions.items():
                    if desc and lang in ['de', 'fr', 'it', 'en']:
                        # Use safe method to prevent duplicates
                        sanitized_desc = sanitize_literal(desc)
                        safe_add_multilingual_property(concept_property_uri, DCTERMS.description, sanitized_desc, lang)
                        safe_add_multilingual_property(concept_property_uri, RDFS.comment, sanitized_desc, lang)
                        safe_add_multilingual_property(concept_property_uri, SH.description, sanitized_desc, lang)

                # Add to class properties
                g.add((class_uri, SH.property, concept_property_uri))
                property_order += 1

            # Add property shapes for classes connected to this class (class-to-class relationships)
            for connected_class in connected_class_classes:
                connected_class_id = norm_id(connected_class.title)
                connected_class_uri = URIRef(f"{i14y_ns}{connected_class_id}")
                class_ref_property_uri = URIRef(f"{i14y_ns}{class_id}_has_{connected_class_id}")

                # Create PropertyShape for the class reference
                g.add((class_ref_property_uri, RDF.type, SH.PropertyShape))
                g.add((class_ref_property_uri, RDF.type, OWL.ObjectProperty))
                g.add((class_ref_property_uri, SH.path, class_ref_property_uri))
                g.add((class_ref_property_uri, SH.order, Literal(property_order, datatype=XSD.integer)))

                # Use sh:node instead of sh:class for I14Y (as recommended in documentation section 6)
                g.add((class_ref_property_uri, SH.node, connected_class_uri))

                # Get cardinality from edge if available
                edge_id = f"{class_node.id}-{connected_class.id}"
                if edges and edge_id in edges:
                    cardinality = edges[edge_id].get('cardinality', '1..1')
                else:
                    # Try reverse edge
                    reverse_edge_id = f"{connected_class.id}-{class_node.id}"
                    if edges and reverse_edge_id in edges:
                        cardinality = edges[reverse_edge_id].get('cardinality', '1..1')
                    else:
                        cardinality = '1..1'  # Default

                # Parse cardinality and add SHACL constraints
                min_count, max_count = parse_cardinality(cardinality)
                if min_count is not None:
                    g.add((class_ref_property_uri, SH.minCount, Literal(min_count, datatype=XSD.integer)))
                if max_count is not None:
                    g.add((class_ref_property_uri, SH.maxCount, Literal(max_count, datatype=XSD.integer)))

                # Add multilingual labels for the relationship
                relationship_title = f"has {connected_class.title}"
                relationship_desc = f"Reference to {connected_class.title} instances"

                safe_add_multilingual_property(class_ref_property_uri, DCTERMS.title, relationship_title, "de")
                safe_add_multilingual_property(class_ref_property_uri, RDFS.label, relationship_title, "de")
                safe_add_multilingual_property(class_ref_property_uri, SH.name, relationship_title, "de")
                safe_add_multilingual_property(class_ref_property_uri, DCTERMS.description, relationship_desc, "de")
                safe_add_multilingual_property(class_ref_property_uri, RDFS.comment, relationship_desc, "de")
                safe_add_multilingual_property(class_ref_property_uri, SH.description, relationship_desc, "de")

                # Add to class properties
                g.add((class_uri, SH.property, class_ref_property_uri))
                property_order += 1

            # Add to dataset properties
            g.add((dataset_shape, SH.property, property_uri))
            property_order += 1

        # Add sh:xone constraints for exclusive property groups
        if hasattr(dataset_node, 'xone_groups') and dataset_node.xone_groups:
            for group_idx, group in enumerate(dataset_node.xone_groups):
                xone_list = BNode()
                g.add((dataset_shape, SH.xone, xone_list))

                for prop_idx, prop_uri in enumerate(group):
                    prop_shape = BNode()
                    g.add((xone_list, RDF.first, prop_shape))
                    g.add((prop_shape, RDF.type, SH.PropertyShape))
                    g.add((prop_shape, SH.path, URIRef(prop_uri)))

                    if prop_idx < len(group) - 1:
                        next_list = BNode()
                        g.add((xone_list, RDF.rest, next_list))
                        xone_list = next_list
                    else:
                        g.add((xone_list, RDF.rest, RDF.nil))

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
@prefix QB: <http://purl.org/linked-data/cube#>.
@prefix dcterms: <http://purl.org/dc/terms/>.
@prefix i14y: <https://www.i14y.admin.ch/resources/datasets/{dataset_id}/structure/>.
@prefix owl: <http://www.w3.org/2002/07/owl#>.
@prefix sh: <http://www.w3.org/ns/shacl#>.

"""

        return custom_prefixes + '\n'.join(data_lines) + '\n'
    
    def save_project(self):
        """Save the current project"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        project_data = {
            'nodes': {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            'dataset_title': self.dataset_title_var.get(),
            'dataset_description': self.dataset_desc_var.get(),
            'created': datetime.now().isoformat()
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2)
            messagebox.showinfo("Save Successful", f"Project saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving project: {str(e)}")
    
    def load_project(self):
        """Load a project from file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Clear current data
            self.nodes.clear()
            self.selected_nodes.clear()
            
            # Load nodes
            for node_id, node_data in project_data.get('nodes', {}).items():
                self.nodes[node_id] = SHACLNode.from_dict(node_data)
            
            # Update UI
            self.dataset_title_var.set(project_data.get('dataset_title', ''))
            self.dataset_desc_var.set(project_data.get('dataset_description', ''))
            
            self.update_graph()
            self.update_info_panel()
            
            messagebox.showinfo("Load Successful", f"Project loaded from {file_path}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Error loading project: {str(e)}")
    
    def import_ttl(self):
        """Import SHACL schema from TTL file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Turtle files", "*.ttl"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Clear current data
            self.nodes.clear()
            self.selected_nodes.clear()
            
            # Parse TTL file
            from rdflib import Graph, Namespace, RDF, RDFS, SH, DCTERMS, XSD
            
            g = Graph()
            g.parse(file_path, format='turtle')
            
            # Extract SHACL information
            self._extract_shacl_from_graph(g)
            
            # Update UI
            self.update_graph()
            self.update_info_panel()
            
            messagebox.showinfo("Import Successful", f"TTL file imported from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Import Error", f"Error importing TTL file: {str(e)}")
    
    def load_example_ttl(self):
        """Load the example working.ttl file"""
        file_path = "/home/this/Dokumente/bfs/shacl-creator/working.ttl"
        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"Example file not found: {file_path}")
            return
        
        try:
            # Clear current data
            self.nodes.clear()
            self.selected_nodes.clear()
            
            # Parse TTL file
            from rdflib import Graph
            
            g = Graph()
            g.parse(file_path, format='turtle')
            
            # Extract SHACL information
            self._extract_shacl_from_graph(g)
            
            # Update UI
            self.update_graph()
            self.update_info_panel()
            
            messagebox.showinfo("Load Successful", f"Example TTL file loaded from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Error loading example TTL file: {str(e)}")
    
    def _extract_shacl_from_graph(self, g):
        """Extract SHACL information from RDF graph and create SHACLNode objects"""
        from rdflib import Namespace, RDF, RDFS, SH, DCTERMS, XSD, URIRef, Literal
        from rdflib.namespace import OWL
        
        # Find the main dataset NodeShape
        dataset_shape = None
        for s, p, o in g.triples((None, RDF.type, SH.NodeShape)):
            # Look for the main dataset shape (usually has sh:property but not sh:path)
            if (s, SH.path, None) not in g and (s, SH.property, None) in g:
                dataset_shape = s
                break
        
        if not dataset_shape:
            raise ValueError("No main dataset NodeShape found in TTL file")
        
        # Create dataset node
        dataset_node = SHACLNode('dataset', title=str(dataset_shape).split('/')[-1])
        
        # Extract dataset metadata
        for p, o in g.predicate_objects(dataset_shape):
            if p == DCTERMS.title:
                if hasattr(o, 'language') and o.language:
                    # Handle multilingual titles
                    if o.language == 'de':
                        dataset_node.title = str(o)
                    elif o.language == 'fr':
                        dataset_node.description = str(o)  # Use description for French
                else:
                    dataset_node.title = str(o)
            elif p == DCTERMS.description:
                if hasattr(o, 'language') and o.language:
                    if o.language == 'de':
                        dataset_node.description = str(o)
                else:
                    dataset_node.description = str(o)
        
        self.nodes[dataset_node.id] = dataset_node
        
        # Extract property shapes
        property_shapes = []
        for s, p, o in g.triples((dataset_shape, SH.property, None)):
            property_shapes.append(o)
        
        # Process each property shape
        for prop_shape in property_shapes:
            # Get property path
            path = None
            for s, p, o in g.triples((prop_shape, SH.path, None)):
                path = o
                break
            
            if not path:
                continue
            
            # Determine if it's a datatype or object property
            is_object_property = False
            for s, p, o in g.triples((prop_shape, RDF.type, OWL.ObjectProperty)):
                is_object_property = True
                break
            
            # Create concept or class node
            node_type = 'class' if is_object_property else 'concept'
            node_title = str(path).split('/')[-1]
            
            shacl_node = SHACLNode(node_type, title=node_title)
            
            # Extract constraints
            for p, o in g.predicate_objects(prop_shape):
                if p == SH.minCount:
                    shacl_node.min_count = int(o)
                elif p == SH.maxCount:
                    shacl_node.max_count = int(o)
                elif p == SH.minLength:
                    shacl_node.min_length = int(o)
                elif p == SH.maxLength:
                    shacl_node.max_length = int(o)
                elif p == SH.pattern:
                    shacl_node.pattern = str(o)
                elif p == SH.datatype:
                    shacl_node.datatype = str(o)
                elif p == RDFS.range:
                    shacl_node.range = str(o)
                elif p == SH.node:
                    shacl_node.node_reference = str(o)
                elif p == SH['in']:
                    # Extract RDF list values
                    shacl_node.in_values = self._extract_rdf_list(g, o)
                elif p == DCTERMS.title:
                    if hasattr(o, 'language') and o.language:
                        if o.language == 'de':
                            shacl_node.title = str(o)
                    else:
                        shacl_node.title = str(o)
                elif p == DCTERMS.description:
                    if hasattr(o, 'language') and o.language:
                        if o.language == 'de':
                            shacl_node.description = str(o)
                    else:
                        shacl_node.description = str(o)
            
            self.nodes[shacl_node.id] = shacl_node
            
            # Connect to dataset
            dataset_node.connections.add(shacl_node.id)
            shacl_node.connections.add(dataset_node.id)
    
    def _extract_rdf_list(self, g, list_head):
        """Extract values from RDF list (used for sh:in enumerations)"""
        from rdflib import RDF
        
        values = []
        current = list_head
        
        while current != RDF.nil:
            # Get first value
            for s, p, o in g.triples((current, RDF.first, None)):
                values.append(str(o))
                break
            
            # Get rest of list
            rest = None
            for s, p, o in g.triples((current, RDF.rest, None)):
                rest = o
                break
            
            if rest is None or rest == RDF.nil:
                break
            current = rest
        
        return values

#------------------------------------------------------------------------------
# Flask Web Application
#------------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production

class FlaskSHACLGraphEditor:
    """
    SHACL Graph Editor for Flask
    
    This class manages the state of the SHACL graph editor.
    """
    
    def __init__(self):
        self.nodes = {}  # Dictionary of nodes keyed by ID
        self.edges = {}  # Dictionary of edges keyed by ID (format: "node1_id-node2_id")
        self.i14y_client = I14YAPIClient()
        self.base_uri = "https://www.i14y.admin.ch/resources/datasets/shacl_editor/structure/"
    
    def add_node(self, node_data):
        """Add a new node to the graph"""
        node = SHACLNode.from_dict(node_data)
        self.nodes[node.id] = node
        return node.to_dict()
    
    def update_node(self, node_id, node_data):
        """Update an existing node with partial data"""
        if node_id not in self.nodes:
            return None
            
        node = self.nodes[node_id]
        
        # Update only the provided fields
        if 'title' in node_data:
            node.title = node_data['title']
        if 'description' in node_data:
            node.description = node_data['description']
        if 'datatype' in node_data:
            node.datatype = node_data['datatype']
        if 'min_length' in node_data:
            node.min_length = node_data['min_length'] if node_data['min_length'] else None
        if 'max_length' in node_data:
            node.max_length = node_data['max_length'] if node_data['max_length'] else None
        if 'pattern' in node_data:
            node.pattern = node_data['pattern'] if node_data['pattern'] else None
        if 'in_values' in node_data:
            node.in_values = node_data['in_values'] if node_data['in_values'] else []
        if 'node_reference' in node_data:
            node.node_reference = node_data['node_reference'] if node_data['node_reference'] else None
        if 'range' in node_data:
            node.range = node_data['range'] if node_data['range'] else None
            
        return {"success": True, "node": node.to_dict()}
    
    def delete_node(self, node_id):
        """Delete a node from the graph"""
        if node_id not in self.nodes:
            return False
            
        # Remove connections to this node
        for other_id, node in self.nodes.items():
            if node_id in node.connections:
                node.connections.remove(node_id)
                
        # Delete the node
        del self.nodes[node_id]
        return True
    
    def get_node(self, node_id):
        """Get a node by ID"""
        if node_id in self.nodes:
            return self.nodes[node_id].to_dict()
        return None
    
    def get_all_nodes(self):
        """Get all nodes"""
        return {node_id: node.to_dict() for node_id, node in self.nodes.items()}
    
    def connect_nodes(self, source_id, target_id):
        """Connect two nodes"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return False
            
        # Add to connections set
        self.nodes[source_id].connections.add(target_id)
        
        # Create an edge in the edge dictionary
        edge_id = f"{source_id}-{target_id}"
        self.edges[edge_id] = {
            'id': edge_id,
            'from': source_id,
            'to': target_id,
            'cardinality': '1..1'
        }
        
        print(f"Connected nodes: {source_id} -> {target_id}")
        return True
    
    def disconnect_nodes(self, source_id, target_id):
        """Disconnect two nodes"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return False
            
        # Remove from connections set
        if target_id in self.nodes[source_id].connections:
            self.nodes[source_id].connections.remove(target_id)
        
        # Remove edge from edge dictionary
        edge_id = f"{source_id}-{target_id}"
        if edge_id in self.edges:
            del self.edges[edge_id]
            
        print(f"Disconnected nodes: {source_id} -> {target_id}")
        return True
        
    def reset_structure(self):
        """Reset the structure to a new empty one with just a dataset node"""
        try:
            # Complete clearing of all data structures
            print("Resetting structure - clearing all nodes and edges")
            
            # Make a new, empty dictionary instead of clearing the existing one
            self.nodes = {}
            self.edges = {}
            
            # Create a new dataset node
            dataset_node = SHACLNode(
                node_id='dataset',
                title="Dataset", 
                description="Dataset description", 
                node_type='dataset'
            )
            self.nodes[dataset_node.id] = dataset_node
            
            # Log the reset
            print(f"Reset complete. New structure has {len(self.nodes)} nodes and {len(self.edges)} edges")
            print("Generating new dataset: Dataset")
            
            return True
        except Exception as e:
            print(f"Error in reset_structure: {str(e)}")
            return False
    
    def create_edge(self, node1_id, node2_id, cardinality="1..1"):
        """Create an edge between two nodes with cardinality"""
        edge_id = f"{node1_id}-{node2_id}"
        reverse_edge_id = f"{node2_id}-{node1_id}"
        
        # Store edge with cardinality
        self.edges[edge_id] = {
            'id': edge_id,
            'from': node1_id,
            'to': node2_id,
            'cardinality': cardinality
        }
        
        print(f"Created edge '{edge_id}' with cardinality {cardinality}")
        
        return edge_id
        # Remove reverse edge if it exists (avoid duplicates)
        if reverse_edge_id in self.edges:
            del self.edges[reverse_edge_id]
            
        return True
    
    def update_edge_cardinality(self, edge_id, cardinality):
        """Update the cardinality of an edge"""
        if edge_id in self.edges:
            self.edges[edge_id]['cardinality'] = cardinality
            return True
        return False
    
    def delete_edge(self, edge_id):
        """Delete an edge"""
        if edge_id in self.edges:
            del self.edges[edge_id]
            return True
        return False
    
    def get_edge(self, edge_id):
        """Get edge by ID"""
        return self.edges.get(edge_id)
    
    def get_all_edges(self):
        """Get all edges"""
        return self.edges
    
    def generate_ttl(self):
        """Generate TTL for all nodes"""
        return generate_full_ttl(self.nodes, self.base_uri, self.edges)
    
    def save_to_file(self, filepath):
        """Save the current graph to a JSON file"""
        data = {
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": self.edges,
            "base_uri": self.base_uri
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    
    def load_from_file(self, filepath):
        """Load a graph from a JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            self.nodes = {}
            for node_id, node_data in data.get("nodes", {}).items():
                self.nodes[node_id] = SHACLNode.from_dict(node_data)
            
            # Load edges if available (for backward compatibility)
            self.edges = data.get("edges", {})
                
            self.base_uri = data.get("base_uri", self.base_uri)
            
            return True
        except Exception as e:
            print(f"Error loading graph: {e}")
            return False

# Create an instance of the graph editor
editor = FlaskSHACLGraphEditor()

# Initialize with a default dataset node if none exists
dataset_exists = False
for node in editor.nodes.values():
    if node.type == 'dataset':
        dataset_exists = True
        break
        
if not dataset_exists:
    dataset_node = SHACLNode('dataset', title="New Dataset", description="Dataset description")
    editor.nodes[dataset_node.id] = dataset_node

@app.route('/')
def index():
    """Render the main application page"""
    # Ensure we have a dataset node
    dataset_exists = False
    for node in editor.nodes.values():
        if node.type == 'dataset':
            dataset_exists = True
            break
            
    if not dataset_exists:
        dataset_node = SHACLNode('dataset', title="New Dataset", description="Dataset description")
        editor.nodes[dataset_node.id] = dataset_node
        
    return render_template('index.html')

@app.route('/api/graph', methods=['GET'])
def get_graph():
    """Get the graph data for visualization"""
    nodes_data = []
    edges_data = []
    
    # Print debug info
    print(f"Fetching graph with {len(editor.nodes)} nodes and {len(editor.edges)} edges")
    
    # For edge debugging
    connection_counts = {}
    for node_id, node in editor.nodes.items():
        connection_counts[node_id] = len(node.connections)
    
    # Count the total connections
    total_connections = sum(connection_counts.values())
    print(f"Found {total_connections} connections across all nodes")
    
    # Process all nodes
    for node_id, node in editor.nodes.items():
        # Determine node color based on type
        color = '#99ccff'  # Default blue for concepts
        if node.type == 'dataset':
            color = '#ff9999'  # Light red for dataset
        elif node.type == 'class':
            color = '#99ff99'  # Light green for classes
            
        # Add node to nodes data
        # Get node type and publisher info
        node_type = 'Dataset'
        if node.type == 'class':
            node_type = 'Class'
        elif node.type == 'concept':
            # For concepts, get more specific type information
            if node.datatype:
                node_type = node.datatype.replace('xsd:', '')
            elif hasattr(node, 'i14y_data') and node.i14y_data:
                if isinstance(node.i14y_data, dict) and 'conceptValueType' in node.i14y_data:
                    node_type = node.i14y_data['conceptValueType']
                else:
                    node_type = 'Concept'
            else:
                node_type = 'Concept'
        
        # Get publisher info for I14Y concepts
        publisher = ''
        if hasattr(node, 'i14y_data') and node.i14y_data and isinstance(node.i14y_data, dict):
            if 'publisherName' in node.i14y_data:
                publisher_data = node.i14y_data['publisherName']
                if isinstance(publisher_data, dict):
                    # Try to get German name first, then fall back to others
                    publisher = (publisher_data.get('de') or 
                               publisher_data.get('en') or 
                               publisher_data.get('fr') or 
                               publisher_data.get('it') or 
                               '')
                else:
                    publisher = str(publisher_data)
            
            # Truncate publisher if too long
            if publisher and len(publisher) > 20:
                publisher = publisher[:18] + '...'
        
        # Truncate title if too long
        title = node.title
        if title and len(title) > 25:
            title = title[:23] + '...'
            
        # Create node label with title and publisher (if available) - using plain text
        node_label = title
        # Type information removed as requested
        if publisher:
            node_label += f"\nFrom: {publisher}"
            
        nodes_data.append({
            'id': node_id,
            'label': node_label,
            'title': node.title,  # Store the title separately for reference
            'description': node.description,  # Include the full description for hover
            'publisher': publisher,  # Include publisher for tooltip
            'color': color,
            'type': node.type,
            'selected': False  # By default, no node is selected
        })
    
    # Process edges from the edge storage system
    for edge_id, edge_data in editor.edges.items():
        edges_data.append({
            'id': edge_id,
            'from': edge_data['from'],
            'to': edge_data['to'],
            'label': edge_data.get('cardinality', '1..1'),
            'cardinality': edge_data.get('cardinality', '1..1')
        })
    
    # For backward compatibility, also process node connections that might not be in edges yet
    for node_id, node in editor.nodes.items():
        for conn_id in node.connections:
            if conn_id in editor.nodes:
                edge_id = f"{node_id}-{conn_id}"
                # Only add if not already in edges_data
                if not any(e['id'] == edge_id for e in edges_data):
                    # Create edge in the new system
                    editor.create_edge(node_id, conn_id, '1..1')
                    edges_data.append({
                        'id': edge_id,
                        'from': node_id,
                        'to': conn_id,
                        'label': '1..1',
                        'cardinality': '1..1'
                    })
    
    # Return the graph data
    return jsonify({
        'nodes': nodes_data,
        'edges': edges_data,
        'nodeCount': len(nodes_data),
        'edgeCount': len(edges_data)
    })

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """Get all nodes in the graph"""
    return jsonify(editor.get_all_nodes())

@app.route('/api/nodes', methods=['POST'])
def add_node():
    """Add a new node to the graph"""
    data = request.json
    node_type = data.get('type')
    title = data.get('title')
    description = data.get('description', '')
    parent_id = data.get('parent_id')
    
    if not node_type or not title:
        return jsonify({"error": "Node type and title are required"}), 400
    
    # Create the node
    node = SHACLNode(node_type, title=title, description=description)
    editor.nodes[node.id] = node
    
    # Connect to parent if specified
    if parent_id and parent_id in editor.nodes:
        # Add to connections sets
        editor.nodes[parent_id].connections.add(node.id)
        node.connections.add(parent_id)
        
        # Create an edge in the edge dictionary
        edge_id = f"{parent_id}-{node.id}"
        editor.edges[edge_id] = {
            'id': edge_id,
            'from': parent_id,
            'to': node.id,
            'cardinality': '1..1'
        }
        print(f"Created edge from {parent_id} to {node.id}")
    else:
        # If no parent specified, connect to dataset node
        dataset_node = None
        for n_id, n in editor.nodes.items():
            if n.type == 'dataset':
                dataset_node = n
                break
        
        if dataset_node:
            # Add to connections sets
            dataset_node.connections.add(node.id)
            node.connections.add(dataset_node.id)
            
            # Create an edge in the edge dictionary
            edge_id = f"{dataset_node.id}-{node.id}"
            editor.edges[edge_id] = {
                'id': edge_id,
                'from': dataset_node.id,
                'to': node.id,
                'cardinality': '1..1'
            }
            print(f"Created edge from {dataset_node.id} to {node.id}")
    
    return jsonify({"success": True, "node_id": node.id})

@app.route('/api/nodes/<node_id>/select', methods=['POST'])
def select_node(node_id):
    """Select a node in the graph"""
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    # Clear selection from all other nodes (if needed)
    # This is handled in the frontend, so nothing to do here
    
    return jsonify({"success": True})

@app.route('/api/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """Get details for a specific node"""
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    node = editor.nodes[node_id]
    return jsonify({
        'id': node.id,
        'type': node.type,
        'title': node.title,
        'description': node.description,
        'i14y_id': node.i14y_id,
        'i14y_data': node.i14y_data,
        'i14y_concept_uri': node.i14y_concept_uri,
        'i14y_dataset_uri': node.i14y_dataset_uri,
        'min_count': node.min_count,
        'max_count': node.max_count,
        'min_length': node.min_length, 
        'max_length': node.max_length,
        'pattern': node.pattern,
        'in_values': node.in_values,
        'node_reference': node.node_reference,
        'range': node.range,
        'datatype': node.datatype
    })

@app.route('/api/nodes/<node_id>/constraints', methods=['POST'])
def update_constraints(node_id):
    """Update constraints for a node"""
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    node = editor.nodes[node_id]
    data = request.json
    
    # Update constraint fields
    if 'min_count' in data and data['min_count']:
        try:
            node.min_count = int(data['min_count'])
        except ValueError:
            node.min_count = None
    else:
        node.min_count = None
        
    if 'max_count' in data and data['max_count']:
        try:
            node.max_count = int(data['max_count'])
        except ValueError:
            node.max_count = None
    else:
        node.max_count = None
        
    if 'min_length' in data and data['min_length']:
        try:
            node.min_length = int(data['min_length'])
        except ValueError:
            node.min_length = None
    else:
        node.min_length = None
        
    if 'max_length' in data and data['max_length']:
        try:
            node.max_length = int(data['max_length'])
        except ValueError:
            node.max_length = None
    else:
        node.max_length = None
        
    node.pattern = data.get('pattern', '').strip() or None
    
    # Handle in_values as comma-separated list
    in_values_text = data.get('in_values', '').strip()
    if in_values_text:
        node.in_values = [v.strip() for v in in_values_text.split(',') if v.strip()]
    else:
        node.in_values = []
        
    node.node_reference = data.get('node_reference', '').strip() or None
    node.range = data.get('range', '').strip() or None
    node.datatype = data.get('datatype', '').strip() or "xsd:string"
    
    return jsonify({"success": True})

@app.route('/api/nodes/<node_id>', methods=['PUT'])
def update_node(node_id):
    """Update a node"""
    node_data = request.json
    result = editor.update_node(node_id, node_data)
    if result:
        return jsonify(result)
    return jsonify({"error": "Node not found"}), 404

@app.route('/api/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    """Delete a node"""
    success = editor.delete_node(node_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Node not found"}), 404

@app.route('/api/connections', methods=['POST'])
def create_connection():
    """Create a connection between nodes"""
    data = request.json
    node1_id = data.get('node1_id')
    node2_id = data.get('node2_id')
    cardinality = data.get('cardinality', '1..1')  # Default cardinality
    
    if not node1_id or not node2_id:
        return jsonify({"error": "Both node IDs are required"}), 400
        
    if node1_id not in editor.nodes or node2_id not in editor.nodes:
        return jsonify({"error": "One or both nodes not found"}), 404
        
    # Create bidirectional connection in the nodes (for backward compatibility)
    editor.nodes[node1_id].connections.add(node2_id)
    editor.nodes[node2_id].connections.add(node1_id)
    
    # Create edge with cardinality
    editor.create_edge(node1_id, node2_id, cardinality)
    
    return jsonify({"success": True})

@app.route('/api/connections', methods=['DELETE'])
def delete_connection():
    """Delete a connection between nodes"""
    data = request.json
    node1_id = data.get('node1_id')
    node2_id = data.get('node2_id')
    
    if not node1_id or not node2_id:
        return jsonify({"error": "Both node IDs are required"}), 400
        
    if node1_id not in editor.nodes or node2_id not in editor.nodes:
        return jsonify({"error": "One or both nodes not found"}), 404
        
    # Remove bidirectional connection
    if node2_id in editor.nodes[node1_id].connections:
        editor.nodes[node1_id].connections.remove(node2_id)
    if node1_id in editor.nodes[node2_id].connections:
        editor.nodes[node2_id].connections.remove(node1_id)
    
    # Remove edges
    edge_id1 = f"{node1_id}-{node2_id}"
    edge_id2 = f"{node2_id}-{node1_id}"
    editor.delete_edge(edge_id1)
    editor.delete_edge(edge_id2)
    
    return jsonify({"success": True})

@app.route('/api/edges/<edge_id>', methods=['GET'])
def get_edge(edge_id):
    """Get edge details by ID"""
    edge = editor.get_edge(edge_id)
    if edge:
        return jsonify(edge)
    return jsonify({"error": "Edge not found"}), 404

@app.route('/api/edges/<edge_id>/cardinality', methods=['POST'])
def update_edge_cardinality(edge_id):
    """Update the cardinality of an edge"""
    data = request.json
    cardinality = data.get('cardinality')
    
    if not cardinality:
        return jsonify({"error": "Cardinality is required"}), 400
        
    success = editor.update_edge_cardinality(edge_id, cardinality)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Edge not found"}), 404

@app.route('/api/connect', methods=['POST'])
def connect_nodes():
    """Connect two nodes"""
    data = request.json
    source_id = data.get('source')
    target_id = data.get('target')
    
    if not source_id or not target_id:
        return jsonify({"error": "Source and target IDs are required"}), 400
        
    success = editor.connect_nodes(source_id, target_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to connect nodes"}), 400

@app.route('/api/disconnect', methods=['POST'])
def disconnect_nodes():
    """Disconnect two nodes"""
    data = request.json
    source_id = data.get('source')
    target_id = data.get('target')
    
    if not source_id or not target_id:
        return jsonify({"error": "Source and target IDs are required"}), 400
        
    success = editor.disconnect_nodes(source_id, target_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to disconnect nodes"}), 400

@app.route('/api/generate-ttl', methods=['GET'])
def generate_ttl():
    """Generate TTL for the graph"""
    ttl = editor.generate_ttl()
    return jsonify({"ttl": ttl})

@app.route('/api/download-ttl', methods=['GET'])
def download_ttl():
    """Download the graph as a TTL file"""
    ttl = editor.generate_ttl()
    
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix='.ttl')
    with os.fdopen(fd, 'w') as tmp:
        tmp.write(ttl)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(path, as_attachment=True, download_name=f"shacl_model_{timestamp}.ttl")

@app.route('/api/save', methods=['POST'])
def save_graph():
    """Save the graph to a file"""
    filename = request.json.get('filename', f"shacl_graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    # Ensure the data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Save to the data directory
    filepath = os.path.join('data', filename)
    success = editor.save_to_file(filepath)
    
    if success:
        return jsonify({"success": True, "filename": filename})
    return jsonify({"error": "Failed to save graph"}), 500

@app.route('/api/load', methods=['POST'])
def load_graph():
    """Load a graph from a file"""
    filename = request.json.get('filename')
    
    if not filename:
        return jsonify({"error": "Filename is required"}), 400
        
    filepath = os.path.join('data', filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
        
    success = editor.load_from_file(filepath)
    
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to load graph"}), 500

@app.route('/api/project/save', methods=['POST'])
def save_project():
    """Save the current project to a file for download"""
    try:
        # Prepare project data
        project_data = {
            "nodes": {node_id: node.to_dict() for node_id, node in editor.nodes.items()},
            "edges": editor.edges,
            "timestamp": datetime.now().isoformat()
        }
        
        # Convert to JSON
        project_json = json.dumps(project_data, indent=2)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            tmp.write(project_json.encode('utf-8'))
            tmp_path = tmp.name
        
        # Return file for download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=f"shacl_project_{timestamp}.json",
            mimetype='application/json'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/project/load', methods=['POST'])
def load_project():
    """Load a project from uploaded file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only JSON files are supported"}), 400
    
    try:
        # Read file content
        content = file.read().decode('utf-8')
        project_data = json.loads(content)
        
        print(f"Loading project - data keys: {project_data.keys()}")
        
        # Clear existing nodes and edges
        editor.nodes.clear()
        editor.edges.clear()
        
        # Load nodes
        node_count = len(project_data.get("nodes", {}))
        print(f"Loading {node_count} nodes from project")
        for node_id, node_data in project_data.get("nodes", {}).items():
            editor.nodes[node_id] = SHACLNode.from_dict(node_data)
        
        # Load edges if available in the project data
        edge_count = 0
        if "edges" in project_data:
            edges_data = project_data.get("edges", {})
            edge_count = len(edges_data)
            print(f"Loading {edge_count} edges from project data")
            editor.edges = edges_data
        else:
            print("No edges found in project data - will generate from node connections")
        
        # Generate edges from node connections for backward compatibility
        conn_edges_added = 0
        for node_id, node in editor.nodes.items():
            for conn_id in node.connections:
                if conn_id in editor.nodes:
                    edge_id = f"{node_id}-{conn_id}"
                    # Only add if not already in edges
                    if edge_id not in editor.edges:
                        editor.create_edge(node_id, conn_id, '1..1')
                        conn_edges_added += 1
        
        if conn_edges_added > 0:
            print(f"Created {conn_edges_added} additional edges from node connections")
        
        print(f"Project loaded: {node_count} nodes and {edge_count + conn_edges_added} total edges")
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error loading project: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all saved graph files"""
    os.makedirs('data', exist_ok=True)
    files = [f for f in os.listdir('data') if f.endswith('.json')]
    return jsonify({"files": files})

@app.route('/api/project/new', methods=['POST'])
def new_project():
    """Create a new empty structure"""
    try:
        print("API: Creating new project structure")
        
        # Reset the structure
        result = editor.reset_structure()
        
        if result:
            # Double-check that the reset worked
            node_count = len(editor.nodes)
            edge_count = len(editor.edges)
            print(f"New project created: {node_count} nodes, {edge_count} edges")
            
            # There should be exactly 1 node (the dataset) and 0 edges
            if node_count == 1 and edge_count == 0:
                return jsonify({
                    "success": True,
                    "message": "New structure created successfully",
                    "nodeCount": node_count,
                    "edgeCount": edge_count
                })
            else:
                print(f"WARNING: Unexpected node/edge count after reset: {node_count} nodes, {edge_count} edges")
                return jsonify({
                    "success": True,
                    "message": "Structure reset, but with unexpected counts",
                    "nodeCount": node_count,
                    "edgeCount": edge_count
                })
        else:
            return jsonify({"error": "Failed to create new structure"}), 500
    except Exception as e:
        print(f"Error creating new project: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/new-structure', methods=['GET'])
def new_structure_page():
    """Create a new structure and redirect to home page"""
    try:
        # Reset the structure
        editor.reset_structure()
        # Redirect to the home page
        return redirect('/')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/i14y/search', methods=['GET'])
def search_i14y():
    """Search for concepts in I14Y"""
    print("=== API: Received request to search I14Y concepts ===")
    
    query = request.args.get('query', '') or request.args.get('q', '')
    print(f"Search query: '{query}'")
    
    # Safely parse page and page_size parameters
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
        
    try:
        page_size = int(request.args.get('page_size', 20))
    except (ValueError, TypeError):
        page_size = 20
    
    print(f"Search parameters: page={page}, page_size={page_size}")
    
    if not query:
        print("Empty query, returning empty results")
        # Return empty results
        return jsonify({"concepts": []})
    
    try:
        # Use I14Y client to search for concepts
        print(f"Searching for concepts with query: '{query}'")
        results = editor.i14y_client.search_concepts(query, page, page_size)
        print(f"Found {len(results)} concepts")
        if results:
            print(f"First result: {results[0].get('title') if results[0] else None}")
        return jsonify({"concepts": results})
    except Exception as e:
        print(f"Error searching I14Y concepts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "concepts": []}), 500

@app.route('/api/i14y/dataset/search', methods=['GET'])
def search_i14y_datasets():
    """Search for datasets in I14Y"""
    print("=== API: Received request to search I14Y datasets ===")
    
    query = request.args.get('query', '') or request.args.get('q', '')
    print(f"Search query: '{query}'")
    
    # Safely parse page and page_size parameters
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
        
    try:
        page_size = int(request.args.get('page_size', 20))
    except (ValueError, TypeError):
        page_size = 20
    
    print(f"Search parameters: page={page}, page_size={page_size}")
    
    if not query:
        print("Empty query, returning empty results")
        # Return empty results
        return jsonify({"datasets": []})
    
    try:
        # Use I14Y client to search for datasets
        print(f"Searching for datasets with query: '{query}'")
        results = editor.i14y_client.search_datasets(query, page, page_size)
        print(f"Found {len(results)} datasets")
        if results:
            print(f"First result: {results[0].get('title') if results[0] else None}")
        return jsonify({"datasets": results})
    except Exception as e:
        print(f"Error searching I14Y datasets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "datasets": []}), 500

@app.route('/api/i14y/dataset/link', methods=['POST'])
def link_i14y_dataset():
    """Link an I14Y dataset to the current dataset node"""
    print("=== API: Received request to link I14Y dataset ===")
    
    if not request.is_json:
        print("ERROR: Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400
    
    # Get the JSON data
    data = request.json
    print(f"Request data: {data.keys() if data else 'None'}")
    
    dataset_id = data.get('dataset_id')
    dataset_data = data.get('dataset_data')
    
    # Validate dataset data
    if not dataset_id or not dataset_data:
        print("ERROR: Missing dataset_id or dataset_data in request")
        return jsonify({"error": "Dataset ID and data are required"}), 400
    
    print(f"Dataset ID: {dataset_id}")
    print(f"Dataset data: {dataset_data.keys() if isinstance(dataset_data, dict) else 'not a dict'}")
    
    try:
        # Find the dataset node
        dataset_node = None
        for node_id, node in editor.nodes.items():
            if node.type == 'dataset':
                dataset_node = node
                break
        
        if not dataset_node:
            print("ERROR: No dataset node found")
            return jsonify({"error": "No dataset node found"}), 404
        
        # Update the dataset node with I14Y information
        if 'title' in dataset_data:
            if isinstance(dataset_data['title'], dict):
                # Handle multilingual titles
                title = (dataset_data['title'].get('de') or 
                         dataset_data['title'].get('en') or 
                         dataset_data['title'].get('fr') or 
                         dataset_data['title'].get('it') or 
                         'Unknown Dataset')
                dataset_node.title = title
            else:
                dataset_node.title = dataset_data.get('title', '')
                
        if 'description' in dataset_data:
            if isinstance(dataset_data['description'], dict):
                # Handle multilingual descriptions
                description = (dataset_data['description'].get('de') or 
                              dataset_data['description'].get('en') or 
                              dataset_data['description'].get('fr') or 
                              dataset_data['description'].get('it') or 
                              '')
                dataset_node.description = description
            else:
                dataset_node.description = dataset_data.get('description', '')
        
        # Set the I14Y ID for the dataset
        dataset_node.i14y_id = dataset_id
        
        # Set the I14Y dataset URI
        dataset_node.i14y_dataset_uri = f"https://www.i14y.admin.ch/catalog/datasets/{dataset_id}/description"
        
        print(f"Successfully linked dataset: {dataset_node.title} (ID: {dataset_id})")
        
        return jsonify({
            "success": True,
            "node": {
                "id": dataset_node.id,
                "title": dataset_node.title,
                "description": dataset_node.description,
                "i14y_id": dataset_node.i14y_id,
                "i14y_dataset_uri": dataset_node.i14y_dataset_uri
            }
        })
    except Exception as e:
        print(f"Error linking I14Y dataset: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/i14y/dataset/disconnect', methods=['POST'])
def disconnect_i14y_dataset():
    """Disconnect an I14Y dataset from the current dataset node"""
    print("=== API: Received request to disconnect I14Y dataset ===")
    
    try:
        # Find the dataset node
        dataset_node = None
        for node_id, node in editor.nodes.items():
            if node.type == 'dataset':
                dataset_node = node
                break
        
        if not dataset_node:
            print("ERROR: No dataset node found")
            return jsonify({"error": "No dataset node found"}), 404
        
        # Check if dataset is actually connected to I14Y
        if not dataset_node.i14y_id and not dataset_node.i14y_dataset_uri:
            print("WARNING: Dataset is not connected to I14Y")
            return jsonify({"success": False, "message": "Dataset is not connected to I14Y"}), 400
        
        # Reset I14Y specific fields
        original_title = dataset_node.title
        original_description = dataset_node.description
        
        dataset_node.i14y_id = None
        dataset_node.i14y_dataset_uri = None
        # Keep the title and description as they were
        
        print(f"Successfully disconnected dataset: {original_title}")
        
        return jsonify({
            "success": True,
            "node": {
                "id": dataset_node.id,
                "title": dataset_node.title,
                "description": dataset_node.description,
                "i14y_id": None,
                "i14y_dataset_uri": None
            }
        })
    except Exception as e:
        print(f"Error disconnecting I14Y dataset: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
        # Create a concept node from I14Y data
        concept_node = SHACLNode('concept')
        concept_node.set_i14y_concept(concept_data)
        
        print(f"Created node with ID: {concept_node.id}, title: {concept_node.title}")
        
        # Add to nodes
        editor.nodes[concept_node.id] = concept_node
        print(f"Added node to editor, total nodes: {len(editor.nodes)}")
        
        # Connect to parent if specified
        if parent_id and parent_id in editor.nodes:
            # Add to connections sets
            editor.nodes[parent_id].connections.add(concept_node.id)
            concept_node.connections.add(parent_id)
            
            # Create an edge in the edge dictionary
            edge_id = f"{parent_id}-{concept_node.id}"
            editor.edges[edge_id] = {
                'id': edge_id,
                'from': parent_id,
                'to': concept_node.id,
                'cardinality': '1..1'
            }
            print(f"Created edge from {parent_id} to {concept_node.id}")
        else:
            # If no parent specified, connect to dataset node
            dataset_node = None
            for n_id, n in editor.nodes.items():
                if n.type == 'dataset':
                    dataset_node = n
                    break
            
            if dataset_node:
                # Add to connections sets
                dataset_node.connections.add(concept_node.id)
                concept_node.connections.add(dataset_node.id)
                
                # Create an edge in the edge dictionary
                edge_id = f"{dataset_node.id}-{concept_node.id}"
                editor.edges[edge_id] = {
                    'id': edge_id,
                    'from': dataset_node.id,
                    'to': concept_node.id,
                    'cardinality': '1..1'
                }
                print(f"Created edge from {dataset_node.id} to {concept_node.id}")
        
        print(f"Successfully added concept node with ID: {concept_node.id}")
        return jsonify({"success": True, "node_id": concept_node.id})
    except Exception as e:
        print(f"ERROR adding I14Y concept: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/export/ttl', methods=['GET'])
def export_ttl():
    """Export the graph as TTL"""
    try:
        # Generate TTL
        ttl_content = generate_full_ttl(editor.nodes, editor.base_uri)
        
        # Determine filename based on dataset information
        filename = request.args.get('filename', None)
        
        if not filename:
            # Try to get filename from dataset information
            dataset_node = None
            for node in editor.nodes.values():
                if node.type == 'dataset':
                    dataset_node = node
                    break
            
            if dataset_node:
                # Use dataset identifier if available
                if hasattr(dataset_node, 'identifier') and dataset_node.identifier and dataset_node.identifier.strip():
                    filename = dataset_node.identifier.strip() + '.ttl'
                # Fall back to dataset title if no identifier
                elif hasattr(dataset_node, 'title') and dataset_node.title and dataset_node.title.strip():
                    # Sanitize title for use as filename
                    sanitized_title = dataset_node.title.strip()
                    # Replace invalid filename characters
                    import re
                    sanitized_title = re.sub(r'[^a-zA-Z0-9\-_]', '_', sanitized_title)
                    sanitized_title = re.sub(r'_+', '_', sanitized_title)
                    sanitized_title = sanitized_title.strip('_')
                    filename = sanitized_title + '.ttl'
            
            # Default fallback
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"shacl_export_{timestamp}.ttl"
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.ttl', delete=False) as tmp:
            tmp.write(ttl_content.encode('utf-8'))
            tmp_path = tmp.name
        
        # Return file for download with dynamic filename
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/turtle'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/i14y/schemes', methods=['GET'])
def get_schemes():
    """Get all concept schemes from I14Y"""
    try:
        # Check if the method exists in the client
        if hasattr(editor.i14y_client, 'get_concept_schemes'):
            schemes = editor.i14y_client.get_concept_schemes()
            return jsonify({"schemes": schemes})
        else:
            # Return empty list if method doesn't exist
            return jsonify({"schemes": [], "message": "Concept scheme retrieval not implemented"})
    except Exception as e:
        return jsonify({"error": str(e), "schemes": []}), 500

@app.route('/api/i14y/concept/<concept_id>', methods=['GET'])
def get_i14y_concept(concept_id):
    """Get details of a specific I14Y concept by ID"""
    print(f"=== API: Received request to get I14Y concept with ID: {concept_id} ===")
    
    try:
        concept_data = editor.i14y_client.get_concept_details(concept_id)
        if concept_data:
            print(f"Found concept: {concept_data.get('title', {}).get('de', 'Unknown')}")
            return jsonify({"success": True, "concept": concept_data})
        else:
            print(f"Concept not found with ID: {concept_id}")
            # Return a 404 status code to indicate the concept was not found
            return jsonify({
                "success": False, 
                "error": "Concept not found",
                "message": "The concept could not be found via the I14Y API. This may be due to an invalid ID or API changes."
            }), 404
    except Exception as e:
        print(f"Error getting I14Y concept: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False, 
            "error": str(e),
            "message": "There was an error fetching the concept from the I14Y API."
        }), 500

@app.route('/api/i14y/add', methods=['POST'])
def add_i14y_concept():
    """Add an I14Y concept to the graph"""
    print("=== API: Received request to add I14Y concept ===")
    
    if not request.is_json:
        print("ERROR: Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400
    
    # Get the JSON data
    data = request.json
    print(f"Request data: {data.keys() if data else 'None'}")
    
    concept_data = data.get('concept_data')
    parent_id = data.get('parent_id')
    
    # Validate concept data
    if not concept_data:
        print("ERROR: Missing concept_data in request")
        return jsonify({"error": "Concept data is required"}), 400
    
    print(f"Concept data: {concept_data.keys() if isinstance(concept_data, dict) else 'not a dict'}")
    print(f"Parent ID: {parent_id}")
    
    try:
        # Create a concept node from I14Y data
        concept_node = SHACLNode('concept')
        concept_node.set_i14y_concept(concept_data)
        
        print(f"Created node with ID: {concept_node.id}, title: {concept_node.title}")
        
        # Add to nodes
        editor.nodes[concept_node.id] = concept_node
        print(f"Added node to editor, total nodes: {len(editor.nodes)}")
        
        # Connect to parent if specified
        if parent_id and parent_id in editor.nodes:
            # Add to connections sets
            editor.nodes[parent_id].connections.add(concept_node.id)
            concept_node.connections.add(parent_id)
            
            # Create an edge in the edge dictionary
            edge_id = f"{parent_id}-{concept_node.id}"
            editor.edges[edge_id] = {
                'id': edge_id,
                'from': parent_id,
                'to': concept_node.id,
                'cardinality': '1..1'
            }
            print(f"Created edge from {parent_id} to {concept_node.id}")
        else:
            # If no parent specified, connect to dataset node
            dataset_node = None
            for n_id, n in editor.nodes.items():
                if n.type == 'dataset':
                    dataset_node = n
                    break
            
            if dataset_node:
                # Add to connections sets
                dataset_node.connections.add(concept_node.id)
                concept_node.connections.add(dataset_node.id)
                
                # Create an edge in the edge dictionary
                edge_id = f"{dataset_node.id}-{concept_node.id}"
                editor.edges[edge_id] = {
                    'id': edge_id,
                    'from': dataset_node.id,
                    'to': concept_node.id,
                    'cardinality': '1..1'
                }
                print(f"Created edge from {dataset_node.id} to {concept_node.id}")
        
        print(f"Successfully added concept node with ID: {concept_node.id}")
        return jsonify({"success": True, "node_id": concept_node.id})
    except Exception as e:
        print(f"ERROR adding I14Y concept: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/dataset', methods=['GET', 'POST'])
def handle_dataset():
    """Get or update dataset information"""
    # Find the dataset node
    dataset_node = None
    for node_id, node in editor.nodes.items():
        if node.type == 'dataset':
            dataset_node = node
            break
    
    # If no dataset node exists, create one
    if not dataset_node:
        dataset_node = SHACLNode('dataset', title="New Dataset", description="Dataset description")
        editor.nodes[dataset_node.id] = dataset_node
    
    if request.method == 'POST':
        # Update dataset information
        data = request.json
        if 'title' in data:
            dataset_node.title = data['title']
        if 'description' in data:
            dataset_node.description = data['description']
        return jsonify({'success': True})
    else:
        # Return dataset information
        return jsonify({
            'title': dataset_node.title,
            'description': dataset_node.description
        })

def parse_ttl_to_nodes(g: Graph, editor) -> bool:
    """Parse RDF graph back to SHACLNode objects"""
    try:
        from rdflib.namespace import DCTERMS
        
        # Define namespaces
        SH = Namespace("http://www.w3.org/ns/shacl#")
        
        # Find NodeShapes (classes and dataset)
        node_shapes = list(g.subjects(RDF.type, SH.NodeShape))
        dataset_node = None
        created_nodes = {}
        
        print(f"Found {len(node_shapes)} NodeShapes")
        
        # First pass: Create dataset and class nodes
        for shape in node_shapes:
            # Get basic properties
            titles = list(g.objects(shape, DCTERMS.title))
            labels = list(g.objects(shape, SH.name)) or list(g.objects(shape, RDFS.label))
            descriptions = list(g.objects(shape, DCTERMS.description)) or list(g.objects(shape, SH.description))
            
            # Extract title (prefer German, fallback to any language)
            title = ""
            if titles:
                for t in titles:
                    if hasattr(t, 'language') and t.language == 'de':
                        title = str(t)
                        break
                if not title and titles:
                    title = str(titles[0])
            elif labels:
                for l in labels:
                    if hasattr(l, 'language') and l.language == 'de':
                        title = str(l)
                        break
                if not title and labels:
                    title = str(labels[0])
            
            # Extract description
            description = ""
            if descriptions:
                for d in descriptions:
                    if hasattr(d, 'language') and d.language == 'de':
                        description = str(d)
                        break
                if not description and descriptions:
                    description = str(descriptions[0])
            
            if not title:
                title = str(shape).split('/')[-1].replace('#', '').replace('_', ' ')
            
            # Determine if this is a dataset or class
            # Check if it has rdfs:Class type or if it's the main dataset shape
            is_class = (shape, RDF.type, RDFS.Class) in g
            
            # Create node
            node_id = str(uuid.uuid4())
            node_type = 'class' if is_class else 'dataset'
            
            if not dataset_node and node_type == 'dataset':
                dataset_node = node_id
            
            # Create SHACLNode
            node_data = {
                'id': node_id,
                'type': node_type,
                'title': title,
                'description': description
            }
            
            node = SHACLNode.from_dict(node_data)
            editor.nodes[node_id] = node
            created_nodes[str(shape)] = node_id
            
            print(f"Created {node_type}: {title}")
        
        # Second pass: Create concept nodes from PropertyShapes
        property_shapes = list(g.subjects(RDF.type, SH.PropertyShape))
        
        for prop_shape in property_shapes:
            # Skip if this is an object property (class-to-class relationship)
            if (prop_shape, RDF.type, OWL.ObjectProperty) in g:
                continue
                
            # Get property details
            titles = list(g.objects(prop_shape, DCTERMS.title))
            labels = list(g.objects(prop_shape, SH.name)) or list(g.objects(prop_shape, RDFS.label))
            descriptions = list(g.objects(prop_shape, DCTERMS.description)) or list(g.objects(prop_shape, SH.description))
            
            # Extract title
            title = ""
            if titles:
                for t in titles:
                    if hasattr(t, 'language') and t.language == 'de':
                        title = str(t)
                        break
                if not title and titles:
                    title = str(titles[0])
            elif labels:
                for l in labels:
                    if hasattr(l, 'language') and l.language == 'de':
                        title = str(l)
                        break
                if not title and labels:
                    title = str(labels[0])
            
            if not title:
                # Extract from path
                paths = list(g.objects(prop_shape, SH.path))
                if paths:
                    title = str(paths[0]).split('/')[-1].replace('#', '').replace('_', ' ')
                else:
                    title = str(prop_shape).split('/')[-1].replace('#', '').replace('_', ' ')
            
            # Extract description
            description = ""
            if descriptions:
                for d in descriptions:
                    if hasattr(d, 'language') and d.language == 'de':
                        description = str(d)
                        break
                if not description and descriptions:
                    description = str(descriptions[0])
            
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
            
            # Create concept node
            node_id = str(uuid.uuid4())
            node_data = {
                'id': node_id,
                'type': 'concept',
                'title': title,
                'description': description,
                'min_count': min_count,
                'max_count': max_count,
                'min_length': min_length,
                'max_length': max_length,
                'pattern': pattern,
                'datatype': datatype or 'xsd:string'
            }
            
            node = SHACLNode.from_dict(node_data)
            editor.nodes[node_id] = node
            created_nodes[str(prop_shape)] = node_id
            
            print(f"Created concept: {title}")
        
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
                    print(f"Connected {editor.nodes[shape_node_id].title} -> {editor.nodes[prop_node_id].title} ({cardinality})")
        
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
        print(f"Error parsing TTL: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/api/import/ttl', methods=['POST'])
def import_ttl():
    """Import SHACL schema from TTL file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file.filename.endswith('.ttl'):
        return jsonify({"error": "Only TTL files are supported"}), 400
    
    try:
        # Read file content
        content = file.read().decode('utf-8')
        
        # Parse TTL file using RDFLib
        g = Graph()
        g.parse(data=content, format='turtle')
        
        # Clear existing data
        editor.nodes.clear()
        editor.edges.clear()
        
        # Convert RDF graph back to SHACLNode objects
        success = parse_ttl_to_nodes(g, editor)
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to parse TTL structure"}), 400
            
    except Exception as e:
        print(f"Error importing TTL: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/import/example/ttl', methods=['GET'])
def import_example_ttl():
    """Import example TTL file"""
    try:
        # Load example TTL file
        example_file = os.path.join(os.path.dirname(__file__), 'working.ttl')
        
        if not os.path.exists(example_file):
            return jsonify({"error": "Example file not found"}), 404
        
        with open(example_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse TTL file using RDFLib
        g = Graph()
        g.parse(data=content, format='turtle')
        
        # TODO: Implement conversion from RDF graph to SHACLNode objects
        # This would require parsing the SHACL shapes and converting to our data model
        # For now, we'll just return success without doing anything
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/import/csv', methods=['POST'])
def import_csv():
    """Import a CSV file and convert to SHACL TTL"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are supported"}), 400
            
        # Get dataset name and language from form data
        dataset_name = request.form.get('dataset_name', os.path.splitext(file.filename)[0])
        lang = request.form.get('lang', 'de')
        
        print(f"Importing CSV file: {file.filename}, Dataset name: {dataset_name}, Language: {lang}")
        
        # Read CSV data
        csv_data = file.read().decode('utf-8-sig')
        
        # Convert to TTL
        ttl = csv_to_ttl(csv_data, dataset_name, lang)
        
        if not ttl:
            return jsonify({"error": "Failed to convert CSV to TTL"}), 500
            
        print(f"Successfully converted CSV to TTL. Size: {len(ttl)} bytes")
        
        # Process the TTL to extract data structure
        try:
            # Use RDFLib to parse the TTL
            g = Graph()
            g.parse(data=ttl, format='turtle')
            
            # Clear existing nodes except for the dataset node
            dataset_node = None
            nodes_to_remove = []
            
            for node_id, node in editor.nodes.items():
                if node.type == 'dataset':
                    dataset_node = node
                else:
                    nodes_to_remove.append(node_id)
            
            # Remove non-dataset nodes
            for node_id in nodes_to_remove:
                del editor.nodes[node_id]
            
            # Create or update dataset node with the provided name
            if dataset_node:
                dataset_node.title = dataset_name
                # Clear any existing connections
                dataset_node.connections = set()
            else:
                dataset_node = SHACLNode('dataset', title=dataset_name)
                editor.nodes[dataset_node.id] = dataset_node
            
            print(f"Using dataset node: {dataset_node.id} with title: {dataset_node.title}")
            
            # Find property shapes in the TTL
            # We're looking for triples with rdf:type sh:PropertyShape
            property_shapes = []
            for s, p, o in g.triples((None, RDF.type, SH.PropertyShape)):
                property_shapes.append(s)
            
            print(f"Found {len(property_shapes)} property shapes in TTL")
            
            # Process each property shape
            for prop_idx, shape in enumerate(property_shapes):
                # Get property name (from sh:name or the URI)
                prop_name = None
                for _, _, name in g.triples((shape, SH.name, None)):
                    prop_name = str(name)
                    break
                
                if not prop_name:
                    # Extract from URI
                    prop_name = str(shape).split('/')[-1]
                
                # Get datatype
                datatype = None
                for _, _, dt in g.triples((shape, SH.datatype, None)):
                    datatype = str(dt)
                    break
                
                # Create a concept node for this property
                concept_node = SHACLNode('concept', title=prop_name)
                concept_node.datatype = datatype or "xsd:string"
                
                # Add to nodes and connect to dataset
                editor.nodes[concept_node.id] = concept_node
                dataset_node.connections.add(concept_node.id)
                concept_node.connections.add(dataset_node.id)
                
                print(f"Created concept node {concept_node.id} for property {prop_name}")
                
                # Extract constraints
                # Min/Max Count
                for _, _, value in g.triples((shape, SH.minCount, None)):
                    try:
                        concept_node.min_count = int(value)
                    except (ValueError, TypeError):
                        pass
                
                for _, _, value in g.triples((shape, SH.maxCount, None)):
                    try:
                        concept_node.max_count = int(value)
                    except (ValueError, TypeError):
                        pass
                
                # Min/Max Length
                for _, _, value in g.triples((shape, SH.minLength, None)):
                    try:
                        concept_node.min_length = int(value)
                    except (ValueError, TypeError):
                        pass
                
                for _, _, value in g.triples((shape, SH.maxLength, None)):
                    try:
                        concept_node.max_length = int(value)
                    except (ValueError, TypeError):
                        pass
                
                # Pattern
                for _, _, value in g.triples((shape, SH.pattern, None)):
                    concept_node.pattern = str(value)
                
            print(f"Successfully processed TTL. Created {len(property_shapes)} concept nodes.")
        except Exception as e:
            import traceback
            print(f"Error processing TTL: {str(e)}")
            print(traceback.format_exc())
            # Continue with basic import even if advanced processing fails
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        print(f"Error importing CSV: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug', methods=['GET'])
def debug_api():
    """Debug endpoint to check app state"""
    # Count nodes by type
    node_counts = {
        'total': len(editor.nodes),
        'dataset': 0,
        'class': 0,
        'concept': 0
    }
    
    for node in editor.nodes.values():
        if node.type in node_counts:
            node_counts[node.type] += 1
    
    # Return basic app state info
    return jsonify({
        'nodes': node_counts,
        'nodes_list': [{'id': node_id, 'type': node.type, 'title': node.title} for node_id, node in editor.nodes.items()],
        'api_client': {
            'base_url': editor.i14y_client.base_url
        }
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5002))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print("Starting SHACL Editor Web Application...")
    print(f"Access the application at: http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=port, debug=debug)