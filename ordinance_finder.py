import os
import json
import re
from typing import Dict, Optional
from flask import Flask, request, jsonify, render_template
from anthropic import Anthropic
from dotenv import load_dotenv
from analysis_api import register_to

# Load environment variables
load_dotenv()

app = Flask(__name__)
register_to(app)

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
    
    prompt = f"""You are an expert assistant specializing in finding municipal documents. Your sole mission is to find a direct link to the most recent, official PDF of a city's zoning ordinance or bylaw.

The city is: **{city_name}**

**Your Process:**
1.  **Prioritize PDF-focused searches.** Use precise search terms like `"{city_name} zoning bylaw filetype:pdf"` and `"{city_name} town code chapter zoning"`.
2.  **Analyze Search Results.** Look for links from official government domains (e.g., `.gov`, `.gov.uk`, `.ca.gov`). These are the most trustworthy sources.
3.  **Handle Web Pages.** If your search leads to a webpage instead of a direct PDF, you must **analyze the page's content** for phrases like "Zoning Bylaw," "Download the Code," or "Chapter 174" to find the actual download link for the PDF document. Do not just return the link to the webpage.
4.  **Verify Recency.** Check for a date on the document to ensure it's the most recent version. Note this date.

**Output Format:**
Return your findings *only* in the following XML format.

<zoning_ordinance>
<city>{city_name}</city>
<link>INSERT THE DIRECT .PDF LINK HERE</link>
<file_type>PDF</file_type>
<notes>Note the document's date and why you believe it is the correct one. If you absolutely cannot find a direct PDF link after analyzing webpages, explain why here.</notes>
</zoning_ordinance>
"""
    
    try:
        # Using the correct web search tool syntax from Anthropic documentation
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
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