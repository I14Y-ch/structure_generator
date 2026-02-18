#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify, send_file, redirect, session
from werkzeug.utils import secure_filename
import json
import os
import tempfile
import requests
import uuid
import threading
import time
import chardet
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import csv
import io
from pathlib import Path
from rdflib import Graph, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, XSD, SH, OWL, RDFS, DCTERMS

# Import CSV converter and XSD importer using relative imports if possible
try:
    from .csv_converter import csv_to_ttl
except ImportError:
    from csv_converter import csv_to_ttl
try:
    from .xsd_importer import xsd_to_ttl
except ImportError:
    from xsd_importer import xsd_to_ttl

class SessionManager:
    """Manages user sessions and automatic cleanup"""
    
    def __init__(self, session_timeout_hours=2, cleanup_interval_minutes=30):
        self.sessions = {}  # session_id -> FlaskSHACLGraphEditor
        self.session_timestamps = {}  # session_id -> last_activity_time
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self.cleanup_interval = cleanup_interval_minutes * 60  # Convert to seconds
        self.lock = threading.RLock()
        self.cleanup_thread = None
        self.start_cleanup_thread()
    
    def start_cleanup_thread(self):
        """Start the automatic cleanup thread"""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self.cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Background thread that periodically cleans up expired sessions"""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                self.cleanup_expired_sessions()
            except Exception as e:
                print(f"Error in session cleanup: {e}")
    
    def cleanup_expired_sessions(self):
        """Remove sessions that haven't been active for too long"""
        now = datetime.now()
        expired_sessions = []
        
        with self.lock:
            for session_id, last_activity in self.session_timestamps.items():
                if now - last_activity > self.session_timeout:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                if session_id in self.sessions:
                    print(f"Cleaning up expired session: {session_id}")
                    del self.sessions[session_id]
                    del self.session_timestamps[session_id]
        
        if expired_sessions:
            print(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_editor_for_session(self, session_id):
        """Get or create an editor for the given session"""
        with self.lock:
            # Update activity timestamp
            self.session_timestamps[session_id] = datetime.now()
            
            # Get or create editor for this session
            if session_id not in self.sessions:
                print(f"Creating new editor for session: {session_id}")
                # Create FlaskSHACLGraphEditor instance - class will be defined later
                self.sessions[session_id] = None  # Will be set when class is available
            
            return self.sessions[session_id]

class I14YAPIClient:
    """Client for interacting with I14Y API"""
    
    def __init__(self):
        self.base_url = "https://core.i14y.c.bfs.admin.ch/api/Catalog"
        
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
        self.type = node_type  # 'dataset', 'data_element', 'concept', 'class'
        self.title = title
        # Support both string and multilingual object descriptions
        if isinstance(description, dict):
            self.description = description
        else:
            # Convert legacy string descriptions to multilingual format
            self.description = {'de': description} if description else {}
        
        # I14Y integration
        self.i14y_id = None  # For concepts from I14Y (the concept UUID)
        self.i14y_data = None  # Full I14Y concept/dataset data
        self.i14y_concept_uri = None  # The I14Y concept URI
        self.i14y_dataset_uri = None  # The I14Y dataset URI
        
        # Data element specific properties
        self.local_name = None  # Local name for the data element (can differ from concept name)
        self.conforms_to_concept_uri = None  # dcterms:conformsTo link to underlying concept
        self.is_linked_to_concept = False  # Whether this data element is linked to an I14Y concept
        
        # Visualization properties
        self.position = {'x': 0.5, 'y': 0.5}  # Default position in graph layout
        
        # Graph structure
        self.connections = set()
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
        self.order = None  # sh:order for sorting in TTL export
        self.suggested_pattern = None
        self.suggested_in_values = None
        self.suggested_min_length = None
        self.suggested_max_length = None
    
    def create_data_element_from_concept(self, concept_node, local_name: str = None):
        """Create a data element from this concept node
        
        Args:
            concept_node: The concept node to base the data element on
            local_name: Optional local name for the data element (different from concept name)
        
        Returns:
            New data element node
        """
        if concept_node.type != 'concept':
            raise ValueError("Can only create data elements from concept nodes")
        
        # Create new data element
        data_element = SHACLNode('data_element')
        
        # Set local name from provided value or from concept
        # Keep the title distinct from local_name to allow custom titles
        if local_name:
            data_element.local_name = local_name
            data_element.title = local_name  # Start with local_name as title, but allow modification
        else:
            data_element.local_name = concept_node.title
            data_element.title = concept_node.title  # Start with concept title, but allow modification
            
        data_element.description = concept_node.description
        
        # Link to concept via conformsTo
        data_element.is_linked_to_concept = True
        data_element.conforms_to_concept_uri = concept_node.i14y_concept_uri or f"concept:{concept_node.id}"
        
        # Inherit constraints from concept
        data_element.datatype = concept_node.datatype
        data_element.min_length = concept_node.min_length
        data_element.max_length = concept_node.max_length
        data_element.pattern = concept_node.pattern
        data_element.in_values = concept_node.in_values.copy() if concept_node.in_values else []
        
        # Copy I14Y reference information (but not the direct link)
        if concept_node.i14y_data:
            data_element.i14y_data = concept_node.i14y_data.copy()
            
        return data_element
    
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
            # Store the full multilingual description object
            self.description = {
                lang: desc for lang, desc in desc_obj.items() 
                if lang in ['de', 'en', 'fr', 'it', 'rm'] and desc
            }
            # Ensure we have at least a German description as fallback
            if not self.description:
                self.description = {'de': ''}
        else:
            # Handle legacy string descriptions
            self.description = {'de': str(desc_obj)} if desc_obj else {'de': ''}
        
        # Set the concept URI for TTL export
        if self.i14y_id:
            self.i14y_concept_uri = f"https://www.i14y.admin.ch/de/catalog/concepts/{self.i14y_id}/description"
        
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
            # Store the full multilingual description object
            self.description = {
                lang: desc for lang, desc in desc_obj.items() 
                if lang in ['de', 'en', 'fr', 'it', 'rm'] and desc
            }
            # Ensure we have at least a German description as fallback
            if not self.description:
                self.description = {'de': ''}
        else:
            # Handle legacy string descriptions
            self.description = {'de': str(desc_obj)} if desc_obj else {'de': ''}
        
        # Set the dataset URI for references
        if self.i14y_id:
            self.i14y_dataset_uri = f"https://www.i14y.admin.ch/de/catalog/datasets/{self.i14y_id}/description"
    
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
        """Get multilingual descriptions, ensuring all supported languages are present"""
        if isinstance(self.description, dict):
            # Return the stored multilingual descriptions, filling in missing languages
            base_desc = (self.description.get('de') or 
                        self.description.get('en') or 
                        self.description.get('fr') or 
                        self.description.get('it') or 
                        self.description.get('rm') or 
                        '')
            return {
                'de': self.description.get('de', base_desc),
                'en': self.description.get('en', base_desc),
                'fr': self.description.get('fr', base_desc),
                'it': self.description.get('it', base_desc)
            }
        else:
            # Handle legacy string descriptions
            desc = self.description or ''
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
            'local_name': self.local_name,
            'conforms_to_concept_uri': self.conforms_to_concept_uri,
            'is_linked_to_concept': self.is_linked_to_concept,
            'connections': connections_list,
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
            'range': self.range,
            'order': self.order,
            'suggested_pattern': self.suggested_pattern,
            'suggested_in_values': self.suggested_in_values,
            'suggested_min_length': self.suggested_min_length,
            'suggested_max_length': self.suggested_max_length,
            # Visualization properties
            'position': self.position
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SHACLNode':
        node = cls(data['type'], data['id'], data['title'], data['description'])
        node.i14y_id = data.get('i14y_id')
        node.i14y_data = data.get('i14y_data')
        node.i14y_concept_uri = data.get('i14y_concept_uri')
        node.i14y_dataset_uri = data.get('i14y_dataset_uri')
        node.local_name = data.get('local_name')
        node.conforms_to_concept_uri = data.get('conforms_to_concept_uri')
        node.is_linked_to_concept = data.get('is_linked_to_concept', False)
        node.connections = set(data.get('connections', []))
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
        node.order = data.get('order')
        node.suggested_pattern = data.get('suggested_pattern')
        node.suggested_in_values = data.get('suggested_in_values')
        node.suggested_min_length = data.get('suggested_min_length')
        node.suggested_max_length = data.get('suggested_max_length')
        # Visualization properties
        node.position = data.get('position', {'x': 0.5, 'y': 0.5})
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
    
    # Generate a normalized dataset ID from title
    dataset_title_str = get_text_value(dataset_node.title, 'de')
    dataset_id = dataset_title_str.lower().replace(' ', '_').replace('-', '_')
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
        """Normalize a label (string or multilingual dict) to a valid ID"""
        # Extract text value if it's a multilingual dict
        if isinstance(label, dict):
            base = get_text_value(label, 'de')
        else:
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
    # Handle both string and multilingual dict formats
    if isinstance(dataset_node.title, dict):
        # Multilingual title - add all available languages
        for lang in ['de', 'fr', 'it', 'en']:
            if lang in dataset_node.title and dataset_node.title[lang]:
                title_text = sanitize_literal(dataset_node.title[lang])
                safe_add_multilingual_property(dataset_shape, DCTERMS.title, title_text, lang)
                safe_add_multilingual_property(dataset_shape, RDFS.label, title_text, lang)
    else:
        # Single language title
        ds_title = sanitize_literal(dataset_node.title)
        if ds_title:
            safe_add_multilingual_property(dataset_shape, DCTERMS.title, ds_title, 'de')
            safe_add_multilingual_property(dataset_shape, RDFS.label, ds_title, 'de')
    
    if isinstance(dataset_node.description, dict):
        # Multilingual description - add all available languages
        for lang in ['de', 'fr', 'it', 'en']:
            if lang in dataset_node.description and dataset_node.description[lang]:
                desc_text = sanitize_literal(dataset_node.description[lang])
                safe_add_multilingual_property(dataset_shape, DCTERMS.description, desc_text, lang)
                safe_add_multilingual_property(dataset_shape, RDFS.comment, desc_text, lang)
    else:
        # Single language description
        ds_desc = sanitize_literal(dataset_node.description)
        if ds_desc:
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
        class_id = norm_id(class_node.title)
        class_uri = URIRef(f"{i14y_ns}{class_id}")  # Use class name directly without "Type" suffix

        # Create NodeShape for the class
        g.add((class_uri, RDF.type, RDFS.Class))
        g.add((class_uri, RDF.type, SH.NodeShape))
        g.add((class_uri, SH.closed, Literal(True)))

        # Add class metadata with multilingual support
        if isinstance(class_node.title, dict):
            # Multilingual title
            for lang in ['de', 'fr', 'it', 'en']:
                if lang in class_node.title and class_node.title[lang]:
                    title_text = sanitize_literal(class_node.title[lang])
                    safe_add_multilingual_property(class_uri, SH.name, title_text, lang)
        else:
            class_title = sanitize_literal(class_node.title)
            if class_title:
                safe_add_multilingual_property(class_uri, SH.name, class_title, "en")

        if isinstance(class_node.description, dict):
            # Multilingual description
            for lang in ['de', 'fr', 'it', 'en']:
                if lang in class_node.description and class_node.description[lang]:
                    desc_text = sanitize_literal(class_node.description[lang])
                    safe_add_multilingual_property(class_uri, DCTERMS.description, desc_text, lang)
                    safe_add_multilingual_property(class_uri, RDFS.comment, desc_text, lang)
        else:
            class_desc = sanitize_literal(class_node.description)
            if class_desc:
                safe_add_multilingual_property(class_uri, DCTERMS.description, class_desc, "de")
                safe_add_multilingual_property(class_uri, RDFS.comment, class_desc, "de")

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

        # Create property shapes for data elements belonging to this class
        # Sort data elements by order field (if set), then by title
        class_data_elements_sorted = sorted(
            class_data_elements,
            key=lambda de: (de.order if de.order is not None else float('inf'), de.title)
        )
        
        for data_element in class_data_elements_sorted:
            element_id = norm_id(data_element.local_name or data_element.title)
            # Use the full I14Y URI pattern 
            property_uri = URIRef(f"{i14y_ns}{element_id}/{element_id}")

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

            # Add multilingual titles and descriptions using local_name and description
            element_title = data_element.title  # Use the custom title
            element_desc = data_element.description
            
            if element_title:
                safe_add_multilingual_property(property_uri, DCTERMS.title, element_title, "de")
                safe_add_multilingual_property(property_uri, RDFS.label, element_title, "de")
                safe_add_multilingual_property(property_uri, SH.name, element_title, "de")

            if element_desc:
                safe_add_multilingual_property(property_uri, DCTERMS.description, element_desc, "de")
                safe_add_multilingual_property(property_uri, RDFS.comment, element_desc, "de")
                safe_add_multilingual_property(property_uri, SH.description, element_desc, "de")

            class_property_uris.append(property_uri)

        # Add properties to the class NodeShape
        for property_uri in class_property_uris:
            g.add((class_uri, SH.property, property_uri))

        # Store for dataset reference creation
        class_properties[class_node.id] = class_uri

    # Add property references for concepts directly connected to dataset
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
        element_id = norm_id(data_element.local_name or data_element.title)
        # Use the full I14Y URI pattern with dataset_id path
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
        class_id = norm_id(class_node.title)
        class_uri = class_properties[class_node.id]
        # Create a property shape that references the class
        property_uri = URIRef(f"{i14y_ns}{dataset_id}/{class_id}")

        # Create PropertyShape for class
        g.add((property_uri, RDF.type, SH.PropertyShape))
        g.add((property_uri, RDF.type, OWL.ObjectProperty))
        g.add((property_uri, SH.path, property_uri))

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
                color = '#87CEFA'  # Light blue
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

        # Generate proper I14Y dataset ID - normalize
        raw_ds = get_text_value(dataset_node.title, 'de').strip() or "dataset"
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

        def norm_id(label) -> str:
            """Normalize a label (string or multilingual dict) to a valid ID"""
            # Extract text value if it's a multilingual dict
            if isinstance(label, dict):
                base = get_text_value(label, 'de')
            else:
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

        # Add dataset metadata with multilingual support
        if isinstance(dataset_node.title, dict):
            # Multilingual title - add all available languages
            for lang in ['de', 'fr', 'it', 'en']:
                if lang in dataset_node.title and dataset_node.title[lang]:
                    title_text = sanitize_literal(dataset_node.title[lang])
                    safe_add_multilingual_property(dataset_shape, DCTERMS.title, title_text, lang)
                    safe_add_multilingual_property(dataset_shape, RDFS.label, title_text, lang)
                    safe_add_multilingual_property(dataset_shape, SH.name, title_text, lang)
        else:
            # Single language title
            ds_title = sanitize_literal(dataset_node.title)
            if ds_title:
                safe_add_multilingual_property(dataset_shape, DCTERMS.title, ds_title, "de")
                safe_add_multilingual_property(dataset_shape, RDFS.label, ds_title, "de")
                safe_add_multilingual_property(dataset_shape, SH.name, ds_title, "de")

        if isinstance(dataset_node.description, dict):
            # Multilingual description - add all available languages
            for lang in ['de', 'fr', 'it', 'en']:
                if lang in dataset_node.description and dataset_node.description[lang]:
                    desc_text = sanitize_literal(dataset_node.description[lang])
                    safe_add_multilingual_property(dataset_shape, DCTERMS.description, desc_text, lang)
                    safe_add_multilingual_property(dataset_shape, RDFS.comment, desc_text, lang)
                    g.add((dataset_shape, SH.description, Literal(desc_text, lang=lang)))
        else:
            # Single language description
            ds_desc = sanitize_literal(dataset_node.description)
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

            # Link to the class NodeShape
            g.add((property_uri, SH.node, class_uri))

            # Add multilingual titles and descriptions
            titles = class_node.get_multilingual_title()
            descriptions = class_node.get_multilingual_description()

            # Ensure we always have at least a basic label
            # Handle both string and dict title formats
            if isinstance(class_node.title, dict):
                class_title = sanitize_literal(get_text_value(class_node.title, 'de'))
            else:
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

            # Add property shapes for classes connected to this class (class-to-class relationships)
            for connected_class in connected_class_classes:
                connected_class_id = norm_id(connected_class.title)
                connected_class_uri = URIRef(f"{i14y_ns}{connected_class_id}")
                class_ref_property_uri = URIRef(f"{i14y_ns}{class_id}_has_{connected_class_id}")

                # Create PropertyShape for the class reference
                g.add((class_ref_property_uri, RDF.type, SH.PropertyShape))
                g.add((class_ref_property_uri, RDF.type, OWL.ObjectProperty))
                g.add((class_ref_property_uri, SH.path, class_ref_property_uri))

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

            # Add to dataset properties
            g.add((dataset_shape, SH.property, property_uri))

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
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# Add the /api/reset endpoint
@app.route('/api/reset', methods=['POST'])
def reset_structure_api():
    """Reset the structure to a new empty one with just a dataset node"""
    editor = get_user_editor()
    try:
        print("API: Resetting project structure (via /api/reset)")
        result = editor.reset_structure()
        if result:
            node_count = len(editor.nodes)
            edge_count = len(editor.edges)
            print(f"Structure reset: {node_count} nodes, {edge_count} edges")
            return jsonify({
                "success": True,
                "message": "Structure reset successfully",
                "nodeCount": node_count,
                "edgeCount": edge_count
            })
        else:
            return jsonify({"error": "Failed to reset structure"}), 500
    except Exception as e:
        print(f"Error resetting structure: {str(e)}")
        return jsonify({"error": "Failed to reset structure"}), 500

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
            # Handle multilingual descriptions (dictionary) or simple string descriptions
            if isinstance(node_data['description'], dict):
                # Multilingual description - store as dictionary
                node.description = node_data['description']
            else:
                # Simple string description - store as string
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
        if 'local_name' in node_data:
            node.local_name = node_data['local_name'] if node_data['local_name'] else None
        if 'order' in node_data:
            # Convert to int if it's a valid number, otherwise set to None
            try:
                node.order = int(node_data['order']) if node_data['order'] not in [None, ''] else None
            except (ValueError, TypeError):
                node.order = None
            
        return {"success": True, "node": node.to_dict()}
    
    def delete_node(self, node_id):
        """Delete a node from the graph"""
        if node_id not in self.nodes:
            return False
        
        print(f"=== Deleting node {node_id} ===")
        
        # First, find and remove all edges connected to this node
        edges_to_delete = []
        for edge_id, edge in self.edges.items():
            if edge.get('from') == node_id or edge.get('to') == node_id:
                edges_to_delete.append(edge_id)
                print(f"Marking edge for deletion: {edge_id}")
        
        # Delete the edges
        for edge_id in edges_to_delete:
            del self.edges[edge_id]
            print(f"Deleted edge: {edge_id}")
        
        # Remove connections to this node from other nodes
        for other_id, node in self.nodes.items():
            if node_id in node.connections:
                node.connections.remove(node_id)
                print(f"Removed connection from node {other_id} to {node_id}")
        
        # Delete the node itself
        deleted_node = self.nodes[node_id]
        print(f"Deleting node: {deleted_node.type} - {deleted_node.title}")
        del self.nodes[node_id]
        
        print(f"Node {node_id} successfully deleted")
        print(f"Remaining nodes: {len(self.nodes)}")
        print(f"Remaining edges: {len(self.edges)}")
        
        return True
    
    def get_node(self, node_id):
        """Get a node by ID"""
        if node_id in self.nodes:
            return self.nodes[node_id].to_dict()
        return None
    
    def get_node_by_id(self, node_id):
        """Get the actual node object by ID"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self):
        """Get all nodes"""
        return {node_id: node.to_dict() for node_id, node in self.nodes.items()}
    
    def connect_nodes(self, source_id, target_id):
        """Connect two nodes"""
        # Verify both nodes exist
        if source_id not in self.nodes:
            print(f"ERROR: Source node {source_id} not found")
            return False
            
        if target_id not in self.nodes:
            print(f"ERROR: Target node {target_id} not found") 
            return False
            
        # Get the actual node objects
        source_node = self.nodes[source_id]
        target_node = self.nodes[target_id]
        
        print(f"Connecting: {source_node.type}({source_node.title}) → {target_node.type}({target_node.title})")
            
        # Add to connections set - bidirectional connection
        source_node.connections.add(target_id)
        target_node.connections.add(source_id)  # Add reverse connection
        
        # Create an edge in the edge dictionary
        edge_id = f"{source_id}-{target_id}"
        self.edges[edge_id] = {
            'id': edge_id,
            'from': source_id,
            'to': target_id,
            'cardinality': '1..1'
        }
        
        print(f"Successfully connected nodes: {source_id} -> {target_id}")
        print(f"Node {source_id} now has {len(source_node.connections)} connections")
        print(f"Node {target_id} now has {len(target_node.connections)} connections")
        return True
    
    def disconnect_nodes(self, source_id, target_id):
        """Disconnect two nodes"""
        # Verify both nodes exist
        if source_id not in self.nodes:
            print(f"ERROR: Source node {source_id} not found")
            return False
            
        if target_id not in self.nodes:
            print(f"ERROR: Target node {target_id} not found")
            return False
        
        # Get the actual node objects
        source_node = self.nodes[source_id]
        target_node = self.nodes[target_id]
        
        print(f"Disconnecting: {source_node.type}({source_node.title}) ← → {target_node.type}({target_node.title})")
        
        # Remove from connections set - both directions
        if target_id in source_node.connections:
            source_node.connections.remove(target_id)
            print(f"Removed {target_id} from {source_id}'s connections")
        else:
            print(f"Warning: {target_id} not found in {source_id}'s connections")
        
        if source_id in target_node.connections:
            target_node.connections.remove(source_id)
            print(f"Removed {source_id} from {target_id}'s connections")
        else:
            print(f"Warning: {source_id} not found in {target_id}'s connections")
        
        # Remove edge from edge dictionary
        edge_id = f"{source_id}-{target_id}"
        if edge_id in self.edges:
            del self.edges[edge_id]
            print(f"Removed edge {edge_id}")
        
        # Also check for reverse edge
        reverse_edge_id = f"{target_id}-{source_id}"
        if reverse_edge_id in self.edges:
            del self.edges[reverse_edge_id]
            print(f"Removed reverse edge {reverse_edge_id}")
            
        print(f"Node {source_id} now has {len(source_node.connections)} connections")
        print(f"Node {target_id} now has {len(target_node.connections)} connections")
        return True
            
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
    
    def create_edge(self, node1_id, node2_id, cardinality="1..1", order=None):
        """Create an edge between two nodes with cardinality and optional order"""
        edge_id = f"{node1_id}-{node2_id}"
        reverse_edge_id = f"{node2_id}-{node1_id}"
        
        # Store edge with cardinality and order
        self.edges[edge_id] = {
            'id': edge_id,
            'from': node1_id,
            'to': node2_id,
            'cardinality': cardinality,
            'order': order
        }
        
        print(f"Created edge '{edge_id}' with cardinality {cardinality}" + (f" and order {order}" if order is not None else ""))
        
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
            # Get source and target ids
            edge = self.edges[edge_id]
            source_id = edge.get('from')
            target_id = edge.get('to')
            
            # Remove connections between nodes if they exist
            if source_id and target_id:
                if source_id in self.nodes and target_id in self.nodes:
                    # Remove bidirectional connections
                    if target_id in self.nodes[source_id].connections:
                        self.nodes[source_id].connections.remove(target_id)
                    if source_id in self.nodes[target_id].connections:
                        self.nodes[target_id].connections.remove(source_id)
            
            # Delete the edge
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

# Create a session manager instance (moved from above to resolve import order)
session_manager = SessionManager()

# Session manager will handle initialization for each user session

def get_user_editor():
    """Get the editor instance for the current user session"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    editor = session_manager.get_editor_for_session(session_id)
    
    # Initialize editor if it's None (first time creation)
    if editor is None:
        editor = FlaskSHACLGraphEditor()
        session_manager.sessions[session_id] = editor
        session_manager.session_timestamps[session_id] = datetime.now()
        
        # Initialize with default dataset node
        dataset_exists = False
        for node in editor.nodes.values():
            if node.type == 'dataset':
                dataset_exists = True
                break
        
        if not dataset_exists:
            dataset_node = SHACLNode('dataset', title="New Dataset", description="Dataset description")
            editor.nodes[dataset_node.id] = dataset_node
    
    return editor

@app.route('/')
def index():
    """Render the main application page"""
    # Get user-specific editor (already initializes if needed)
    get_user_editor()
    return render_template('index.html')

@app.route('/api/graph', methods=['GET'])
def get_graph():
    """Get the graph data for visualization"""
    editor = get_user_editor()
    nodes_data = []
    edges_data = []
    
    # Print debug info
    print(f"Fetching graph with {len(editor.nodes)} nodes and {len(editor.edges)} edges")
    
    # Process all nodes
    for node_id, node in editor.nodes.items():
        # Determine node type
        node_type = node.type
        
        # Add node to nodes data
        nodes_data.append({
            'id': node_id,
            'title': node.title,
            'description': node.description,
            'type': node_type,
            'order': node.order if hasattr(node, 'order') else None,
            'i14y_id': node.i14y_id if hasattr(node, 'i14y_id') else None,
            'is_linked_to_concept': node.is_linked_to_concept if hasattr(node, 'is_linked_to_concept') else False
        })
    
    # Process all edges
    for edge_id, edge in editor.edges.items():
        # Check the type of edge object
        if hasattr(edge, 'from_node') and hasattr(edge, 'to_node'):
            # Edge is an object with from_node and to_node attributes
            edges_data.append({
                'id': edge_id,
                'from': edge.from_node.id,
                'to': edge.to_node.id,
                'cardinality': edge.cardinality if hasattr(edge, 'cardinality') else '1..1'
            })
        elif isinstance(edge, dict) and 'from' in edge and 'to' in edge:
            # Edge is already a dict with 'from' and 'to' keys
            edges_data.append({
                'id': edge_id,
                'from': edge['from'],
                'to': edge['to'],
                'cardinality': edge.get('cardinality', '1..1')
            })
        else:
            # Try to extract from and to IDs based on common patterns
            try:
                from_id = edge.from_id if hasattr(edge, 'from_id') else (
                    edge['from_id'] if isinstance(edge, dict) and 'from_id' in edge else None
                )
                to_id = edge.to_id if hasattr(edge, 'to_id') else (
                    edge['to_id'] if isinstance(edge, dict) and 'to_id' in edge else None
                )
                
                if from_id and to_id:
                    edges_data.append({
                        'id': edge_id,
                        'from': from_id,
                        'to': to_id,
                        'cardinality': edge.cardinality if hasattr(edge, 'cardinality') else (
                            edge.get('cardinality', '1..1') if isinstance(edge, dict) else '1..1'
                        )
                    })
                else:
                    print(f"Warning: Could not extract from/to IDs for edge {edge_id}")
            except Exception as e:
                print(f"Error processing edge {edge_id}: {str(e)}")
                continue
    
    return jsonify({
        'nodes': nodes_data,
        'edges': edges_data
    })
@app.route('/api/nodes/<node_id>/position', methods=['POST'])
def update_node_position(node_id):
    """Update a node's position in the layout"""
    editor = get_user_editor()
    data = request.json
    
    if not data or 'x' not in data or 'y' not in data:
        return jsonify({"error": "Missing position data"}), 400
    
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    # Store position in the node's data
    editor.nodes[node_id].position['x'] = data['x']
    editor.nodes[node_id].position['y'] = data['y']
    
    return jsonify({"success": True})

@app.route('/api/graph/layout', methods=['GET'])
def get_graph_layout():
    """Get the NetworkX computed layout for the graph"""
    editor = get_user_editor()
    
    try:
        import networkx as nx
        import numpy as np
        
        # Create NetworkX graph
        G = nx.Graph()
        
        # Add nodes
        for node_id in editor.nodes:
            G.add_node(node_id)
        
        # Add edges
        for edge_id, edge in editor.edges.items():
            # Check the type of edge object
            if hasattr(edge, 'from_node') and hasattr(edge, 'to_node'):
                # Edge is an object with from_node and to_node attributes
                G.add_edge(edge.from_node.id, edge.to_node.id)
            elif isinstance(edge, dict) and 'from' in edge and 'to' in edge:
                # Edge is already a dict with 'from' and 'to' keys
                G.add_edge(edge['from'], edge['to'])
            else:
                # Try to extract from and to IDs based on common patterns
                try:
                    from_id = edge.from_id if hasattr(edge, 'from_id') else (
                        edge['from_id'] if isinstance(edge, dict) and 'from_id' in edge else None
                    )
                    to_id = edge.to_id if hasattr(edge, 'to_id') else (
                        edge['to_id'] if isinstance(edge, dict) and 'to_id' in edge else None
                    )
                    
                    if from_id and to_id:
                        G.add_edge(from_id, to_id)
                    else:
                        print(f"Warning: Could not extract from/to IDs for edge {edge_id} in layout calculation")
                except Exception as e:
                    print(f"Error processing edge {edge_id} in layout calculation: {str(e)}")
                    continue
        
        # Apply NetworkX layout algorithm
        if len(G.nodes) > 0:
            # Check for saved positions first
            saved_pos = {}
            fixed_nodes = []
            
            for node_id in G.nodes():
                if node_id in editor.nodes and hasattr(editor.nodes[node_id], 'position') and editor.nodes[node_id].position and 'x' in editor.nodes[node_id].position and 'y' in editor.nodes[node_id].position:
                    # Use saved position
                    saved_pos[node_id] = (editor.nodes[node_id].position['x'], editor.nodes[node_id].position['y'])
                    fixed_nodes.append(node_id)
            
            # Use different layouts based on graph size, respecting fixed positions
            if len(G.nodes) < 10:
                pos = nx.spring_layout(G, k=0.3, iterations=50, pos=saved_pos, fixed=fixed_nodes)
            elif len(G.nodes) < 30:
                pos = nx.fruchterman_reingold_layout(G, pos=saved_pos, fixed=fixed_nodes)
            else:
                # For kamada_kawai, we need to handle fixed nodes differently since it doesn't support the fixed parameter
                if fixed_nodes:
                    # Initialize with positions for all nodes
                    init_pos = saved_pos.copy()
                    for node_id in G.nodes():
                        if node_id not in init_pos:
                            init_pos[node_id] = (np.random.random(), np.random.random())
                    pos = nx.kamada_kawai_layout(G, pos=init_pos)
                    # Restore fixed positions
                    for node_id in fixed_nodes:
                        pos[node_id] = saved_pos[node_id]
                else:
                    pos = nx.kamada_kawai_layout(G)
            
            # Normalize positions to 0-1 range
            min_x = min(p[0] for p in pos.values())
            max_x = max(p[0] for p in pos.values())
            min_y = min(p[1] for p in pos.values())
            max_y = max(p[1] for p in pos.values())
            
            width_range = max_x - min_x if max_x > min_x else 1
            height_range = max_y - min_y if max_y > min_y else 1
            
            normalized_pos = {}
            for node_id, p in pos.items():
                normalized_pos[node_id] = {
                    'x': (p[0] - min_x) / width_range * 0.8 + 0.1,  # Add 10% margin
                    'y': (p[1] - min_y) / height_range * 0.8 + 0.1   # Add 10% margin
                }
            
            return jsonify({
                'success': True,
                'positions': normalized_pos
            })
        else:
            return jsonify({
                'success': True,
                'positions': {}
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Failed to get graph data'
        })
    
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
            color = '#87CEFA'  # Light blue for dataset
        elif node.type == 'class':
            color = '#99ff99'  # Light green for classes
        elif node.type == 'data_element':
            if node.is_linked_to_concept:
                color = '#ffcc99'  # Orange for data elements linked to concepts
            else:
                color = '#ccccff'  # Light purple for standalone data elements
            
        # Add node to nodes data
        # Get node type and publisher info
        node_type = 'Dataset'
        if node.type == 'class':
            node_type = 'Class'
        elif node.type == 'data_element':
            node_type = 'Data Element'
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
    editor = get_user_editor()
    return jsonify(editor.get_all_nodes())

@app.route('/api/data-elements', methods=['POST'])
def create_data_element():
    """Create a data element from a concept or as standalone"""
    editor = get_user_editor()
    data = request.json
    
    concept_id = data.get('concept_id')
    concept_data = data.get('concept_data')  # I14Y concept data for linking during creation
    local_name = data.get('local_name')
    parent_id = data.get('parent_id')
    standalone = data.get('standalone', False)
    
    if not local_name:
        return jsonify({"error": "Local name is required"}), 400
    
    try:
        if concept_id and not standalone:
            # Create data element from existing concept
            if concept_id not in editor.nodes:
                return jsonify({"error": "Concept not found"}), 404
            
            concept_node = editor.nodes[concept_id]
            if concept_node.type != 'concept':
                return jsonify({"error": "Referenced node is not a concept"}), 400
            
            # Create data element from concept
            data_element = concept_node.create_data_element_from_concept(concept_node, local_name)
        else:
            # Create standalone data element
            data_element = SHACLNode('data_element', title=local_name)
            data_element.local_name = local_name
            
            # If concept_data is provided, link to I14Y concept during creation
            if concept_data:
                concept_id_from_data = concept_data.get('id')
                if concept_id_from_data:
                    data_element.conforms_to_concept_uri = f"https://www.i14y.admin.ch/de/catalog/concepts/{concept_id_from_data}/description"
                    data_element.is_linked_to_concept = True
                    data_element.i14y_data = concept_data
                    
                    # Extract multilingual descriptions from concept data
                    desc_obj = concept_data.get('description')
                    
                    if desc_obj:
                        if isinstance(desc_obj, dict):
                            # Store the full multilingual description object
                            multilingual_descriptions = {
                                lang: desc for lang, desc in desc_obj.items()
                                if lang in ['de', 'en', 'fr', 'it', 'rm'] and desc
                            }
                            # Ensure we have at least a German description as fallback
                            if multilingual_descriptions:
                                data_element.description = multilingual_descriptions
                                print(f"Created data element with multilingual description: {list(multilingual_descriptions.keys())}")
                            else:
                                data_element.description = {'de': ''}
                        elif isinstance(desc_obj, str) and desc_obj.strip():
                            # Handle string descriptions
                            data_element.description = {'de': desc_obj}
                            print(f"Created data element with string description")
                    else:
                        # Use provided description if no concept description
                        data_element.description = data.get('description', '')
                else:
                    data_element.description = data.get('description', '')
            else:
                # No concept data - use provided description or empty
                data_element.description = data.get('description', '')
                
            data_element.datatype = data.get('datatype', 'xsd:string')
        
        # Add to editor
        editor.nodes[data_element.id] = data_element
        
        # Connect to parent if specified
        if parent_id and parent_id in editor.nodes:
            # Add to connections sets
            editor.nodes[parent_id].connections.add(data_element.id)
            data_element.connections.add(parent_id)
            
            # Create an edge in the edge dictionary
            edge_id = f"{parent_id}-{data_element.id}"
            editor.edges[edge_id] = {
                'id': edge_id,
                'from': parent_id,
                'to': data_element.id,
                'cardinality': '1..1'
            }
        else:
            # Connect to dataset node by default
            dataset_node = None
            for n_id, n in editor.nodes.items():
                if n.type == 'dataset':
                    dataset_node = n
                    break
            
            if dataset_node:
                dataset_node.connections.add(data_element.id)
                data_element.connections.add(dataset_node.id)
                
                edge_id = f"{dataset_node.id}-{data_element.id}"
                editor.edges[edge_id] = {
                    'id': edge_id,
                    'from': dataset_node.id,
                    'to': data_element.id,
                    'cardinality': '1..1'
                }
        
        return jsonify({"success": True, "node_id": data_element.id})
    except Exception as e:
        print(f"Error creating data element: {str(e)}")
        return jsonify({"error": "Failed to create data element"}), 500

@app.route('/api/data-elements/<data_element_id>', methods=['PUT'])
def update_data_element(data_element_id):
    """Update a data element"""
    editor = get_user_editor()
    
    if data_element_id not in editor.nodes:
        return jsonify({"error": "Data element not found"}), 404
    
    data_element = editor.nodes[data_element_id]
    if data_element.type != 'data_element':
        return jsonify({"error": "Node is not a data element"}), 400
    
    # Get update data
    node_data = request.json
    
    # Update the node using the general update method
    result = editor.update_node(data_element_id, node_data)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to update data element"}), 500

@app.route('/api/link/i14y', methods=['POST'])
def link_node_to_i14y_concept():
    """Link a node to an I14Y concept"""
    editor = get_user_editor()
    data = request.json
    
    # Ensure node_id is a string
    node_id = data.get('node_id')
    if not node_id:
        return jsonify({"error": "Node ID is required"}), 400
        
    # Handle the case where node_id is a dict (from D3.js visualization data)
    if isinstance(node_id, dict) and 'id' in node_id:
        print(f"Received node_id as dict: {node_id}")
        node_id = node_id['id']
    # Convert node_id to string if it's not already
    elif not isinstance(node_id, str):
        print(f"Warning: node_id is not a string, it's a {type(node_id)}. Value: {node_id}")
        try:
            node_id = str(node_id)
        except Exception as e:
            print(f"Error converting node_id to string: {e}")
            return jsonify({"error": f"Invalid node ID format: {type(node_id)}"}), 400
    
    # Check if the node exists
    if node_id not in editor.nodes:
        return jsonify({"error": f"Node with ID {node_id} not found"}), 404
        
    node = editor.nodes[node_id]
    if node.type != 'data_element':
        return jsonify({"error": "Only data elements can be linked to I14Y concepts"}), 400
    
    # Check if already linked to a concept
    print(f"Attempting to link data element {node_id} to concept")
    print(f"Current is_linked_to_concept: {node.is_linked_to_concept}")
    print(f"Current conforms_to_concept_uri: {node.conforms_to_concept_uri}")
    
    if node.is_linked_to_concept:
        return jsonify({"error": "This data element is already linked to a concept. Please detach the existing concept first."}), 400
        
    concept_uri = data.get('concept_uri')
    concept_data = data.get('concept_data')
    
    if not concept_uri or not concept_data:
        return jsonify({"error": "Concept URI and data are required"}), 400
    
    # Debug logging
    print(f"=== Linking data element to I14Y concept ===")
    print(f"Node ID: {node_id}")
    print(f"Concept URI: {concept_uri}")
    print(f"Concept data keys: {concept_data.keys() if isinstance(concept_data, dict) else 'not a dict'}")
    if isinstance(concept_data, dict) and 'description' in concept_data:
        print(f"Description type: {type(concept_data['description'])}")
        if isinstance(concept_data['description'], dict):
            print(f"Description languages: {list(concept_data['description'].keys())}")
            print(f"Description DE: {concept_data['description'].get('de', 'N/A')[:100] if concept_data['description'].get('de') else 'N/A'}")
        else:
            print(f"Description (string): {str(concept_data['description'])[:100]}")
        
    try:
        # Save original values
        original_title = node.title
        original_description = node.description
        
        # Link to concept
        node.conforms_to_concept_uri = concept_uri
        node.is_linked_to_concept = True
        node.i14y_data = concept_data
        
        # Extract multilingual descriptions from concept data and update data element
        # The concept_data comes directly from the frontend, not nested under 'data' key
        # Check if description exists and has content
        has_existing_description = False
        if node.description:
            if isinstance(node.description, dict):
                # Check if any language has non-empty content
                has_existing_description = any(node.description.get(lang, '').strip() 
                                              for lang in ['de', 'fr', 'it', 'en'])
            elif isinstance(node.description, str):
                has_existing_description = bool(node.description.strip())
        
        # Only update description if the data element doesn't have a meaningful one
        if not has_existing_description:
            desc_obj = concept_data.get('description')
            
            if desc_obj:
                if isinstance(desc_obj, dict):
                    # Store the full multilingual description object
                    multilingual_descriptions = {
                        lang: desc for lang, desc in desc_obj.items()
                        if lang in ['de', 'en', 'fr', 'it', 'rm'] and desc
                    }
                    # Ensure we have at least a German description as fallback
                    if multilingual_descriptions:
                        node.description = multilingual_descriptions
                        print(f"Updated data element description with multilingual content: {list(multilingual_descriptions.keys())}")
                    else:
                        node.description = {'de': ''}
                elif isinstance(desc_obj, str) and desc_obj.strip():
                    # Handle string descriptions
                    node.description = {'de': desc_obj}
                    print(f"Updated data element description with string content")
            
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error linking to I14Y concept: {e}")
        return jsonify({"error": "Failed to link to I14Y concept"}), 500

@app.route('/api/data-elements/<data_element_id>/link-concept', methods=['POST'])
def link_data_element_to_concept(data_element_id):
    """Link a data element to an I14Y concept"""
    editor = get_user_editor()
    data = request.json
    
    if data_element_id not in editor.nodes:
        return jsonify({"error": "Data element not found"}), 404
    
    data_element = editor.nodes[data_element_id]
    if data_element.type != 'data_element':
        return jsonify({"error": "Node is not a data element"}), 400
    
    # Check if already linked to a concept
    if data_element.is_linked_to_concept:
        return jsonify({"error": "This data element is already linked to a concept. Please detach the existing concept first."}), 400
    
    concept_data = data.get('concept_data')
    if not concept_data:
        return jsonify({"error": "Concept data is required"}), 400
    
    try:
        # Save the existing custom title and description before linking
        original_title = data_element.title
        original_description = data_element.description
        original_local_name = data_element.local_name
        
        # Create concept URI for conformsTo
        concept_id = concept_data.get('id')
        if concept_id:
            data_element.conforms_to_concept_uri = f"https://www.i14y.admin.ch/de/catalog/concepts/{concept_id}/description"
            data_element.is_linked_to_concept = True
        
        # Store I14Y data for reference (but don't make it a concept node)
        data_element.i14y_data = concept_data
        
        # Apply constraints from concept
        api_client = I14YAPIClient()
        constraints = api_client.extract_constraints_from_concept(concept_data)
        
        if 'pattern' in constraints:
            data_element.pattern = constraints['pattern']
        if 'in_values' in constraints:
            data_element.in_values = constraints['in_values']
        if 'datatype' in constraints:
            data_element.datatype = constraints['datatype']
            
        # Restore the original title, description, and local_name
        data_element.title = original_title
        data_element.description = original_description
        data_element.local_name = original_local_name
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error unlinking concept from data element: {str(e)}")
        return jsonify({"error": "Failed to unlink concept from data element"}), 500

@app.route('/api/data-elements/<data_element_id>/unlink-concept', methods=['POST'])
def unlink_data_element_from_concept(data_element_id):
    """Unlink a data element from its concept"""
    editor = get_user_editor()
    
    if data_element_id not in editor.nodes:
        return jsonify({"error": "Data element not found"}), 404
    
    data_element = editor.nodes[data_element_id]
    if data_element.type != 'data_element':
        return jsonify({"error": "Node is not a data element"}), 400
    
    print(f"Unlinking data element {data_element_id} from concept")
    print(f"Before unlink - is_linked_to_concept: {data_element.is_linked_to_concept}")
    print(f"Before unlink - conforms_to_concept_uri: {data_element.conforms_to_concept_uri}")
    
    # Clear concept link
    data_element.conforms_to_concept_uri = None
    data_element.is_linked_to_concept = False
    data_element.i14y_data = None
    
    print(f"After unlink - is_linked_to_concept: {data_element.is_linked_to_concept}")
    print(f"After unlink - conforms_to_concept_uri: {data_element.conforms_to_concept_uri}")
    
    return jsonify({"success": True})

@app.route('/api/nodes', methods=['POST'])
def add_node():
    """Add a new node to the graph"""
    editor = get_user_editor()
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
    editor = get_user_editor()
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    # Clear selection from all other nodes (if needed)
    # This is handled in the frontend, so nothing to do here
    
    return jsonify({"success": True})

@app.route('/api/nodes/<node_id>', methods=['GET'])
def get_node(node_id):
    """Get details for a specific node"""
    editor = get_user_editor()
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    node = editor.nodes[node_id]
    print(f"GET NODE {node_id}: Returning node with order={node.order}")
    return jsonify({
        'id': node.id,
        'type': node.type,
        'title': node.title,
        'description': node.description,
        'i14y_id': node.i14y_id,
        'i14y_data': node.i14y_data,
        'i14y_concept_uri': node.i14y_concept_uri,
        'i14y_dataset_uri': node.i14y_dataset_uri,
        'local_name': node.local_name,
        'is_linked_to_concept': node.is_linked_to_concept,
        'conforms_to_concept_uri': node.conforms_to_concept_uri,
        'min_count': node.min_count,
        'max_count': node.max_count,
        'min_length': node.min_length, 
        'max_length': node.max_length,
        'pattern': node.pattern,
        'in_values': node.in_values,
        'node_reference': node.node_reference,
        'range': node.range,
        'datatype': node.datatype,
        'order': node.order,
        'suggested_pattern': node.suggested_pattern,
        'suggested_in_values': node.suggested_in_values,
        'suggested_min_length': node.suggested_min_length,
        'suggested_max_length': node.suggested_max_length
    })

@app.route('/api/nodes/<node_id>/constraints', methods=['POST'])
def update_constraints(node_id):
    """Update constraints for a node"""
    editor = get_user_editor()
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

@app.route('/api/nodes/<node_id>/link-to-i14y', methods=['POST'])
def link_node_to_i14y(node_id):
    """Link an existing custom concept to an I14Y concept"""
    editor = get_user_editor()
    
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    node = editor.nodes[node_id]
    
    # Only allow linking concepts
    if node.type != 'concept':
        return jsonify({"error": "Only concept nodes can be linked to I14Y"}), 400
    
    # Check if the node is already linked to I14Y
    if node.i14y_id:
        return jsonify({"error": "This concept is already linked to I14Y"}), 400
    
    data = request.json
    concept_data = data.get('concept_data')
    
    if not concept_data:
        return jsonify({"error": "I14Y concept data is required"}), 400
    
    try:
        # Save existing constraints before updating
        min_length = node.min_length
        max_length = node.max_length
        pattern = node.pattern
        in_values = node.in_values
        datatype = node.datatype
        
        # Update node with I14Y concept data
        node.set_i14y_concept(concept_data)
        
        # Restore any existing constraints
        if min_length is not None:
            node.min_length = min_length
        if max_length is not None:
            node.max_length = max_length
        if pattern:
            node.pattern = pattern
        if in_values:
            node.in_values = in_values
        if datatype:
            node.datatype = datatype
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        print(f"Error linking node to I14Y: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to link node to I14Y"}), 500

