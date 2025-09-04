# SHACL Creator for I14Y

A web-based visual editor for creating SHACL shapes compatible with the Swiss I14Y interoperability platform.

## Features

- **Visual Graph Editor**: Drag-and-drop interface for datasets, concepts, and classes
- **I14Y Integration**: Direct search and integration with I14Y concept catalog
- **Multilingual Support**: German, French, Italian, and English
- **TTL Export**: Generates I14Y-compatible SHACL files for upload
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

## Deployment

### Digital Ocean App Platform

1. Fork this repository to your GitHub account (if not already done)
2. Create a new app on [Digital Ocean App Platform](https://cloud.digitalocean.com/apps)
3. Connect your GitHub repository
4. Select the `structure_generator` repository
5. Use the following settings:
   - **Source**: GitHub repository
   - **Branch**: main
   - **Autodeploy**: Enabled (recommended)
   - **Build Command**: Auto-detected
   - **Run Command**: `python app.py`
6. Deploy with the default settings

The app will automatically:
- Detect Python environment from `runtime.txt`
- Install dependencies from `requirements.txt`
- Run on port 8080 (configured via `PORT` environment variable)
- Use production settings when `FLASK_ENV=production`

### Environment Variables

The following environment variables are automatically configured:
- `PORT`: Set to 8080 by Digital Ocean App Platform
- `FLASK_ENV`: Set to 'production' for production deployment (disables debug mode)

### Alternative: Using Gunicorn

If you prefer to use Gunicorn as the WSGI server, Digital Ocean will automatically detect the `Procfile` and use:
```
gunicorn --bind 0.0.0.0:$PORT app:app
```

## Usage

### Graph Elements
- **Dataset** (red): Main data structure definition
- **Concepts** (blue): Data fields (searchable from I14Y or custom)
- **Classes** (green): Groupings of related concepts

### Basic Workflow
1. Start with the default Dataset node
2. Add concepts: "+ Search I14Y Concept" or "+ Add Custom Concept"
3. Add classes: "+ Add Class" to group related concepts
4. Connect elements: Select 2 nodes → "Connect Nodes"
5. Export: "Export as TTL" for I14Y upload

### Key Operations
- **Select**: Click nodes (turns yellow when selected)
- **Connect**: Select exactly 2 nodes, then "Connect Nodes"
- **Remove**: Select nodes → "Remove Selected"
- **Edit**: Select single node to edit properties in sidebar

## Export Format

Generates TTL files following I14Y standards:
- Uses proper I14Y namespaces and URIs
- Includes `dcterms:conformsTo` references to I14Y concepts
- Maintains multilingual labels and descriptions
- Adds proper SHACL constraints and datatypes

## File Structure

```
├── app.py              # Main Flask application
├── csv_converter.py    # CSV converter utility
├── requirements.txt    # Python dependencies
├── app.yaml           # Digital Ocean App Platform configuration
├── Procfile           # Alternative: Gunicorn configuration
├── runtime.txt        # Python version specification
├── README.md          # This documentation
├── templates/
│   └── index.html     # Main web interface
├── static/css/
│   └── styles.css     # Application styles
├── data/              # Sample data files
└── tst/               # Test files and examples
```

## Troubleshooting

### Local Development
- **Port conflicts**: Change port in `app.py` if 5002 is unavailable
- **I14Y search issues**: Requires internet connection for concept search
- **Upload errors**: Ensure TTL file has valid SHACL structure and all required `sh:name` properties

### Digital Ocean Deployment
- **Health check failures**: App must respond on the assigned port (8080)
- **Build failures**: Check that all dependencies are listed in `requirements.txt`
- **Runtime errors**: Check app logs in Digital Ocean dashboard for detailed error messages

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