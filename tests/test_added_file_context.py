from sweagent.utils.patch_formatter import PatchFormatter


def test_new_file_is_included_in_review_context():
    patch = """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+def answer():
+    return 42
"""
    paths = []

    def read_file(path):
        paths.append(path)
        return "def answer():\n    return 42\n"

    formatter = PatchFormatter(patch, read_file)
    result = formatter.get_files_str(original=False, context_length=30)
    assert paths == ["new.py"]
    assert "[File: new.py]" in result
    assert "return 42" in result


def test_deleted_file_is_not_read_from_working_tree():
    patch = """diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1 +0,0 @@
-old
"""

    def read_file(path):
        msg = f"deleted file read: {path}"
        raise AssertionError(msg)

    assert PatchFormatter(patch, read_file).get_files_str(original=False) == ""


def test_added_binary_file_is_not_read_as_text():
    patch = """diff --git a/image.png b/image.png
new file mode 100644
index 0000000..1234567
Binary files /dev/null and b/image.png differ
"""

    def read_file(path):
        msg = f"binary file read: {path}"
        raise AssertionError(msg)

    assert PatchFormatter(patch, read_file).get_files_str(original=False) == ""