@app.route('/api/nodes/<node_id>/disconnect-i14y', methods=['POST'])
def disconnect_node_from_i14y(node_id):
    """Disconnect a node from I14Y, converting it back to a custom concept"""
    editor = get_user_editor()
    
    if node_id not in editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    node = editor.nodes[node_id]
    
    # Only allow disconnecting concepts
    if node.type != 'concept':
        return jsonify({"error": "Only concept nodes can be disconnected from I14Y"}), 400
    
    # Check if the node is actually linked to I14Y
    if not node.i14y_id:
        return jsonify({"error": "This concept is not linked to I14Y"}), 400
    
    try:
        # Save title, description, and constraints before disconnecting
        title = node.title
        description = node.description
        min_length = node.min_length
        max_length = node.max_length
        pattern = node.pattern
        in_values = node.in_values
        datatype = node.datatype
        
        # Clear I14Y specific data
        node.i14y_id = None
        node.i14y_data = None
        
        # Restore the title and description
        node.title = title
        node.description = description
        
        # Restore constraints
        node.min_length = min_length
        node.max_length = max_length
        node.pattern = pattern
        node.in_values = in_values
        node.datatype = datatype
        
        return jsonify({
            "success": True,
            "node": {
                "id": node.id,
                "title": node.title,
                "description": node.description,
                "type": node.type
            }
        })
    except Exception as e:
        import traceback
        print(f"Error disconnecting node from I14Y: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to disconnect node from I14Y"}), 500

