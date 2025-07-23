# utils/pdf_parser.py  (only the additions/changes shown) ---------------------
import os, tempfile, requests, pdfplumber, json
from typing import List, Dict

PDF_SIZE_LIMIT = 40 * 1024 * 1024      # 40 MB – bail out early on monsters

class PDFAnalysisError(RuntimeError):
    """Any failure you want to bubble back to /api/status."""

# ---------------------------------------------------------------- download
def download_pdf(url: str, timeout: int = 45) -> str:
    """Download a remote PDF to a temp file and return its local path."""
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            if total and total > PDF_SIZE_LIMIT:
                raise PDFAnalysisError("PDF is larger than 40 MB — skipping.")
            fd, path = tempfile.mkstemp(suffix=".pdf")
            downloaded = 0
            with os.fdopen(fd, "wb") as tmp:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > PDF_SIZE_LIMIT:
                            raise PDFAnalysisError("PDF exceeded 40 MB while downloading.")
                        tmp.write(chunk)
        return path
    except (requests.RequestException, PDFAnalysisError) as e:
        raise PDFAnalysisError(f"Failed to download PDF: {e}") from e

# ---------------------------------------------------------------- extract
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

# ---------------------------------------------------------------- summarize / score – wrap LLM errors
def summarize_chunks(chunks: List[str], client) -> str:
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

# ---------------------------------------------------------------- orchestrator unchanged except catches
def analyse_pdf(url: str, client, best_practices: Dict, weights: Dict) -> Dict:
    path = None
    try:
        path = download_pdf(url)
        pages = extract_text(path)
        chunks = chunk_text(pages)          # uses new 5 000-token default
        summary = summarize_chunks(chunks, client)
        scores = score_document(summary, best_practices, weights, client)
        return {"summary": summary, "scores": scores}
    finally:
        if path and os.path.exists(path):
            os.remove(path)
