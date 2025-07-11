import os
import json
import re
from typing import Dict, Optional
from flask import Flask, request, jsonify, render_template_string
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>City Zoning Ordinance Finder</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { background: #f5f5f5; padding: 20px; border-radius: 10px; margin: 20px 0; }
        input[type="text"] { width: 300px; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #005a87; }
        .result { margin-top: 20px; padding: 15px; background: white; border-radius: 5px; border-left: 4px solid #007cba; }
        .error { border-left-color: #dc3545; background: #f8d7da; }
        .loading { color: #666; font-style: italic; }
        a { color: #007cba; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>City Zoning Ordinance Finder</h1>
    <div class="container">
        <form id="zoningForm">
            <label for="city">Enter City Name:</label><br>
            <input type="text" id="city" name="city" placeholder="e.g., San Francisco, CA" required>
            <button type="submit">Find Zoning Ordinance</button>
        </form>
    </div>
    
    <div id="result"></div>

    <script>
        document.getElementById('zoningForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const city = document.getElementById('city').value;
            const resultDiv = document.getElementById('result');
            
            resultDiv.innerHTML = '<div class="result loading">Searching for zoning ordinance...</div>';
            
            try {
                const response = await fetch('/api/zoning', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({city: city})
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    resultDiv.innerHTML = `
                        <div class="result">
                            <h3>Zoning Ordinance Found for ${data.city}</h3>
                            <p><strong>Document Link:</strong> <a href="${data.link}" target="_blank">${data.link}</a></p>
                            <p><strong>File Type:</strong> ${data.file_type}</p>
                            ${data.notes ? `<p><strong>Notes:</strong> ${data.notes}</p>` : ''}
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `<div class="result error">Error: ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="result error">Error: ${error.message}</div>`;
            }
        });
    </script>
</body>
</html>
"""

def parse_zoning_response(response_text: str) -> Dict:
    """Parse the Claude response to extract zoning ordinance information."""
    # Look for the zoning_ordinance tags
    pattern = r'<zoning_ordinance>(.*?)</zoning_ordinance>'
    match = re.search(pattern, response_text, re.DOTALL)
    
    if not match:
        raise ValueError("No zoning ordinance information found in response")
    
    content = match.group(1)
    
    # Extract individual fields
    def extract_field(field_name: str, content: str) -> Optional[str]:
        pattern = f'<{field_name}>(.*?)</{field_name}>'
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else None
    
    return {
        'city': extract_field('city', content),
        'link': extract_field('link', content),
        'file_type': extract_field('file_type', content),
        'notes': extract_field('notes', content)
    }

def get_zoning_ordinance(city_name: str) -> Dict:
    """Get zoning ordinance information for a city using Claude with web search tools."""
    
    prompt = f"""
You are tasked with finding the most recent version of a city's zoning ordinance, code, or bylaw for development. Your goal is to return a concise result with a working web link to the document, preferably in PDF format.

The city name you will be searching for is:
<city_name>
{city_name}
</city_name>

Follow these steps to complete the task:

1. Search the web for the zoning ordinance of the specified city. Use search terms like:
   - "{city_name} zoning ordinance filetype:pdf"
   - "{city_name} zoning code official"
   - "{city_name} municipal code zoning"

2. Look for official government websites (.gov domains preferred)

3. Verify that you have found the most recent version of the ordinance by:
   - Checking the date of publication or last update
   - Looking for mentions of recent amendments or revisions
   - Ensuring it's the comprehensive city-wide ordinance, not just a district-specific document

4. Prioritize:
   - Direct PDF links over web pages
   - Official city/government websites over third-party sites
   - Recent documents over archived versions

5. If you find multiple versions, explain your reasoning for selecting the most recent/official one

Return your findings in the following format:

<zoning_ordinance>
<city>{city_name}</city>
<link>Insert the direct link to the ordinance document here</link>
<file_type>Specify whether it's a PDF, web page, or other format</file_type>
<notes>Include brief notes about the document, its date, or your search process if relevant</notes>
</zoning_ordinance>

If you cannot find a reliable zoning ordinance, explain the issue in the <notes> section and suggest alternatives like contacting the city directly.

Use the web search tool to find current, accurate information. Do not rely on your training data for specific document links.
"""
    
    try:
        # Using the correct web search tool syntax from Anthropic documentation
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search"
                }
            ],
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the final text response
        final_response = ""
        for content in response.content:
            if content.type == "text":
                final_response += content.text
        
        return parse_zoning_response(final_response)
        
    except Exception as e:
        raise Exception(f"Error calling Claude API with web search: {str(e)}")

@app.route('/')
def home():
    """Serve the web interface."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/zoning', methods=['POST'])
def api_zoning():
    """API endpoint to get zoning ordinance information."""
    try:
        data = request.get_json()
        
        if not data or 'city' not in data:
            return jsonify({'error': 'City name is required'}), 400
        
        city_name = data['city'].strip()
        
        if not city_name:
            return jsonify({'error': 'City name cannot be empty'}), 400
        
        # Get zoning ordinance information using web search
        result = get_zoning_ordinance(city_name)
        
        # Validate that we got the required fields
        if not result.get('city') or not result.get('link'):
            return jsonify({'error': 'Could not find zoning ordinance information'}), 404
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Check if API key is set
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable is not set")
        print("Please create a .env file with your API key or set it as an environment variable")
        exit(1)
    
    print("Starting Zoning Ordinance Finder with Anthropic Web Search...")
    print("Available at: http://localhost:8000")
    app.run(debug=True, host='0.0.0.0', port=8000)