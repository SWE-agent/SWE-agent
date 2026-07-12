import pytest

from sweagent.utils.files import load_file


@pytest.mark.parametrize(
    ("suffix", "content"),
    [
        (".json", '{"problem_statement": "Fix the café — please"}'),
        (".traj", '{"problem_statement": "Fix the café — please"}'),
        (".yaml", "problem_statement: Fix the café — please"),
    ],
)
def test_load_file_reads_utf8(tmp_path, suffix, content):
    path = tmp_path / f"instance{suffix}"
    path.write_text(content, encoding="utf-8")
    assert load_file(path) == {"problem_statement": "Fix the café — please"}


def test_load_jsonl_reads_utf8(tmp_path):
    path = tmp_path / "instances.jsonl"
    instances = [{"problem_statement": "Fix the café"}, {"problem_statement": "Keep the em dash — intact"}]
    path.write_text(
        '{"problem_statement": "Fix the café"}\n{"problem_statement": "Keep the em dash — intact"}', encoding="utf-8"
    )
    assert load_file(path) == instances