@app.route('/api/nodes/<node_id>', methods=['PUT'])
def update_node(node_id):
    """Update a node"""
    editor = get_user_editor()
    node_data = request.json
    print(f"UPDATE NODE {node_id}: Received data: {node_data}")
    result = editor.update_node(node_id, node_data)
    print(f"UPDATE NODE {node_id}: Result: {result}")
    if result:
        # Log the updated node's order field specifically
        if node_id in editor.nodes:
            print(f"UPDATE NODE {node_id}: Node order after update: {editor.nodes[node_id].order}")
        return jsonify(result)
    return jsonify({"error": "Node not found"}), 404

@app.route('/api/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    """Delete a node"""
    editor = get_user_editor()
    success = editor.delete_node(node_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Node not found"}), 404

@app.route('/api/connections', methods=['POST'])
def create_connection():
    """Create a connection between nodes"""
    editor = get_user_editor()
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
    editor = get_user_editor()
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
    editor = get_user_editor()
    edge = editor.get_edge(edge_id)
    if edge:
        # Add source and target node details to the response
        if 'from' in edge and 'to' in edge:
            from_node = editor.nodes.get(edge['from'])
            to_node = editor.nodes.get(edge['to'])
            if from_node and to_node:
                edge_with_nodes = edge.copy()
                edge_with_nodes['from_node'] = from_node.to_dict()
                edge_with_nodes['to_node'] = to_node.to_dict()
                return jsonify(edge_with_nodes)
        return jsonify(edge)
    return jsonify({"error": "Edge not found"}), 404

@app.route('/api/edges/<edge_id>', methods=['DELETE'])
def delete_edge(edge_id):
    """Delete an edge by ID"""
    editor = get_user_editor()
    
    # Ensure the edge exists
    if edge_id not in editor.edges:
        print(f"Edge not found: {edge_id}")
        return jsonify({"error": "Edge not found"}), 404
    
    # Get the nodes connected by this edge before deletion
    edge = editor.edges.get(edge_id)
    if edge and 'from' in edge and 'to' in edge:
        from_id = edge['from']
        to_id = edge['to']
        
        print(f"Deleting edge {edge_id} connecting {from_id} to {to_id}")
        
        # Remove the connection from both nodes' connection sets
        if from_id in editor.nodes and to_id in editor.nodes:
            if to_id in editor.nodes[from_id].connections:
                editor.nodes[from_id].connections.remove(to_id)
                print(f"Removed {to_id} from {from_id}'s connections")
            else:
                print(f"Warning: {to_id} not found in {from_id}'s connections")
                
            if from_id in editor.nodes[to_id].connections:
                editor.nodes[to_id].connections.remove(from_id)
                print(f"Removed {from_id} from {to_id}'s connections")
            else:
                print(f"Warning: {from_id} not found in {to_id}'s connections")
    else:
        print(f"Warning: Edge {edge_id} doesn't have valid from/to fields")
    
    # Delete the edge
    try:
        del editor.edges[edge_id]
        print(f"Successfully deleted edge {edge_id}")
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting edge: {str(e)}")
        return jsonify({"error": "Failed to delete edge"}), 500

@app.route('/api/edges/<edge_id>/cardinality', methods=['POST'])
def update_edge_cardinality(edge_id):
    """Update the cardinality of an edge"""
    editor = get_user_editor()
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
    editor = get_user_editor()
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
    editor = get_user_editor()
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
    editor = get_user_editor()
    ttl = editor.generate_ttl()
    return jsonify({"ttl": ttl})

@app.route('/api/download-ttl', methods=['GET'])
def download_ttl():
    """Download the graph as a TTL file"""
    editor = get_user_editor()
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
    editor = get_user_editor()
    filename = request.json.get('filename', f"shacl_graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    # Sanitize filename
    safe_filename = secure_filename(filename)
    # Ensure the data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Build and normalize the path
    data_dir = os.path.abspath('data')
    filepath = os.path.normpath(os.path.join(data_dir, safe_filename))
    # Ensure the file is within the data directory
    if not filepath.startswith(data_dir + os.sep):
        return jsonify({"error": "Invalid filename/path"}), 400
    success = editor.save_to_file(filepath)
    
    if success:
        return jsonify({"success": True, "filename": safe_filename})
    return jsonify({"error": "Failed to save graph"}), 500

@app.route('/api/load', methods=['POST'])
def load_graph():
    """Load a graph from a file"""
    editor = get_user_editor()
    filename = request.json.get('filename')
    
    if not filename:
        return jsonify({"error": "Filename is required"}), 400
        
    # Prevent path traversal: normalize and check that path stays in 'data'
    base_dir = os.path.abspath('data')
    filepath = os.path.normpath(os.path.join(base_dir, filename))
    if not filepath.startswith(base_dir + os.sep):
        return jsonify({"error": "Invalid filename"}), 400
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
        
    success = editor.load_from_file(filepath)
    
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to load graph"}), 500

@app.route('/api/project/save', methods=['GET'])
def save_project():
    """Save the current project to a file for download"""
    editor = get_user_editor()
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
        print(f"Error saving project: {str(e)}")
        return jsonify({"error": "Failed to save project"}), 500

@app.route('/api/project/load', methods=['POST'])
def load_project():
    """Load a project from uploaded file"""
    editor = get_user_editor()
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only JSON files are supported"}), 400
    
    try:
        # Debug logging
        print(f"File upload debug: filename={file.filename}, content_type={file.content_type}")
        print(f"File object: {file}")
        
        # Read file content
        raw_content = file.read()
        print(f"Raw content length: {len(raw_content)} bytes")
        
        if len(raw_content) == 0:
            print("ERROR: File content is empty!")
            return jsonify({"error": "Uploaded file is empty"}), 400
        
        content = raw_content.decode('utf-8')
        print(f"Decoded content length: {len(content)} characters")
        print(f"Content preview: {content[:200]}...")
        
        project_data = json.loads(content)
        
        print(f"Loading project - data keys: {project_data.keys()}")
        
        # Clear existing nodes and edges
        editor.nodes.clear()
        editor.edges.clear()
        
        # Check if this is the legacy format (with "concepts" instead of "nodes")
        edges_loaded_from_file = False  # Track if edges were loaded from file
        
        if "concepts" in project_data and "nodes" not in project_data:
            print("Detected legacy project format - converting concepts to nodes")
            # Convert legacy format to current format
            nodes_data = {}
            for concept_id, concept_data in project_data.get("concepts", {}).items():
                # Convert concept to node format
                node_data = {
                    'id': concept_id,
                    'type': 'concept',  # Legacy format used concepts
                    'title': concept_data.get('title', ''),
                    'description': concept_data.get('description', ''),
                    'datatype': concept_data.get('datatype', 'xsd:string'),
                    'min_count': concept_data.get('min_count'),
                    'max_count': concept_data.get('max_count'),
                    'min_length': concept_data.get('min_length'),
                    'max_length': concept_data.get('max_length'),
                    'pattern': concept_data.get('pattern')
                }
                nodes_data[concept_id] = node_data
            
            # Create a dataset node if it doesn't exist
            dataset_node_id = None
            for node_id, node_data in nodes_data.items():
                if node_data.get('type') == 'dataset':
                    dataset_node_id = node_id
                    break
            
            if not dataset_node_id:
                dataset_node_id = str(uuid.uuid4())
                nodes_data[dataset_node_id] = {
                    'id': dataset_node_id,
                    'type': 'dataset',
                    'title': 'Imported Dataset',
                    'description': 'Dataset imported from legacy format'
                }
            
            # Set nodes from converted data
            for node_id, node_data in nodes_data.items():
                editor.nodes[node_id] = SHACLNode.from_dict(node_data)
            
            # Create edges from node connections
            for node_id, node in editor.nodes.items():
                if node_id != dataset_node_id and not node.connections:
                    # Connect to dataset
                    editor.nodes[dataset_node_id].connections.add(node_id)
                    node.connections.add(dataset_node_id)
                    edge_id = f"{dataset_node_id}-{node_id}"
                    editor.edges[edge_id] = {
                        'id': edge_id,
                        'from': dataset_node_id,
                        'to': node_id,
                        'cardinality': '1..1'
                    }
            
            node_count = len(editor.nodes)
            edge_count = len(editor.edges)
            print(f"Converted legacy format: {node_count} nodes and {edge_count} edges")
            
        else:
            # Load current format
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
                edges_loaded_from_file = True
            else:
                print("No edges found in project data - will generate from node connections")
        
        # Generate edges from node connections ONLY for backward compatibility
        # (when edges were not saved in the project file)
        if not edges_loaded_from_file:
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
                print(f"Created {conn_edges_added} edges from node connections (backward compatibility)")
        else:
            print(f"Skipped edge generation from node connections - edges already loaded from file")
        
        total_nodes = len(editor.nodes)
        total_edges = len(editor.edges)
        print(f"Project loaded: {total_nodes} nodes and {total_edges} total edges")
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error loading project: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to load project"}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all saved graph files"""
    os.makedirs('data', exist_ok=True)
    files = [f for f in os.listdir('data') if f.endswith('.json')]
    return jsonify({"files": files})

@app.route('/api/project/new', methods=['POST'])
def new_project():
    """Create a new empty structure"""
    editor = get_user_editor()
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
        return jsonify({"error": "Failed to create new project"}), 500

@app.route('/new-structure', methods=['GET'])
def new_structure_page():
    """Create a new structure and redirect to home page"""
    editor = get_user_editor()
    try:
        # Reset the structure
        editor.reset_structure()
        # Redirect to the home page
        return redirect('/')
    except Exception as e:
        print(f"Error creating new structure: {str(e)}")
        return "Failed to create new structure", 500

@app.route('/api/i14y/search', methods=['GET'])
def search_i14y():
    """Search for concepts in I14Y"""
    editor = get_user_editor()
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
        return jsonify({"error": "Failed to search I14Y concepts", "concepts": []}), 500

@app.route('/api/i14y/dataset/search', methods=['GET'])
def search_i14y_datasets():
    """Search for datasets in I14Y"""
    editor = get_user_editor()
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
        return jsonify({"error": "Failed to search I14Y datasets", "datasets": []}), 500

@app.route('/api/i14y/dataset/link', methods=['POST'])
def link_i14y_dataset():
    """Link an I14Y dataset to the current dataset node"""
    editor = get_user_editor()
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
        # Find the specific dataset node
        dataset_node = editor.nodes.get(dataset_id)
        if not dataset_node or dataset_node.type != 'dataset':
            print("ERROR: Dataset node not found or not a dataset type")
            return jsonify({"error": "Dataset node not found"}), 404
        
        # Update the dataset node with I14Y information
        if 'title' in dataset_data:
            if isinstance(dataset_data['title'], dict):
                # Handle multilingual titles - store the full multilingual object
                multilingual_titles = {
                    lang: desc for lang, desc in dataset_data['title'].items() 
                    if lang in ['de', 'en', 'fr', 'it', 'rm'] and desc
                }
                # Ensure we have at least a German title as fallback
                if not multilingual_titles:
                    multilingual_titles = {'de': 'Unknown Dataset'}
                dataset_node.title = multilingual_titles
            else:
                dataset_node.title = dataset_data.get('title', '')
                
        if 'description' in dataset_data:
            if isinstance(dataset_data['description'], dict):
                # Handle multilingual descriptions - store the full multilingual object
                multilingual_descriptions = {
                    lang: desc for lang, desc in dataset_data['description'].items() 
                    if lang in ['de', 'en', 'fr', 'it', 'rm'] and desc
                }
                # Ensure we have at least a German description as fallback
                if not multilingual_descriptions:
                    multilingual_descriptions = {'de': ''}
                dataset_node.description = multilingual_descriptions
            else:
                dataset_node.description = dataset_data.get('description', '')
        
        # Set the I14Y ID for the dataset
        dataset_node.i14y_id = dataset_data.get('id')
        
        # Set the I14Y dataset URI
        dataset_node.i14y_dataset_uri = f"https://www.i14y.admin.ch/de/catalog/datasets/{dataset_data.get('id')}/description"
        
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
        return jsonify({"error": "Failed to link I14Y dataset"}), 500

@app.route('/api/i14y/dataset/disconnect', methods=['POST'])
def disconnect_i14y_dataset():
    """Disconnect an I14Y dataset from the current dataset node"""
    editor = get_user_editor()
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
        return jsonify({"error": "Failed to disconnect I14Y dataset"}), 500
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
        return jsonify({"error": "Failed to add I14Y concept"}), 500

@app.route('/api/export/ttl', methods=['GET'])
def export_ttl():
    """Export the graph as TTL"""
    editor = get_user_editor()
    try:
        # Generate TTL
        ttl_content = generate_full_ttl(editor.nodes, editor.base_uri, editor.edges)
        
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
                elif hasattr(dataset_node, 'title') and dataset_node.title:
                    # Sanitize title for use as filename
                    # Handle multilingual title
                    if isinstance(dataset_node.title, dict):
                        title_text = (dataset_node.title.get('de') or 
                                     dataset_node.title.get('en') or 
                                     dataset_node.title.get('fr') or 
                                     dataset_node.title.get('it') or 
                                     next(iter(dataset_node.title.values()), ""))
                    else:
                        title_text = str(dataset_node.title)
                    
                    if title_text and title_text.strip():
                        sanitized_title = title_text.strip()
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
        print(f"Error exporting TTL: {str(e)}")
        return jsonify({"error": "Failed to export TTL"}), 500

@app.route('/api/i14y/schemes', methods=['GET'])
def get_schemes():
    """Get all concept schemes from I14Y"""
    editor = get_user_editor()
    try:
        # Check if the method exists in the client
        if hasattr(editor.i14y_client, 'get_concept_schemes'):
            schemes = editor.i14y_client.get_concept_schemes()
            return jsonify({"schemes": schemes})
        else:
            # Return empty list if method doesn't exist
            return jsonify({"schemes": [], "message": "Concept scheme retrieval not implemented"})
    except Exception as e:
        print(f"Error getting schemes: {str(e)}")
        return jsonify({"error": "Failed to get concept schemes", "schemes": []}), 500

@app.route('/api/i14y/concept/<concept_id>', methods=['GET'])
def get_i14y_concept(concept_id):
    """Get details of a specific I14Y concept by ID"""
    editor = get_user_editor()
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
            "error": "Failed to fetch concept from I14Y API",
            "message": "There was an error fetching the concept from the I14Y API."
        }), 500

@app.route('/api/i14y/add', methods=['POST'])
def add_i14y_concept():
    """Add an I14Y concept to the graph"""
    editor = get_user_editor()
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
        return jsonify({"error": "Failed to add I14Y concept"}), 500

@app.route('/api/dataset', methods=['GET', 'POST'])
def handle_dataset():
    """Get or update dataset information"""
    editor = get_user_editor()
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
        from rdflib.namespace import DCTERMS, DCAT, QB
        
        # Define namespaces
        SH = Namespace("http://www.w3.org/ns/shacl#")
        
        # Find NodeShapes (classes and dataset)
        node_shapes = list(g.subjects(RDF.type, SH.NodeShape))
        dataset_node = None
        created_nodes = {}
        
        print(f"Found {len(node_shapes)} NodeShapes")
        
        # First identify which NodeShape is the dataset
        dataset_shape = None
        for shape in node_shapes:
            # Check for dataset-specific indicators
            is_dataset = False
            
            # Check for data structure definition
            if (shape, RDF.type, QB.DataStructureDefinition) in g:
                is_dataset = True
            
            # Check for DCAT dataset type
            if (shape, RDF.type, DCAT.Dataset) in g:
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
            
            node = SHACLNode.from_dict(node_data)
            editor.nodes[node_id] = node
            created_nodes[str(shape)] = node_id
            
            print(f"Created {node_type}: {title}")
        
        # Second pass: Create data element nodes from PropertyShapes
        property_shapes = list(g.subjects(RDF.type, SH.PropertyShape))
        
        for prop_shape in property_shapes:
            # Handle object properties (class-to-class relationship) separately
            is_object_property = (prop_shape, RDF.type, OWL.ObjectProperty) in g
            
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
                
            # Extract enumeration values (sh:in)
            in_values = []
            in_lists = list(g.objects(prop_shape, SH['in']))
            if in_lists:
                # Follow the RDF list structure
                current = in_lists[0]
                while current and current != RDF.nil:
                    value_literals = list(g.objects(current, RDF.first))
                    if value_literals:
                        in_values.append(str(value_literals[0]))
                    next_nodes = list(g.objects(current, RDF.rest))
                    if next_nodes:
                        current = next_nodes[0]
                    else:
                        break
            
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
                'in_values': in_values
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
                        print(f"Mapped object property {title} to class reference")
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
            
            node = SHACLNode.from_dict(node_data)
            editor.nodes[node_id] = node
            created_nodes[str(prop_shape)] = node_id
            
            # Log message based on whether it has a concept link
            if conforms_to_uri:
                print(f"Created data element with concept link: {title}")
            else:
                print(f"Created data element: {title}")
        
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
    editor = get_user_editor()
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
        return jsonify({"error": "Failed to import TTL"}), 500

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
        print(f"Error importing example TTL: {str(e)}")
        return jsonify({"error": "Failed to import example TTL"}), 500

def detect_and_decode_csv(file_content: bytes, encoding: str = 'auto') -> tuple[str, str]:
    """
    Detect and decode CSV file content with the specified encoding.
    
    Args:
        file_content: Raw bytes from the uploaded file
        encoding: Encoding to use ('auto' for auto-detection, or specific encoding like 'utf-8', 'latin-1', etc.)
    
    Returns:
        Tuple of (decoded_content, actual_encoding_used)
    
    Raises:
        UnicodeDecodeError: If decoding fails with the specified encoding
    """
    # List of common encodings to try for auto-detection
    common_encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'windows-1252', 'cp1252', 'iso-8859-1']
    
    if encoding == 'auto':
        # First try chardet for intelligent detection
        try:
            detected = chardet.detect(file_content)
            detected_encoding = detected.get('encoding')
            confidence = detected.get('confidence', 0)
            
            print(f"Chardet detected encoding: {detected_encoding} (confidence: {confidence})")
            
            # If confidence is high enough, try the detected encoding first
            if detected_encoding and confidence > 0.7:
                try:
                    decoded = file_content.decode(detected_encoding)
                    print(f"Successfully decoded with detected encoding: {detected_encoding}")
                    return decoded, detected_encoding
                except (UnicodeDecodeError, LookupError) as e:
                    print(f"Failed to decode with detected encoding {detected_encoding}: {e}")
        except Exception as e:
            print(f"Chardet detection failed: {e}")
        
        # Fall back to trying common encodings
        for enc in common_encodings:
            try:
                decoded = file_content.decode(enc)
                print(f"Successfully decoded with fallback encoding: {enc}")
                return decoded, enc
            except (UnicodeDecodeError, LookupError):
                continue
        
        # If all else fails, use latin-1 which accepts all byte values
        decoded = file_content.decode('latin-1', errors='replace')
        print(f"Using latin-1 as last resort with error replacement")
        return decoded, 'latin-1'
    else:
        # Use the specified encoding
        try:
            decoded = file_content.decode(encoding)
            print(f"Successfully decoded with specified encoding: {encoding}")
            return decoded, encoding
        except (UnicodeDecodeError, LookupError) as e:
            raise UnicodeDecodeError(
                encoding, file_content, 0, len(file_content),
                f"Failed to decode CSV file with encoding '{encoding}'. Please try a different encoding."
            )

