import pytest

from sweagent.utils.patch_formatter import PatchFormatter


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_patch_formatter_uses_git_line_boundaries(newline):
    text = newline.join(['value = "before\u2028after"', "unchanged = 1", "changed = 2", ""])
    patch = "\n".join(
        [
            "diff --git a/example.py b/example.py",
            "--- a/example.py",
            "+++ b/example.py",
            "@@ -3 +3 @@",
            "-changed = 1",
            "+changed = 2",
            "",
        ]
    )
    formatter = PatchFormatter(patch, lambda _: text)

    assert formatter.get_files_str(original=False, context_length=0) == (
        "[File: example.py]\n[2 lines above omitted]\n     3: changed = 2"
    )
