import pytest
from fastapi import HTTPException

from app.api.routes_documents import RAW_DATA_DIR, _resolve_destination, _sanitize_filename


def test_sanitize_filename_allows_normal_names():
    assert _sanitize_filename("report.txt") == "report.txt"


def test_sanitize_filename_strips_directory_components():
    assert _sanitize_filename("../../etc/passwd") == "passwd"


def test_sanitize_filename_replaces_special_characters():
    assert _sanitize_filename("my report #1.txt") == "my_report__1.txt"


@pytest.mark.parametrize(
    "name",
    ["CON", "con.txt", "Con.pdf", "NUL", "nul.docx", "PRN.txt", "AUX", "COM1", "com3.txt", "LPT1", "lpt9.md"],
)
def test_sanitize_filename_rejects_windows_reserved_names(name):
    with pytest.raises(HTTPException) as exc_info:
        _sanitize_filename(name)
    assert exc_info.value.status_code == 400


def test_sanitize_filename_allows_names_containing_but_not_equal_to_reserved_words():
    # "console.txt" and "nullable.txt" are not reserved -- only the exact device name (stem) is.
    assert _sanitize_filename("console.txt") == "console.txt"
    assert _sanitize_filename("nullable.txt") == "nullable.txt"


def test_resolve_destination_reuses_path_for_identical_content(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.routes_documents.RAW_DATA_DIR", tmp_path)
    content = b"same content"
    dest1 = _resolve_destination("report.txt", content)
    dest1.write_bytes(content)

    dest2 = _resolve_destination("report.txt", content)

    assert dest1 == dest2


def test_resolve_destination_disambiguates_different_content_with_same_name(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.routes_documents.RAW_DATA_DIR", tmp_path)
    dest1 = _resolve_destination("report.txt", b"first version")
    dest1.write_bytes(b"first version")

    dest2 = _resolve_destination("report.txt", b"second, different version")

    assert dest1 != dest2
    assert dest2.name != "report.txt"
    assert dest2.name.endswith("_report.txt")