@app.route('/api/import/csv', methods=['POST'])
def import_csv():
    """Import a CSV file and convert to SHACL TTL"""
    with open('/tmp/csv_import.log', 'a') as f:
        f.write("=== CSV IMPORT FUNCTION CALLED ===\n")
    editor = get_user_editor()
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
        encoding = request.form.get('encoding', 'auto')
        
        print(f"Importing CSV file: {file.filename}, Dataset name: {dataset_name}, Language: {lang}, Encoding: {encoding}")
        
        # Read CSV data with proper encoding detection/handling
        file_content = file.read()
        try:
            csv_data, actual_encoding = detect_and_decode_csv(file_content, encoding)
            print(f"CSV decoded successfully with encoding: {actual_encoding}")
        except UnicodeDecodeError as e:
            print(f"Encoding error: {str(e)}")
            return jsonify({"error": f"Failed to decode CSV file. The file may not be in {encoding} encoding. Please try a different encoding."}), 400
        
        # Convert to TTL
        ttl = csv_to_ttl(csv_data, dataset_name, lang)
        
        if not ttl:
            return jsonify({"error": "Failed to convert CSV to TTL"}), 500
            
        print(f"Successfully converted CSV to TTL. Size: {len(ttl)} bytes")
        
        # Process the TTL to extract data structure
        try:
            with open('/tmp/csv_import.log', 'a') as f:
                f.write("Starting TTL processing...\n")
            # Use RDFLib to parse the TTL
            g = Graph()
            g.parse(data=ttl, format='turtle')
            SUG = Namespace("https://www.i14y.admin.ch/vocab#")
            with open('/tmp/csv_import.log', 'a') as f:
                f.write("TTL parsed successfully\n")
            
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
                with open('/tmp/csv_import.log', 'a') as f:
                    f.write(f"Found PropertyShape: {s}\n")
            
            with open('/tmp/csv_import.log', 'a') as f:
                f.write(f"Found {len(property_shapes)} property shapes in TTL\n")
            
            # Process each property shape
            for prop_idx, shape in enumerate(property_shapes):
                with open('/tmp/csv_import.log', 'a') as f:
                    f.write(f"Processing property shape {prop_idx + 1}/{len(property_shapes)}: {shape}\n")
                
                # Get property name (from sh:name or the URI)
                prop_name = None
                for _, _, name in g.triples((shape, SH.name, None)):
                    prop_name = str(name)
                    break
                
                if not prop_name:
                    # Extract from URI
                    prop_name = str(shape).split('/')[-1]
                
                with open('/tmp/csv_import.log', 'a') as f:
                    f.write(f"Property name: {prop_name}\n")
                
                # Get datatype
                datatype = None
                for _, _, dt in g.triples((shape, SH.datatype, None)):
                    datatype = str(dt)
                    break
                
                with open('/tmp/csv_import.log', 'a') as f:
                    f.write(f"Property datatype: {datatype}\n")
                
                # Create a data element node for this property
                data_element_node = SHACLNode('data_element', title=prop_name)
                data_element_node.datatype = datatype or "xsd:string"

                for _, _, value in g.triples((shape, SH.order, None)):
                    try:
                        data_element_node.order = int(value)
                    except (ValueError, TypeError):
                        pass
                    break

                for _, _, value in g.triples((shape, SUG.suggestedPattern, None)):
                    data_element_node.suggested_pattern = str(value)
                    break
                
                # Extract suggested enumeration values
                for _, _, value in g.triples((shape, SUG.suggestedInValues, None)):
                    try:
                        import json
                        data_element_node.suggested_in_values = json.loads(str(value))
                    except (ValueError, json.JSONDecodeError):
                        pass
                    break
                
                # Extract suggested min/max length
                for _, _, value in g.triples((shape, SUG.suggestedMinLength, None)):
                    try:
                        data_element_node.suggested_min_length = int(value)
                    except (ValueError, TypeError):
                        pass
                    break
                
                for _, _, value in g.triples((shape, SUG.suggestedMaxLength, None)):
                    try:
                        data_element_node.suggested_max_length = int(value)
                    except (ValueError, TypeError):
                        pass
                    break
                
                # Add to nodes and connect to dataset
                editor.nodes[data_element_node.id] = data_element_node
                dataset_node.connections.add(data_element_node.id)
                data_element_node.connections.add(dataset_node.id)
                
                # Create edge between dataset and data element
                edge_id = f"{dataset_node.id}_{data_element_node.id}"
                editor.edges[edge_id] = {
                    "id": edge_id,
                    "from": dataset_node.id,
                    "to": data_element_node.id,
                    "cardinality": "0..1"  # Default cardinality
                }
                
                with open('/tmp/csv_import.log', 'a') as f:
                    f.write(f"Created data element node {data_element_node.id} for property {prop_name}\n")
                    f.write(f"Current node count: {len(editor.nodes)}\n")
                
                # Extract constraints
                # Min/Max Count
                for _, _, value in g.triples((shape, SH.minCount, None)):
                    try:
                        data_element_node.min_count = int(value)
                        print(f"Set min_count: {data_element_node.min_count}")
                    except (ValueError, TypeError):
                        pass
                
                for _, _, value in g.triples((shape, SH.maxCount, None)):
                    try:
                        data_element_node.max_count = int(value)
                        print(f"Set max_count: {data_element_node.max_count}")
                    except (ValueError, TypeError):
                        pass
                
                # Min/Max Length
                for _, _, value in g.triples((shape, SH.minLength, None)):
                    try:
                        data_element_node.min_length = int(value)
                        print(f"Set min_length: {data_element_node.min_length}")
                    except (ValueError, TypeError):
                        pass
                
                for _, _, value in g.triples((shape, SH.maxLength, None)):
                    try:
                        data_element_node.max_length = int(value)
                        print(f"Set max_length: {data_element_node.max_length}")
                    except (ValueError, TypeError):
                        pass
                
                # Pattern
                for _, _, value in g.triples((shape, SH.pattern, None)):
                    data_element_node.pattern = str(value)
                    print(f"Set pattern: {data_element_node.pattern}")
                
                # Enumeration values (sh:in)
                for _, _, in_list in g.triples((shape, SH['in'], None)):
                    # Extract values from the RDF list
                    values_list = []
                    current = in_list
                    while current != RDF.nil:
                        for _, _, first_value in g.triples((current, RDF.first, None)):
                            values_list.append(str(first_value))
                        # Move to next item in list
                        rest_items = list(g.triples((current, RDF.rest, None)))
                        if rest_items:
                            current = rest_items[0][2]
                        else:
                            break
                    if values_list:
                        data_element_node.in_values = values_list
                        print(f"Set in_values: {data_element_node.in_values}")
            
            print(f"Successfully processed TTL. Created {len(property_shapes)} data element nodes.")
        except Exception as e:
            import traceback
            print(f"Error processing TTL: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()
            # Continue with basic import even if advanced processing fails
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        print(f"Error importing CSV: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to import CSV"}), 500

