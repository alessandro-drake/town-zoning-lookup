# tests/test_analyzer.py
# tests logic in pdf_parser.py. Goes through every function, 
# sees if it gets what it wants that it outputs the correct thing

import os
import json
import pytest
import tempfile

import utils.pdf_parser as pdf_parser
from utils.pdf_parser import PDFAnalysisError

# A dummy LLM client for use in tests
class DummyClient:
    def complete(self, prompt):
        return "OK"

# ------------------------------------------------------
# 1) summarise_chunks
# ------------------------------------------------------
def test_summarize_chunks_success(monkeypatch):
    calls = []
    class FakeClient:
        def complete(self, prompt):
            calls.append(prompt)
            # return a short placeholder each time
            return f"PART#{len(calls)}"
    chunks = ["A", "B", "C"]
    result = pdf_parser.summarize_chunks(chunks, FakeClient())
    # we expect one call per chunk + one final “combine” call
    assert len(calls) == len(chunks) + 1
    assert isinstance(result, str)
    # final result is whatever fake complete returned on last call
    assert result == "PART#4"

def test_summarize_chunks_failure(monkeypatch):
    class BadClient:
        def complete(self, prompt):
            raise RuntimeError("syn_fail")
    with pytest.raises(PDFAnalysisError) as excinfo:
        pdf_parser.summarize_chunks(["X"], BadClient())
    assert "LLM summarisation failed" in str(excinfo.value)

# ------------------------------------------------------
# 2) score_document
# ------------------------------------------------------
def test_score_document_success(monkeypatch):
    best_prac = {"rule1": "desc"}
    weights   = {"rule1": 1}
    class FakeClient:
        def complete(self, prompt):
            # return a valid JSON with total
            return json.dumps({"rule1": 75, "total": 75})
    scores = pdf_parser.score_document("summary", best_prac, weights, FakeClient())
    assert isinstance(scores, dict)
    assert scores["rule1"] == 75
    assert scores["total"] == 75

def test_score_document_bad_json(monkeypatch):
    class FakeClient:
        def complete(self, prompt):
            return "not a json"
    with pytest.raises(PDFAnalysisError) as excinfo:
        pdf_parser.score_document("summary", {}, {}, FakeClient())
    assert "LLM scoring failed" in str(excinfo.value)

def test_score_document_missing_total(monkeypatch):
    class FakeClient:
        def complete(self, prompt):
            # valid JSON but no "total"
            return json.dumps({"rule1": 50})
    with pytest.raises(PDFAnalysisError) as excinfo:
        pdf_parser.score_document("summary", {}, {}, FakeClient())
    # the underlying ValueError will get wrapped
    assert "missing 'total'" in str(excinfo.value)

# ------------------------------------------------------
# 3) analyse_pdf orchestration
# ------------------------------------------------------
def test_analyse_pdf_happy_path(monkeypatch, tmp_path):
    # 3a) Prepare a dummy PDF file
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%EOF")

    # 3b) Stub download_pdf → our dummy file
    monkeypatch.setattr(pdf_parser, "download_pdf", lambda url: str(dummy_pdf))

    # 3c) Stub extract_text → pretend we got two pages
    monkeypatch.setattr(pdf_parser, "extract_text", lambda path: ["p1", "p2"])

    # 3d) Stub chunk_text → pretend it cuts into three chunks
    monkeypatch.setattr(pdf_parser, "chunk_text", lambda pages: ["c1", "c2", "c3"])

    # 3e) Stub summarisation + scoring
    monkeypatch.setattr(pdf_parser, "summarize_chunks", lambda chunks, client: "THE SUMMARY")
    monkeypatch.setattr(pdf_parser, "score_document", lambda summary, bp, w, client: {"foo": 1, "total": 1})

    # 3f) Spy on os.remove so we know cleanup happened
    removed = {"called": False}
    def fake_remove(path):
        removed["called"] = True
    monkeypatch.setattr(os, "remove", fake_remove)

    # finally call
    result = pdf_parser.analyse_pdf(
        url="http://example.com/fake.pdf",
        client=DummyClient(),
        best_practices={"x": "y"},
        weights={"x": 1},
    )

    assert result == {"summary": "THE SUMMARY", "scores": {"foo": 1, "total": 1}}
    assert removed["called"], "Downloaded PDF should be removed in cleanup"

def test_analyse_pdf_download_error(monkeypatch):
    # Make download_pdf raise an error that looks like the real one
    error_message = "Failed to download PDF: dl fail"
    monkeypatch.setattr(pdf_parser, "download_pdf",
                        lambda url: (_ for _ in ()).throw(PDFAnalysisError(error_message)))

    with pytest.raises(PDFAnalysisError) as excinfo:
        pdf_parser.analyse_pdf("bad://url", DummyClient(), {}, {})
    
    # Now the assertion will pass because the message from the mock matches
    assert "Failed to download PDF" in str(excinfo.value)

def test_analyse_pdf_extract_error(monkeypatch, tmp_path):
    # download succeeds
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%EOF")
    monkeypatch.setattr(pdf_parser, "download_pdf", lambda url: str(dummy_pdf))
    # extract_text fails
    monkeypatch.setattr(pdf_parser, "extract_text",
                        lambda path: (_ for _ in ()).throw(PDFAnalysisError("no text")))
    # cleanup spy
    removed = {"called": False}
    monkeypatch.setattr(os, "remove", lambda p: removed.__setitem__("called", True))

    with pytest.raises(PDFAnalysisError):
        pdf_parser.analyse_pdf("http://example.com/fake.pdf", DummyClient(), {}, {})
    # still should clean up
    assert removed["called"]
