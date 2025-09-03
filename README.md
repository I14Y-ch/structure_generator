# SHACL Editor for I14Y

A web-based SHACL editor specifically designed for the Swiss interoperability platform I14Y. This application allows you to create and edit SHACL (Shapes Constraint Language) graphs for datasets, concepts, and classes, with full integration to the I14Y platform.

## Key Features

### Web-based Graph Editor
- **User-friendly Interface**: Easy-to-use web interface for creating and editing SHACL shapes
- **Node Types**: Dataset (red), Concepts (blue), and Classes (green)
- **Visual Organization**: Hierarchical node structure with intuitive navigation
- **Connection Management**: Simple management of node relationships

### I14Y Platform Integration
- **Concept Search**: Direct integration with I14Y REST API
- **Multilingual Support**: Full support for German, French, Italian, and English
- **Metadata Preservation**: Maintains I14Y concept IDs and multilingual descriptions
- **Automatic Datatype Detection**: Smart datatype assignment based on concept semantics

### Export Capabilities
- **I14Y-Compatible TTL**: Generates TTL files that match I14Y's specific format requirements
- **SHACL Compliance**: Full SHACL vocabulary support with proper constraints
- **Multilingual Export**: All labels and descriptions in 4 languages
- **Project Management**: Save/load project files for continued editing

## Installation

1. Ensure you have Python 3.8+ installed
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Starting the Application
```bash
python run_flask.py
```
Then open your browser and navigate to: http://localhost:5002
Then open your browser and navigate to: http://localhost:5002

### Basic Workflow

1. **Dataset Setup**:
   - The application starts with a default "Dataset" node
   - Edit the dataset title and description when selected
   - This becomes the main `QB:DataStructureDefinition`

2. **Adding Elements**:
   - **+ Add Custom Concept**: Create your own concept with custom title/description
   - **+ Search I14Y Concept**: Search the I14Y platform for existing concepts
   - **+ Add Class**: Create a class to group related concepts

3. **Graph Interaction**:
   - **Select Nodes**: Click nodes to select them (turns yellow when selected)
   - **Connect**: Select exactly 2 nodes, then click "Connect Nodes"
   - **Disconnect**: Select 2 connected nodes, then click "Disconnect Nodes"
   - **Remove**: Select nodes and click "Remove Selected" (except dataset)

4. **Export Options**:
   - **Export as TTL**: Generate I14Y-compatible SHACL TTL file
   - **Save Project**: Save current work as JSON for later editing
   - **Load Project**: Load previously saved project

### Graph Elements

| Element | Color | Purpose | Example |
|---------|-------|---------|---------|
| **Dataset** | Red | Main data structure definition | "Beta-ID", "Population Census" |
| **Concepts** | Blue | Individual data concepts | "Family Name", "Birth Date", "Age" |
| **Classes** | Green | Groupings of related concepts | "Personal Data", "Demographics" |

## I14Y Integration Details

### API Integration
- **Endpoint**: `https://apiconsole.i14y.admin.ch/public/v1/concepts`
- **Search**: Real-time concept search with multilingual results
- **Metadata**: Preserves full I14Y concept metadata and references

### Multilingual Support
All I14Y concepts maintain their multilingual labels and descriptions:
- **German (de)**: Primary language for Swiss federal data
- **French (fr)**: Second official language
- **Italian (it)**: Third official language  
- **English (en)**: International/technical documentation

## TTL Export Format

The exported TTL files follow I14Y-specific standards:

```turtle
@prefix i14y: <https://www.i14y.admin.ch/resources/datasets/dataset_id/structure/>.
@prefix QB: <http://purl.org/linked-data/cube#>.
@prefix sh: <http://www.w3.org/ns/shacl#>.
# ... other standard prefixes

i14y:dataset_name dcterms:title "Dataset Name"@de,
                                "Dataset Name"@en,
                                "Dataset Name"@fr,
                                "Dataset Name"@it;
                  pav:version "1.0.0";
                  a QB:DataStructureDefinition,
                    rdfs:Class,
                    sh:NodeShape;
                  sh:property <property-uri-1>,
                              <property-uri-2>;
                  schema:validFrom "2025-08-25"^^xsd:date;
                  schema:version "1.0.0".

<property-uri> dcterms:conformsTo <i14y-concept-uri>;
               dcterms:description "Description"@de,
                                   "Description"@fr,
                                   "Description"@it,
                                   "Description"@en;
               dcterms:title "Title"@de,
                             "Title"@fr,
                             "Title"@it,
                             "Title"@en;
               a QB:AttributeProperty,
                 owl:DatatypeProperty,
                 sh:PropertyShape;
               sh:datatype xsd:string;
               sh:order 1;
               sh:path <property-uri>.
```

### Key Format Features
- **I14Y Namespaces**: Uses actual I14Y URIs and structure
- **Concept References**: `dcterms:conformsTo` links to I14Y concept descriptions
- **Property Ordering**: `sh:order` maintains logical sequence
- **Datatype Detection**: Automatic XSD datatype assignment
- **Full Compliance**: Matches `data/example1.ttl` format requirements

## Testing

Run the test suite to verify functionality:
```bash
python test_app.py
```

This will:
- Test TTL generation with sample data
- Verify node serialization/deserialization
- Generate sample output files
- Validate I14Y format compliance

## File Structure

```
shacl-creator/
├── app.py                    # Main application
├── test_app.py              # Test suite
├── requirements.txt         # Python dependencies
├── README.md               # This documentation
└── data/
    ├── example1.ttl        # Target I14Y format template
    └── generated_sample.ttl # Generated test output
```

## Technical Architecture

### Core Components
- **FlaskSHACLGraphEditor**: Main web application class
- **SHACLNode**: Enhanced node representation with I14Y support
- **I14YAPIClient**: REST API client for concept search
- **CSVToSHACL**: Converter for importing CSV data

### Key Technologies
- **Web Framework**: Flask for the web application
- **Frontend**: HTML, CSS, JavaScript with Bootstrap
- **API Integration**: Requests library for I14Y REST calls
- **Data Format**: TTL (Turtle) with SHACL and I14Y vocabularies
- **Project Storage**: JSON for save/load functionality

## Use Cases

### 1. Creating New Datasets
- Define a new dataset structure using I14Y concepts
- Mix custom concepts with existing I14Y vocabulary
- Export for validation and publication

### 2. Extending Existing Datasets  
- Load existing project files
- Add new concepts or modify relationships
- Maintain version control through project saves

### 3. I14Y Concept Discovery
- Search the I14Y platform for relevant concepts
- Preview concept metadata before adding
- Ensure consistency with Swiss data standards

### 4. Educational/Training
- Visualize SHACL structures for learning
- Understand I14Y platform organization
- Practice data modeling with real concepts

## Troubleshooting

### Common Issues
- **API Connection**: Ensure internet access for I14Y concept search
- **Dependencies**: Verify all Python packages are correctly installed
- **Browser Compatibility**: Use a modern browser like Chrome, Firefox, or Edge

### Error Messages
- **"No dataset found"**: Ensure at least one dataset node exists
- **"Invalid Selection"**: Check node selection for connection operations
- **"Export Error"**: Verify file permissions for TTL export location

## Contributing

This tool is designed specifically for I14Y platform integration. When contributing:
- Maintain compatibility with I14Y TTL format requirements
- Preserve multilingual support for all features
- Test with real I14Y concepts when possible
- Follow Swiss federal data standards

## License

This project is designed for use with the Swiss I14Y interoperability platform and follows Swiss federal open data principles.
