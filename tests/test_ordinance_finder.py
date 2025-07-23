# tests/test_ordinance_finder.py

import pytest
import json
from unittest.mock import MagicMock, patch

# Import the Flask app instance and functions from your module
from ordinance_finder import app, parse_zoning_response, get_zoning_ordinance

# -----------------
# Pytest Fixtures
# -----------------

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as client:
        yield client

# -----------------
# ## 1. parse_zoning_response Tests
# Tests the pure function responsible for parsing the AI's text response.
# -----------------

def test_parse_zoning_response_success():
    """Test successful parsing of a well-formed response."""
    response_text = """
    Some introductory text from the model.
    <zoning_ordinance>
        <city>Sunnyvale</city>
        <link>http://example.com/sunnyvale-zoning.pdf</link>
        <file_type>PDF</file_type>
        <notes>This is the most recent version from the official city website.</notes>
    </zoning_ordinance>
    Some concluding text.
    """
    expected = {
        'city': 'Sunnyvale',
        'link': 'http://example.com/sunnyvale-zoning.pdf',
        'file_type': 'PDF',
        'notes': 'This is the most recent version from the official city website.'
    }
    assert parse_zoning_response(response_text) == expected

def test_parse_zoning_response_missing_fields():
    """Test parsing when some optional fields are missing."""
    response_text = """
    <zoning_ordinance>
        <city>Gotham</city>
        <link>http://gotham.gov/code</link>
    </zoning_ordinance>
    """
    expected = {
        'city': 'Gotham',
        'link': 'http://gotham.gov/code',
        'file_type': None,
        'notes': None
    }
    assert parse_zoning_response(response_text) == expected

def test_parse_zoning_response_with_extra_whitespace():
    """Test that whitespace around content is correctly stripped."""
    response_text = """
    <zoning_ordinance>
        <city>
            Metropolis
        </city>
        <link>
            http://metropolis.com/zoning
        </link>
    </zoning_ordinance>
    """
    result = parse_zoning_response(response_text)
    assert result['city'] == 'Metropolis'
    assert result['link'] == 'http://metropolis.com/zoning'

def test_parse_zoning_response_no_main_tag_raises_error():
    """Test that a ValueError is raised if the <zoning_ordinance> tag is missing."""
    response_text = "Sorry, I could not find the zoning ordinance for that city."
    with pytest.raises(ValueError, match="No zoning ordinance information found in response"):
        parse_zoning_response(response_text)

# -----------------
# ## 2. get_zoning_ordinance Tests
# Tests the function that interacts with the Anthropic API.
# -----------------

@patch('ordinance_finder.client')
def test_get_zoning_ordinance_success(mock_anthropic_client):
    """Test the happy path where Claude returns a valid, parsable response."""
    # Mock the API response object
    mock_response = MagicMock()
    # The response.content is a list, so we mock that
    mock_response.content = [
        MagicMock(type="text", text="""
        <zoning_ordinance>
            <city>Testville</city>
            <link>http://test.com/zoning.pdf</link>
            <file_type>PDF</file_type>
            <notes>Found it!</notes>
        </zoning_ordinance>
        """)
    ]
    mock_anthropic_client.messages.create.return_value = mock_response

    result = get_zoning_ordinance("Testville")

    # Assert that the API was called correctly
    mock_anthropic_client.messages.create.assert_called_once()
    assert "Testville" in mock_anthropic_client.messages.create.call_args[1]['messages'][0]['content']

    # Assert that the parsed result is correct
    assert result['city'] == 'Testville'
    assert result['link'] == 'http://test.com/zoning.pdf'

@patch('ordinance_finder.client')
def test_get_zoning_ordinance_api_error(mock_anthropic_client):
    """Test that an exception from the Claude API is caught and re-raised."""
    mock_anthropic_client.messages.create.side_effect = Exception("API connection timed out")

    with pytest.raises(Exception, match="Error calling Claude API with web search: API connection timed out"):
        get_zoning_ordinance("Nowhere")

@patch('ordinance_finder.client')
def test_get_zoning_ordinance_unparsable_response(mock_anthropic_client):
    """Test when Claude responds successfully but without the required format."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="I looked everywhere but could not find it.")]
    mock_anthropic_client.messages.create.return_value = mock_response

    # The function should catch the parsing ValueError and wrap it.
    with pytest.raises(Exception, match="No zoning ordinance information found in response"):
        get_zoning_ordinance("Atlantis")


# -----------------
# ## 3. Flask API Endpoint Tests
# Tests the web routes of the application.
# -----------------

def test_health_check(client):
    """Test the /health endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'healthy'}

@patch('ordinance_finder.get_zoning_ordinance')
def test_api_zoning_success(mock_get_ordinance, client):
    """Test the /api/zoning endpoint with a successful lookup."""
    mock_get_ordinance.return_value = {
        'city': 'Springfield',
        'link': 'http://springfield.gov/zoning.pdf',
        'file_type': 'PDF',
        'notes': 'Official document.'
    }

    response = client.post('/api/zoning', json={'city': 'Springfield'})
    
    assert response.status_code == 200
    assert response.get_json()['city'] == 'Springfield'
    assert response.get_json()['link'] == 'http://springfield.gov/zoning.pdf'
    mock_get_ordinance.assert_called_once_with('Springfield')

def test_api_zoning_no_city_data(client):
    """Test the /api/zoning endpoint when the 'city' field is missing."""
    response = client.post('/api/zoning', json={'location': 'Shelbyville'})
    assert response.status_code == 400
    assert 'City name is required' in response.get_json()['error']

def test_api_zoning_empty_city_data(client):
    """Test the /api/zoning endpoint when the 'city' field is empty."""
    response = client.post('/api/zoning', json={'city': '  '})
    assert response.status_code == 400
    assert 'City name cannot be empty' in response.get_json()['error']

@patch('ordinance_finder.get_zoning_ordinance')
def test_api_zoning_lookup_fails_to_find(mock_get_ordinance, client):
    """Test the endpoint when the core logic can't find the required fields."""
    # Simulate a result that is missing the required 'link'
    mock_get_ordinance.return_value = {'city': 'Failsville', 'link': None}

    response = client.post('/api/zoning', json={'city': 'Failsville'})
    assert response.status_code == 404
    assert 'Could not find zoning ordinance information' in response.get_json()['error']

@patch('ordinance_finder.get_zoning_ordinance')
def test_api_zoning_internal_error(mock_get_ordinance, client):
    """Test the endpoint when the core logic raises an unexpected exception."""
    mock_get_ordinance.side_effect = Exception("A critical internal error occurred.")

    response = client.post('/api/zoning', json={'city': 'InternalErrorCity'})
    assert response.status_code == 500
    assert 'A critical internal error occurred.' in response.get_json()['error']