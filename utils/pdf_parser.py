import os
import tempfile
import time
import json
import requests
import pdfplumber
from typing import List, Dict

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

PDF_SIZE_LIMIT = 40 * 1024 * 1024

class PDFAnalysisError(RuntimeError):
    """Any failure you want to bubble back to /api/status."""

def download_pdf(url: str, timeout: int = 45) -> str:
    """
    Uses a hybrid Selenium + Requests approach to download a PDF.
    1. Selenium gets a valid session and cookies from the server.
    2. Requests uses those cookies to perform the actual download.
    """
    try:
        # --- Step 1: Use Selenium to get session cookies ---
        
        # Configure and initialize a headless Chrome browser
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Navigate to the URL to establish a session
        driver.get(url)
        
        # Give the page a moment to load and set any cookies
        time.sleep(3) 

        # Get the cookies from the browser session
        selenium_cookies = driver.get_cookies()
        
        # We're done with the browser, so clean it up
        driver.quit()

        # --- Step 2: Use Requests with the session cookies to download the file ---
        
        # The User-Agent header is still a good idea to include
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Convert Selenium's cookie format to one that Requests can use
        requests_cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}

        # Perform the download using requests, passing the headers and cookies
        with requests.get(url, stream=True, timeout=timeout, headers=headers, cookies=requests_cookies) as resp:
            resp.raise_for_status() # Will raise an error for 4xx or 5xx status codes
            
            # Create a temporary file to save the PDF
            fd, path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as tmp:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
        return path

    except Exception as e:
        # Ensure the browser is closed if it was still open during an error
        if 'driver' in locals() and driver:
            driver.quit()
        raise PDFAnalysisError(f"Failed to download PDF with Selenium/Requests: {e}") from e


def extract_text(path: str) -> List[str]:
    """Return page-text list, raise if nothing extractable."""
    try:
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
                pages.append(txt.strip())
    except Exception as e:
        raise PDFAnalysisError(f"Could not read PDF: {e}") from e
    if not any(pages):
        raise PDFAnalysisError("PDF contains no extractable text (likely scanned).")
    return pages

def chunk_text(pages: List[str], chunk_size: int = 5000) -> List[str]:
    """Combine pages and split into ~5000-char chunks for LLM context."""
    full_text = "\n\n".join(pages)
    if not full_text:
        return []
    return [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

def summarize_chunks(chunks: List[str], client) -> str:
    """Summarize text chunks using an LLM."""
    partial = []
    try:
        for ch in chunks:
            prompt = f"Summarise this zoning ordinance segment in ≤250 words:\n\n{ch}"
            partial.append(client.complete(prompt))
        final_prompt = ("Combine the following partial summaries into one coherent, "
                        "non-redundant executive summary (≤400 words):\n\n" +
                        "\n\n".join(partial))
        return client.complete(final_prompt)
    except Exception as e:
        raise PDFAnalysisError(f"LLM summarisation failed: {e}") from e

def score_document(summary: str, best_practices: Dict,
                   weights: Dict, client) -> Dict[str, float]:
    """Score a summary against best practices using an LLM."""
    try:
        prompt = (
            "Using the summary below, score each best-practice 0-100 and return JSON with "
            "a 'total' key for the weighted average.\n\n"
            f"BEST_PRACTICES = {json.dumps(best_practices)}\n"
            f"WEIGHTS = {json.dumps(weights)}\n\n"
            f"SUMMARY:\n{summary}"
        )
        raw = client.complete(prompt)
        scores = json.loads(raw)
        if "total" not in scores:
            raise ValueError("missing 'total' key")
        return scores
    except Exception as e:
        raise PDFAnalysisError(f"LLM scoring failed or returned bad JSON: {e}") from e

def analyze_pdf(url: str, client, best_practices_data: Dict) -> Dict:
    """Orchestrates the full PDF analysis pipeline."""
    path = None
    try:
        weights = {
            category: data['weight']
            for category, data in best_practices_data['zoning_best_practices_framework']['evaluation_categories'].items()
        }

        path = download_pdf(url)
        pages = extract_text(path)
        chunks = chunk_text(pages)
        summary = summarize_chunks(chunks, client)
        scores = score_document(summary, best_practices_data, weights, client)
        return {"summary": summary, "scores": scores}
    finally:
        if path and os.path.exists(path):
             pass
