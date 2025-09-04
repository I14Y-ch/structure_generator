# SHACL Creator for I14Y

A web-based visual editor for creating SHACL shapes compatible with the Swiss I14Y interoperability platform.

## Features

- **Visual Graph Editor**: Drag-and-drop interface for datasets, concepts, and classes
- **I14Y Integration**: Direct search and integration with I14Y concept catalog
- **Multilingual Support**: German, French, Italian, and English
- **TTL Export**: Generates I14Y-compatible SHACL files for upload
- **Project Management**: Save/load projects as JSON

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

# Export Format

Generates TTL files following I14Y standards:
- Uses proper I14Y namespaces and URIs
- Includes `dcterms:conformsTo` references to I14Y concepts
- Maintains multilingual labels and descriptions
- Adds proper SHACL constraints and datatypes