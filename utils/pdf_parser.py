# utils/pdf_parser.py
import os, tempfile, requests, pdfplumber
from typing import List, Dict

def download_pdf(url: str, timeout: int = 30) -> str:
    """Download a remote PDF to a temp file and return its local path."""
    resp = requests.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()
    suffix = '.pdf'
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'wb') as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
    return path          # caller is responsible for deleting

def extract_text(path: str) -> List[str]:
    """Return a list where each item = text of one page."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ''
            pages.append(txt.strip())
    return pages

def chunk_text(pages: List[str], max_tokens: int = 1500) -> List[str]:
    """Concatenate pages into chunks below the LLM token limit."""
    chunks, current = [], []
    tokens = 0
    for pg in pages:
        t = len(pg.split())
        if tokens + t > max_tokens and current:
            chunks.append('\n'.join(current))
            current, tokens = [], 0
        current.append(pg)
        tokens += t
    if current: chunks.append('\n'.join(current))
    return chunks

def summarize_chunks(chunks: List[str], client) -> str:
    """Call the LLM on each chunk, then aggregate."""
    partial_summaries = []
    for ch in chunks:
        prompt = f"Summarize this zoning ordinance segment in ≤250 words:\n\n{ch}"
        partial_summaries.append(client.complete(prompt))
    # final aggregation
    final_prompt = ("Combine the following partial summaries into one coherent, "
                    "non‑redundant executive summary (≤400 words):\n\n" +
                    '\n\n'.join(partial_summaries))
    return client.complete(final_prompt)

def score_document(summary: str,
                   best_practices: Dict, weights: Dict,
                   client) -> Dict[str, float]:
    """Ask the LLM (or run rules) to score each criterion, then weight."""
    prompt = (
        "Using the following summary of a zoning ordinance, evaluate it against "
        f"these best practices:\n{json.dumps(best_practices,indent=2)}\n\n"
        "Return a JSON object with a 0‑100 score for each practice, "
        "then a weighted overall score using these weights:\n"
        f"{json.dumps(weights)}\n\n"
        f"SUMMARY:\n{summary}"
    )
    raw = client.complete(prompt)
    return json.loads(raw)

def analyze_pdf(url: str, client,
                best_practices: Dict, weights: Dict) -> Dict:
    """Orchestrator – download, parse, summarise, score."""
    path  = download_pdf(url)
    try:
        pages   = extract_text(path)
        chunks  = chunk_text(pages)
        summary = summarize_chunks(chunks, client)
        scores  = score_document(summary, best_practices, weights, client)
        return { "summary": summary, "scores": scores }
    finally:
        os.remove(path)
