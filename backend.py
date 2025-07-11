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
    """Get zoning ordinance information for a city using Claude API."""
    
    prompt = f"""
You are tasked with finding the most recent version of a city's zoning ordinance, code, or bylaw for development. Your goal is to return a concise result with a working web link to the document, preferably in PDF format.

The city name you will be searching for is:
<city_name>
{city_name}
</city_name>

Follow these steps to complete the task:

1. Conduct a web search for the zoning ordinance of the specified city. Use search terms like "[CITY_NAME] zoning ordinance", "[CITY_NAME] zoning code", or "[CITY_NAME] development bylaw".

2. Verify that you have found the most recent version of the ordinance. Look for:
   - Date of publication or last update
   - Any mentions of recent amendments or revisions
   - News articles or press releases about recent zoning changes

3. Ensure that the document you've found is the official, comprehensive zoning ordinance for the entire city, not just a specific district or a summary of regulations.

4. Check that the web link to the document is functional and, if possible, leads directly to a PDF version of the ordinance.

5. If you cannot find a PDF version, provide a link to the most accessible official version available (e.g., a web page with the full text).

6. If you encounter multiple versions or conflicting information, briefly explain your reasoning for selecting a particular version as the most recent.

Return your findings in the following format:

<zoning_ordinance>
<city>Insert the city name here</city>
<link>Insert the direct link to the ordinance document here</link>
<file_type>Specify whether it's a PDF or another format</file_type>
<notes>Include any brief, relevant notes about the document or your search process here. This field is optional and should only be used if necessary.</notes>
</zoning_ordinance>

If you cannot find the zoning ordinance or are unsure about its validity, explain the issue briefly in the <notes> section.

Remember to focus solely on finding and returning the ordinance information. Do not include any analysis of the ordinance content or any other extraneous information.
"""
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = response.content[0].text
        return parse_zoning_response(response_text)
        
    except Exception as e:
        raise Exception(f"Error calling Claude API: {str(e)}")

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
        
        # Get zoning ordinance information
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
    
    app.run(debug=True, host='0.0.0.0', port=5000)