@app.route('/api/import/xsd', methods=['POST'])
def import_xsd():
    """Import an XSD file and convert to SHACL TTL"""
    editor = get_user_editor()
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        if not file.filename.endswith('.xsd'):
            return jsonify({"error": "Only XSD files are supported"}), 400
            
        # Get dataset name from form data
        dataset_name = request.form.get('dataset_name', os.path.splitext(file.filename)[0])
        
        print(f"Importing XSD file: {file.filename}, Dataset name: {dataset_name}")
        
        # Read XSD data
        xsd_data = file.read().decode('utf-8')
        
        # Convert to TTL
        ttl = xsd_to_ttl(xsd_data, dataset_name)
        
        if not ttl:
            return jsonify({"error": "Failed to convert XSD to TTL"}), 500
            
        print(f"Successfully converted XSD to TTL. Size: {len(ttl)} bytes")
        
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
            
            # Clear edges
            editor.edges = {}
            
            # Create or update dataset node with the provided name
            if dataset_node:
                dataset_node.title = dataset_name
                dataset_node.description = f"Dataset imported from {file.filename}"
                # Clear any existing connections
                dataset_node.connections = set()
            else:
                dataset_node = SHACLNode('dataset', title=dataset_name, description=f"Dataset imported from {file.filename}")
                editor.nodes[dataset_node.id] = dataset_node
            
            print(f"Using dataset node: {dataset_node.id} with title: {dataset_node.title}")
            
            # Track processed node shapes for edge creation
            processed_nodes = {}
            
            # Find all NodeShapes (these become classes/concepts)
            node_shapes = []
            for s, p, o in g.triples((None, RDF.type, SH.NodeShape)):
                node_shapes.append(s)
            
            print(f"Found {len(node_shapes)} node shapes in TTL")
            
            # Process each node shape
            for shape_uri in node_shapes:
                # Get node name (from sh:name or the URI)
                node_name = None
                for _, _, name in g.triples((shape_uri, SH.name, None)):
                    node_name = str(name)
                    break
                
                if not node_name:
                    # Extract from URI
                    node_name = str(shape_uri).split('/')[-1]
                
                # Get description
                description = ""
                for desc_prop in [SH.description, RDFS.comment, DCTERMS.description]:
                    for _, _, desc in g.triples((shape_uri, desc_prop, None)):
                        description = str(desc)
                        break
                    if description:
                        break
                
                # Determine node type based on properties
                # If it has a datatype, it's more like a data element
                # Otherwise, it's a class
                has_datatype = False
                for _, _, _ in g.triples((shape_uri, SH.datatype, None)):
                    has_datatype = True
                    break
                
                # Create appropriate node
                node_type = 'data_element' if has_datatype else 'class'
                shacl_node = SHACLNode(node_type, title=node_name, description=description)
                
                # Add datatype if present
                if has_datatype:
                    for _, _, dt in g.triples((shape_uri, SH.datatype, None)):
                        shacl_node.datatype = str(dt)
                        break
                
                # Add constraints for data elements
                if node_type == 'data_element':
                    # Min/Max Length
                    for _, _, value in g.triples((shape_uri, SH.minLength, None)):
                        try:
                            shacl_node.min_length = int(value)
                        except (ValueError, TypeError):
                            pass
                    
                    for _, _, value in g.triples((shape_uri, SH.maxLength, None)):
                        try:
                            shacl_node.max_length = int(value)
                        except (ValueError, TypeError):
                            pass
                    
                    # Pattern
                    for _, _, value in g.triples((shape_uri, SH.pattern, None)):
                        shacl_node.pattern = str(value)
                
                # Add to editor nodes
                editor.nodes[shacl_node.id] = shacl_node
                processed_nodes[str(shape_uri)] = shacl_node
                
                # Connect to dataset
                edge_id = f"{dataset_node.id}-{shacl_node.id}"
                editor.edges[edge_id] = {
                    'id': edge_id,
                    'from': dataset_node.id,
                    'to': shacl_node.id,
                    'cardinality': '1..1'
                }
                dataset_node.connections.add(shacl_node.id)
                shacl_node.connections.add(dataset_node.id)
                
                print(f"Created {node_type} node {shacl_node.id} for shape {node_name} (has_datatype={has_datatype})")
            
            # Process property shapes to establish connections between nodes
            property_shapes = []
            for s, p, o in g.triples((None, RDF.type, SH.PropertyShape)):
                property_shapes.append(s)
            
            # Look for sh:node references to establish connections
            for shape_uri in node_shapes:
                if str(shape_uri) not in processed_nodes:
                    continue
                
                source_node = processed_nodes[str(shape_uri)]
                
                # Find properties that reference other nodes
                for _, _, prop_shape in g.triples((shape_uri, SH.property, None)):
                    for _, _, target_shape in g.triples((prop_shape, SH.node, None)):
                        if str(target_shape) in processed_nodes:
                            target_node = processed_nodes[str(target_shape)]
                            
                            # Create edge between source and target
                            edge_id = f"{source_node.id}-{target_node.id}"
                            if edge_id not in editor.edges:
                                editor.edges[edge_id] = {
                                    'id': edge_id,
                                    'from': source_node.id,
                                    'to': target_node.id,
                                    'cardinality': '1..1'
                                }
                                source_node.connections.add(target_node.id)
                                target_node.connections.add(source_node.id)
            
            print(f"Successfully processed XSD. Created {len(processed_nodes)} nodes and {len(editor.edges)} edges.")
        except Exception as e:
            import traceback
            print(f"Error processing TTL from XSD: {str(e)}")
            print(traceback.format_exc())
            # Continue with basic import even if advanced processing fails
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        print(f"Error importing XSD: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "An internal error occurred."}), 500

@app.route('/api/nodes/<node_id>/convert-to-dataset', methods=['POST'])
def convert_to_dataset(node_id):
    """Convert a class node to a dataset node"""
    user_editor = get_user_editor()
    
    # Check if node exists
    if node_id not in user_editor.nodes:
        return jsonify({"error": "Node not found"}), 404
    
    node = user_editor.nodes[node_id]
    
    # Check if node is a class
    if node.type != 'class':
        return jsonify({"error": "Only class nodes can be converted to dataset"}), 400
    
    # Check if there's already a dataset node
    existing_dataset = None
    for n in user_editor.nodes.values():
        if n.type == 'dataset' and n.id != node_id:
            existing_dataset = n
            break
    
    if existing_dataset:
        return jsonify({
            "error": "A dataset node already exists. Please delete it first.",
            "dataset_id": existing_dataset.id
        }), 400
    
    # Convert the class to a dataset
    node.type = 'dataset'
    
    # Remove any connections where this node is the target
    # (datasets can't be targets of connections)
    edges_to_remove = []
    for edge_id, edge in user_editor.edges.items():
        if edge['to'] == node_id:
            edges_to_remove.append(edge_id)
            # Also remove the connection in the nodes
            if edge['from'] in user_editor.nodes:
                user_editor.nodes[edge['from']].connections.discard(node_id)
            node.connections.discard(edge['from'])
    
    for edge_id in edges_to_remove:
        user_editor.edges.pop(edge_id)
    
    return jsonify({"success": True, "node": node.to_dict()})

@app.route('/api/nodes/update-order', methods=['POST'])
def update_nodes_order():
    """Update the order field for multiple data elements at once"""
    user_editor = get_user_editor()
    data = request.json
    
    if not data or 'orders' not in data:
        return jsonify({"error": "Missing 'orders' in request body"}), 400
    
    orders = data['orders']  # Expected format: [{"node_id": "...", "order": 0}, ...]
    
    updated_count = 0
    errors = []
    
    for item in orders:
        node_id = item.get('node_id')
        order = item.get('order')
        
        if not node_id:
            errors.append({"error": "Missing node_id", "item": item})
            continue
        
        if node_id not in user_editor.nodes:
            errors.append({"error": f"Node {node_id} not found", "item": item})
            continue
        
        node = user_editor.nodes[node_id]
        
        # Set the order (convert to int or None)
        try:
            node.order = int(order) if order not in [None, ''] else None
            updated_count += 1
        except (ValueError, TypeError):
            errors.append({"error": f"Invalid order value for node {node_id}", "item": item})
    
    return jsonify({
        "success": True,
        "updated_count": updated_count,
        "errors": errors if errors else None
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5002))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print("Starting SHACL Editor Web Application...")
    print(f"Access the application at: http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=port, debug=debug)