from pathlib import Path

from briefing.ingest import chunk_text, normalize_text, read_input, rows_to_markdown_table


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("one   two\r\n\r\n\r\nthree") == "one two\n\nthree"


def test_chunk_text_preserves_paragraphs() -> None:
    text = "\n\n".join([f"paragraph {idx} " + ("x" * 20) for idx in range(8)])
    chunks = chunk_text(text, max_chars=80)
    assert len(chunks) > 1
    assert "paragraph 0" in chunks[0]


def test_rows_to_markdown_table_normalizes_cells() -> None:
    table = rows_to_markdown_table(
        [
            ["Name", "Notes"],
            ["Gemma\n3", "Vision | language\nmodel"],
            ["Gemma 4", None],
        ]
    )
    assert "| Name | Notes |" in table
    assert "| Gemma 3 | Vision \\| language model |" in table
    assert "| Gemma 4 |  |" in table


def test_sample_gemma_pdf_preserves_table() -> None:
    text = read_input(Path("data/input/Gemma_(language_model).pdf"))
    assert "Gemma" in text
    assert "## Page 3" in text
    assert "### Table 1 on Page 3" in text
    assert "Generation" in text
    assert "Release date" in text
    assert "Parameters" in text
    assert "Context length" in text
    assert "Multimodal" in text
    assert "Gemma 1" in text
    assert "Gemma 2" in text
    assert "Gemma 3" in text
