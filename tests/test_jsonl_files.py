import json

import pytest

from sweagent.utils.files import load_file


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_load_jsonl_preserves_unicode_separators(tmp_path, separator):
    records = [{"instance_id": "one", "problem_statement": f"before{separator}after"}, {"instance_id": "two"}]
    path = tmp_path / "instances.jsonl"
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
    assert load_file(path) == records


@pytest.mark.parametrize(
    ("terminator", "last_terminator", "blank_lines", "ensure_ascii"),
    [
        ("\n", True, False, False),
        ("\r\n", True, False, False),
        ("\n", False, False, False),
        ("\n", True, True, False),
        ("\n", True, False, True),
    ],
)
def test_load_jsonl_line_forms(tmp_path, terminator, last_terminator, blank_lines, ensure_ascii):
    records = [{"problem_statement": "before\u2028after" if ensure_ascii else "plain"}, {"instance_id": "two"}]
    lines = [json.dumps(record, ensure_ascii=ensure_ascii) for record in records]
    if blank_lines:
        lines = ["", lines[0], " ", lines[1], ""]
    path = tmp_path / "instances.jsonl"
    path.write_bytes((terminator.join(lines) + (terminator if last_terminator else "")).encode("utf-8"))
    assert load_file(path) == records


def test_load_empty_jsonl(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.touch()
    assert load_file(path) == []


def test_load_jsonl_rejects_invalid_control(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_bytes(b'{"text":"before\x01after"}\n')
    with pytest.raises(json.JSONDecodeError):
        load_file(path)
