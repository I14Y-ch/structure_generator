# SHACL Creator for I14Y

A web-based visual editor for creating SHACL shapes compatible with the Swiss I14Y interoperability platform.

## Features

- **Visual Graph Editor**: Drag-and-drop interface for datasets, concepts, and classes
- **I14Y Integration**: Direct search and integration with I14Y concept catalog
- **Multilingual Support**: German, French, Italian, and English
- **TTL Export**: Generates I14Y-compatible SHACL files for upload
- **Data Import**: Import from CSV files and XSD schemas
- **Project Management**: Save/load projects as JSON
- **Multi-User Support**: Session-based isolation allowing concurrent users without workspace interference
- **Automatic Cleanup**: Expired user sessions are automatically cleaned up to prevent memory leaks

## Quick Start

1. **Setup virtual environment** (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open browser**: Navigate to http://localhost:5002

## Usage

### Graph Elements
- **Dataset** (red): Main data structure definition
- **Concepts** (blue): Data fields (searchable from I14Y or custom)
- **Classes** (green): Groupings of related concepts

### Import Options
- **CSV Import**: Upload structured data from CSV files
- **XSD Import**: Convert XML Schema Definitions (XSD) to SHACL shapes
- **TTL Import**: Load existing SHACL TTL files

## Export Format

Generates TTL files following I14Y standards:
- Uses proper I14Y namespaces and URIs
- Includes `dcterms:conformsTo` references to I14Y concepts
- Maintains multilingual labels and descriptions
- Adds proper SHACL constraints and datatypes

## Technical Details

- **Backend**: Flask with RDFLib for TTL generation
- **Frontend**: HTML/JavaScript with Bootstrap UI
- **I14Y API**: REST integration for concept search
- **Export**: SHACL-compliant TTL with I14Y-specific formatting
- **Production**: Gunicorn WSGI server for production deployment
- **Multi-User Architecture**: Session-based user isolation with automatic cleanup
  - Each user gets a unique session ID and isolated workspace
  - Expired sessions (default: 2 hours inactivity) are automatically cleaned up
  - Background cleanup thread runs every 30 minutes to free memory
  - Concurrent users can work independently without interference