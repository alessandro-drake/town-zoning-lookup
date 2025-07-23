# tests/test_analyzer.py
# tests logic in pdf_parser.py. Goes through every function, 
# sees if it gets what it wants that it outputs the correct thing

import os
import json
import pytest
import tempfile
import utils.pdf_parser as pdf_parser
from utils.pdf_parser import PDFAnalysisError

class DummyClient:
    def complete(self, prompt):
        return "OK"

# --- summarise_chunks tests (unchanged) ---
def test_summarize_chunks_success(monkeypatch):
    calls = []
    class FakeClient:
        def complete(self, prompt):
            calls.append(prompt)
            return f"PART#{len(calls)}"
    chunks = ["A", "B", "C"]
    result = pdf_parser.summarize_chunks(chunks, FakeClient())
    assert len(calls) == len(chunks) + 1
    assert result == "PART#4"

def test_summarize_chunks_failure(monkeypatch):
    class BadClient:
        def complete(self, prompt):
            raise RuntimeError("syn_fail")
    with pytest.raises(PDFAnalysisError):
        pdf_parser.summarize_chunks(["X"], BadClient())

# --- score_document tests (unchanged, as its signature is the same) ---
def test_score_document_success(monkeypatch):
    best_prac = {"rule1": "desc"}
    weights   = {"rule1": 1}
    class FakeClient:
        def complete(self, prompt):
            return json.dumps({"rule1": 75, "total": 75})
    scores = pdf_parser.score_document("summary", best_prac, weights, FakeClient())
    assert scores["total"] == 75

def test_score_document_bad_json(monkeypatch):
    class FakeClient:
        def complete(self, prompt): return "not a json"
    with pytest.raises(PDFAnalysisError):
        pdf_parser.score_document("summary", {}, {}, FakeClient())

def test_score_document_missing_total(monkeypatch):
    class FakeClient:
        def complete(self, prompt): return json.dumps({"rule1": 50})
    with pytest.raises(PDFAnalysisError):
        pdf_parser.score_document("summary", {}, {}, FakeClient())

# --- analyze_pdf orchestration tests (updated) ---
def test_analyze_pdf_happy_path(monkeypatch, tmp_path):
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%EOF")
    monkeypatch.setattr(pdf_parser, "download_pdf", lambda url: str(dummy_pdf))
    monkeypatch.setattr(pdf_parser, "extract_text", lambda path: ["p1", "p2"])
    monkeypatch.setattr(pdf_parser, "chunk_text", lambda pages: ["c1", "c2", "c3"])
    monkeypatch.setattr(pdf_parser, "summarize_chunks", lambda chunks, client: "THE SUMMARY")
    monkeypatch.setattr(pdf_parser, "score_document", lambda summary, bp, w, client: {"foo": 1, "total": 1})
    
    removed = {"called": False}
    monkeypatch.setattr(os, "remove", lambda path: removed.update({"called": True}))

    # <-- KEY CHANGE: Create a dummy data structure that includes weights
    dummy_best_practices_data = {
        "zoning_best_practices_framework": {
            "evaluation_categories": {
                "category1": {"weight": 50},
                "category2": {"weight": 50}
            }
        }
    }

    result = pdf_parser.analyze_pdf(
        url="http://example.com/fake.pdf",
        client=DummyClient(),
        best_practices_data=dummy_best_practices_data, # Use new argument
    )

    assert result == {"summary": "THE SUMMARY", "scores": {"foo": 1, "total": 1}}
    assert removed["called"]

def test_analyze_pdf_download_error(monkeypatch):
    # <-- KEY CHANGE: The mock now raises an exception with the correctly formatted message
    # that the real download_pdf function would produce.
    monkeypatch.setattr(pdf_parser, "download_pdf",
                        lambda url: (_ for _ in ()).throw(PDFAnalysisError("Failed to download PDF: dl fail")))

    dummy_best_practices_data = {
        "zoning_best_practices_framework": {"evaluation_categories": {}}
    }
    
    # This assertion will now pass because the mocked exception message matches.
    with pytest.raises(PDFAnalysisError, match="Failed to download PDF"):
        pdf_parser.analyze_pdf("bad://url", DummyClient(), dummy_best_practices_data)


def test_analyze_pdf_extract_error(monkeypatch, tmp_path):
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%EOF")
    monkeypatch.setattr(pdf_parser, "download_pdf", lambda url: str(dummy_pdf))
    monkeypatch.setattr(pdf_parser, "extract_text",
                        lambda path: (_ for _ in ()).throw(PDFAnalysisError("no text")))
    
    removed = {"called": False}
    monkeypatch.setattr(os, "remove", lambda p: removed.update({"called": True}))

    # Create a minimal data structure to prevent the KeyError
    dummy_best_practices_data = {
        "zoning_best_practices_framework": {"evaluation_categories": {}}
    }

    with pytest.raises(PDFAnalysisError):
         # Pass the minimal data instead of an empty dictionary
        pdf_parser.analyze_pdf("http://example.com/fake.pdf", DummyClient(), dummy_best_practices_data)
    assert removed["called"]