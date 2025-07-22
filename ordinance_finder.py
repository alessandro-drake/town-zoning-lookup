import os
import json
import re
from typing import Dict, Optional
from flask import Flask, request, jsonify, render_template
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

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
    return render_template('index.html')

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