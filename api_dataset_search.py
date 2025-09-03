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
