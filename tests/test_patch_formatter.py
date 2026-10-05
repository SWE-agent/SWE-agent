import pytest

from sweagent.utils.patch_formatter import PatchFormatter


@pytest.mark.parametrize(("stop", "omitted"), [(3, 2), (4, 1), (5, 0), (8, 0)])
def test_format_file_counts_lines_below_exclusive_stop(stop: int, omitted: int):
    formatter = PatchFormatter("", lambda _: "")

    result = formatter.format_file("first\nsecond\nthird\nfourth\n", [1], [stop])

    if omitted:
        assert result.endswith(f"[{omitted} lines below omitted]")
    else:
        assert "lines below omitted" not in result
        assert result.endswith("     4: fourth")


def test_patch_context_reports_the_final_unshown_line():
    patch = "--- a/example.py\n+++ b/example.py\n@@ -1,2 +1,2 @@\n first\n-second\n+changed\n"
    formatter = PatchFormatter(patch, lambda _: "first\nchanged\nlast\n")

    assert formatter.get_files_str(original=False, context_length=0) == (
        "[File: example.py]\n     1: first\n     2: changed\n[1 lines below omitted]"
    )
