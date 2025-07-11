# town-zoning-lookup
A website that allows looking up a town's zoning code quickly and easily.

# City Zoning Ordinance Finder

A web application that allows users to input a city name and retrieve the most recent zoning ordinance document using Claude AI.

## Features

- Web interface for easy city input
- RESTful API endpoint for programmatic access
- Finds official zoning ordinances with direct links
- Identifies file types (PDF, web page, etc.)
- Includes relevant notes about the search process

## Setup Instructions

### 1. Prerequisites

- Python 3.7 or higher
- Git
- VSCode (recommended)
- An Anthropic API key

### 2. Get Your Anthropic API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an account or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (you'll need it for the .env file)

### 3. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd zoning-ordinance-finder

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
```

### 4. Configure Environment

Edit the `.env` file and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_actual_api_key_here
```

### 5. Run the Application

```bash
python backend.py
```

The application will start on `http://localhost:5000`

## Usage

### Web Interface

1. Open your browser and go to `http://localhost:5000`
2. Enter a city name (e.g., "San Francisco, CA")
3. Click "Find Zoning Ordinance"
4. View the results with document link and details

### API Endpoint

You can also use the API directly:

```bash
curl -X POST http://localhost:5000/api/zoning \
  -H "Content-Type: application/json" \
  -d '{"city": "San Francisco, CA"}'
```

Response format:
```json
{
  "city": "San Francisco, CA",
  "link": "https://example.com/zoning-ordinance.pdf",
  "file_type": "PDF",
  "notes": "Document was last updated in 2024"
}
```

## Project Structure

```
zoning-ordinance-finder/
├── backend.py          # Main Flask application
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variable template
├── .gitignore         # Git ignore file
└── README.md          # This file
```

## Development Notes

### VSCode Setup

1. Open the project folder in VSCode
2. Install the Python extension
3. Select your virtual environment as the Python interpreter
4. Use the integrated terminal for running commands

### GitHub Setup

```bash
# Initialize git repository
git init

# Add files
git add .

# Initial commit
git commit -m "Initial commit"

# Add remote repository
git remote add origin <your-github-repo-url>

# Push to GitHub
git push -u origin main
```

## API Rate Limits

- Be aware of Anthropic's API rate limits
- The application includes basic error handling for API failures
- Consider implementing caching for frequently requested cities

## Error Handling

The application handles several types of errors:
- Missing API key
- Invalid city input
- API failures
- Parsing errors
- Network issues

## Security Considerations

- Never commit your `.env` file to version control
- Keep your API key secure
- Consider implementing rate limiting for production use
- Add input validation for city names

## Customization

You can modify the prompt in the `get_zoning_ordinance()` function to:
- Change search criteria
- Add additional fields to the response
- Modify the output format
- Include different types of documents

## Troubleshooting

### Common Issues

1. **API Key Error**: Make sure your `.env` file contains the correct API key
2. **Import Errors**: Ensure all dependencies are installed with `pip install -r requirements.txt`
3. **Network Issues**: Check your internet connection and Anthropic API status

### Debug Mode

The application runs in debug mode by default. To disable for production:

```python
app.run(debug=False, host='0.0.0.0', port=5000)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).
