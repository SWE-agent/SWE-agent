import pytest

from tests.tools.test_default_utils import create_test_file_with_content


@pytest.mark.parametrize("content", ["\noriginal", "\n\noriginal", "original", ""])
def test_insert_at_start_preserves_existing_blank_lines(with_tmp_env_file, content):
    wfile = create_test_file_with_content(with_tmp_env_file, content)
    info = wfile.insert("new", line=-1)
    assert wfile.text == ("new\n" + content if content else "new")
    assert info.first_inserted_line == 0
    assert info.n_lines_added == 1
