from __future__ import annotations

import re
import zipfile
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
PRESENTATIONS = ROOT / "docs" / "presentations"
MANUSCRIPT = ROOT / "docs" / "dissertation_manuscript_20260801.md"
MATRIX = ROOT / "docs" / "dissertation_literature_matrix_20260801.md"
BIBLIOGRAPHY = ROOT / "docs" / "dissertation_references_20260802.bib"
DECK_SOURCE = PRESENTATIONS / "traffictwin_supervisor_checkpoint_20260802.mjs"
DECK = PRESENTATIONS / "traffictwin_supervisor_checkpoint_20260802.pptx"
DECK_PDF = PRESENTATIONS / "traffictwin_supervisor_checkpoint_20260802.pdf"
SOURCE_AUDIT = PRESENTATIONS / "traffictwin_supervisor_checkpoint_20260802_sources.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _bib_entries(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"^@\w+\{(tt\d{3}),", text, flags=re.MULTILINE))
    return {
        match.group(1): text[match.start() : starts[index + 1].start()]
        if index + 1 < len(starts)
        else text[match.start() :]
        for index, match in enumerate(starts)
    }


def _citation_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    for match in re.finditer(r"\[([0-9]+)\]\s*[–-]\s*\[([0-9]+)\]", text):
        numbers.update(range(int(match.group(1)), int(match.group(2)) + 1))
    for match in re.finditer(r"\[([0-9][0-9, \-–]*)\]", text):
        for raw_part in match.group(1).split(","):
            part = raw_part.strip()
            separator = "–" if "–" in part else "-" if "-" in part else None
            if separator is None:
                numbers.add(int(part))
                continue
            start, end = (int(value.strip()) for value in part.split(separator, maxsplit=1))
            numbers.update(range(start, end + 1))
    return numbers


def _pptx_text(archive: zipfile.ZipFile, prefix: str) -> str:
    names = sorted(
        name for name in archive.namelist() if name.startswith(prefix) and name.endswith(".xml")
    )
    return "\n".join(archive.read(name).decode("utf-8") for name in names)


def test_bibliography_has_exactly_100_audited_sources() -> None:
    text = _read(BIBLIOGRAPHY)
    entries = _bib_entries(text)
    expected_keys = {f"tt{number:03d}" for number in range(1, 101)}
    non_doi_keys = {
        "tt012",
        "tt014",
        "tt015",
        "tt016",
        "tt017",
        "tt031",
        "tt040",
        "tt046",
        "tt047",
        "tt064",
        "tt085",
        "tt090",
    }

    assert set(entries) == expected_keys
    assert len(entries) == 100
    assert (
        sum(bool(re.search(r"\bdoi\s*=", entry, flags=re.IGNORECASE)) for entry in entries.values())
        == 88
    )
    assert {
        key
        for key, entry in entries.items()
        if re.search(r"\bdoi\s*=", entry, flags=re.IGNORECASE) is None
    } == non_doi_keys
    assert all(
        re.search(r"\btitle\s*=", entry, flags=re.IGNORECASE)
        and re.search(r"\byear\s*=", entry, flags=re.IGNORECASE)
        for entry in entries.values()
    )
    assert all(
        re.search(r"\b(?:doi|url)\s*=", entry, flags=re.IGNORECASE)
        or key in {"tt015", "tt016", "tt017"}
        for key, entry in entries.items()
    )
    assert "10.1109/mc.2016.245" in text.lower()
    assert "10.1109/jsac.2016.2611964" in text.lower()
    assert "10.1109/tvt.2016.2532863" in text.lower()
    assert "&amp;" not in text
    assert "<i>" not in text


def test_manuscript_has_100_references_and_cites_every_one() -> None:
    text = _read(MANUSCRIPT)
    body, references = text.split("## References", maxsplit=1)
    numbered_references = [
        int(match.group(1))
        for match in re.finditer(r"^\[([0-9]+)\] ", references, flags=re.MULTILINE)
    ]

    assert numbered_references == list(range(1, 101))
    assert _citation_numbers(body) == set(range(1, 101))
    counted = (
        "## Abstract"
        + text.split("## Abstract", maxsplit=1)[1].split("## References", maxsplit=1)[0]
    )
    assert len(counted.split()) == 8396
    assert "**8,396**" in text


def test_literature_matrix_keeps_source_classes_and_transfer_limits_separate() -> None:
    matrix = _read(MATRIX)
    source_audit = _read(SOURCE_AUDIT)

    assert "DOI-bearing primary literature | 88" in matrix
    assert "First-party official/standards records | 9" in matrix
    assert "Private producer records | 3" in matrix
    assert "Total: **100 distinct sources**" in matrix
    assert "LLM drafting | zero bibliography entries" in matrix
    assert "Project measurements | separate from the 100 literature records" in matrix
    assert "not a live twin" in matrix
    assert "not a predeclared causal mechanism" in source_audit.lower()
    assert "never a measurement, citation, approval or evidence source" in " ".join(
        source_audit.split()
    )


def test_deck_is_editable_four_slide_artifact_with_sources_notes() -> None:
    source = _read(DECK_SOURCE)
    assert "@oai/artifact-tool" in source
    assert "PresentationFile.exportPptx" in source
    assert "python-pptx" not in source
    assert "[Sources]" in source

    with zipfile.ZipFile(DECK) as archive:
        slide_names = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", name)
        )
        notes_names = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"ppt/notesSlides/notesSlide[0-9]+\.xml", name)
        )
        chart_names = [
            name
            for name in archive.namelist()
            if re.fullmatch(r"ppt/slides/charts/chart[0-9]+\.xml", name)
        ]
        slide_xml = _pptx_text(archive, "ppt/slides/slide")
        notes_xml = _pptx_text(archive, "ppt/notesSlides/notesSlide")

    assert len(slide_names) == 4
    assert len(notes_names) == 4
    assert len(chart_names) == 1
    assert notes_xml.count("[Sources]") == 4
    assert "TrafficTwin" in slide_xml
    assert "−8,310.9 ms" in slide_xml
    assert "8,956,800 decisions" in slide_xml
    assert "no supervisor, ethics or publication approval inferred" in slide_xml


def test_rendered_pdf_has_four_landscape_pages() -> None:
    reader = PdfReader(DECK_PDF)

    assert len(reader.pages) == 4
    for page in reader.pages:
        assert float(page.mediabox.width) > float(page.mediabox.height)
