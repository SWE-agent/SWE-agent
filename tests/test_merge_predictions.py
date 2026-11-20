import errno
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from sweagent.run.run import main


def _write_prediction(source: Path, patch: str = "new patch") -> dict[str, str]:
    source.mkdir()
    datum = {"instance_id": "instance", "model_patch": patch}
    (source / "instance.pred").write_text(json.dumps(datum))
    return datum


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux file size limits")
@pytest.mark.parametrize("explicit_output", [False, True])
@pytest.mark.parametrize("existing_output", [False, True])
def test_short_write_keeps_previous_aggregate(tmp_path, explicit_output, existing_output):
    source = tmp_path / "source"
    datum = _write_prediction(source, "new patch" * 800)
    target = tmp_path / "custom.json" if explicit_output else source / "preds.json"
    previous = b'{"previous": {"model_patch": "old"}}'
    if existing_output:
        target.write_bytes(previous)

    command = [
        sys.executable,
        "-c",
        "import resource; resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024)); "
        "from sweagent.run.run import main; main()",
        "merge-preds",
        str(source),
    ]
    if explicit_output:
        command.extend(["--output", str(target)])
    failed = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert failed.returncode != 0
    assert "File too large" in failed.stderr
    assert (target.read_bytes() if target.exists() else None) == (previous if existing_output else None)
    expected_entries = {"source"} if explicit_output else {"instance.pred"}
    if existing_output:
        expected_entries.add(target.name)
    assert {path.name for path in target.parent.iterdir()} == expected_entries

    arguments = ["merge-preds", str(source)]
    if explicit_output:
        arguments.extend(["--output", str(target)])
    main(arguments)
    assert json.loads(target.read_bytes()) == {"instance": datum}


def test_aggregate_reader_sees_complete_previous_output_until_replace(tmp_path, monkeypatch):
    source = tmp_path / "source"
    datum = _write_prediction(source)
    target = tmp_path / "preds.json"
    previous = b'{"previous": {"model_patch": "old"}}'
    target.write_bytes(previous)
    replace = Path.replace
    calls = []

    def inspect(staged, destination):
        assert destination == target
        assert target.read_bytes() == previous
        assert json.loads(staged.read_bytes()) == {"instance": datum}
        assert list(tmp_path.rglob("*.pred")) == [source / "instance.pred"]
        calls.append(destination)
        return replace(staged, destination)

    if not hasattr(os, "listxattr"):
        pytest.skip("requires inspectable existing-file access metadata")
    monkeypatch.setattr(Path, "replace", inspect)
    main(["merge-preds", str(source), "--output", str(target)])
    assert calls == [target]
    assert json.loads(target.read_bytes()) == {"instance": datum}


@pytest.mark.parametrize("error", [KeyboardInterrupt(), OSError(errno.ENOSPC, "cannot replace predictions")])
def test_failed_replacement_leaves_aggregate_and_cleans_staging(tmp_path, monkeypatch, error):
    if not hasattr(os, "listxattr"):
        pytest.skip("requires inspectable existing-file access metadata")
    source = tmp_path / "source"
    _write_prediction(source)
    target = tmp_path / "preds.json"
    previous = b'{"previous": {"model_patch": "old"}}'
    target.write_bytes(previous)

    def interrupted(staged, destination):
        assert destination == target
        assert staged.exists()
        raise error

    monkeypatch.setattr(Path, "replace", interrupted)
    with pytest.raises(type(error)) as rejected:
        main(["merge-preds", str(source), "--output", str(target)])
    assert rejected.value is error
    assert target.read_bytes() == previous
    assert set(tmp_path.iterdir()) == {source, target}


@pytest.mark.skipif(os.name != "posix", reason="checks POSIX link and permission semantics")
def test_aggregate_resolves_symlink_without_losing_permissions(tmp_path):
    source = tmp_path / "source"
    datum = _write_prediction(source)
    target = tmp_path / "target.json"
    link = tmp_path / "aggregate.json"
    link.symlink_to(target.name)
    arguments = ["merge-preds", str(source), "--output", str(link)]
    mask = os.umask(0o027)
    try:
        main(arguments)
    finally:
        os.umask(mask)

    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    target.chmod(0o600)
    main(arguments)
    assert link.is_symlink()
    assert json.loads(link.read_bytes()) == {"instance": datum}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="checks POSIX shared inode semantics")
def test_aggregate_keeps_explicit_hardlink_sharing(tmp_path):
    source = tmp_path / "source"
    datum = _write_prediction(source)
    target = tmp_path / "preds.json"
    target.write_text("{}")
    other = tmp_path / "shared.json"
    os.link(target, other)

    main(["merge-preds", str(source), "--output", str(target)])

    assert target.samefile(other)
    assert json.loads(other.read_bytes()) == {"instance": datum}


@pytest.mark.skipif(not hasattr(os, "listxattr"), reason="requires inspectable POSIX extended attributes")
def test_aggregate_keeps_output_extended_attributes(tmp_path):
    source = tmp_path / "source"
    datum = _write_prediction(source)
    target = tmp_path / "preds.json"
    target.write_text("{}")
    name = "user.sweagent_predictions"
    expected = b"evaluation metadata"
    try:
        os.setxattr(target, name, expected)
    except OSError as error:
        if error.errno != errno.ENOTSUP:
            raise
        pytest.skip("filesystem does not support extended attributes")

    main(["merge-preds", str(source), "--output", str(target)])

    assert json.loads(target.read_bytes()) == {"instance": datum}
    assert os.getxattr(target, name) == expected


@pytest.mark.skipif(os.name != "posix", reason="checks POSIX directory access semantics")
def test_writable_aggregate_in_nonwritable_parent_keeps_working(tmp_path):
    source = tmp_path / "source"
    datum = _write_prediction(source)
    parent = tmp_path / "outputs"
    parent.mkdir()
    target = parent / "existing.json"
    target.write_text("{}")
    old_inode = target.stat().st_ino
    original_mode = stat.S_IMODE(parent.stat().st_mode)
    parent.chmod(0o555)
    try:
        if os.access(parent, os.W_OK):
            pytest.skip("requires an unprivileged writer")
        main(["merge-preds", str(source), "--output", str(target)])
    finally:
        parent.chmod(original_mode)

    assert json.loads(target.read_bytes()) == {"instance": datum}
    assert target.stat().st_ino == old_inode
    assert list(parent.iterdir()) == [target]


@pytest.mark.skipif(not hasattr(os, "listxattr"), reason="requires inspectable existing-file access metadata")
@pytest.mark.parametrize(("existing_output", "error_number"), [(True, errno.ENOSPC), (False, errno.EACCES)])
def test_other_staging_errors_do_not_write_directly(tmp_path, monkeypatch, existing_output, error_number):
    source = tmp_path / "source"
    _write_prediction(source)
    target = tmp_path / "preds.json"
    previous = b'{"previous": {"model_patch": "old"}}'
    if existing_output:
        target.write_bytes(previous)

    def fail_staging(*, dir):
        assert dir == target.parent
        raise OSError(error_number, "staging unavailable")

    monkeypatch.setattr("sweagent.run.merge_predictions.TemporaryDirectory", fail_staging)
    with pytest.raises(OSError, match="staging unavailable") as failed:
        main(["merge-preds", str(source), "--output", str(target)])
    assert failed.value.errno == error_number
    assert (target.read_bytes() if target.exists() else None) == (previous if existing_output else None)


@pytest.mark.skipif(not hasattr(os, "listxattr"), reason="requires inspectable existing-file access metadata")
@pytest.mark.parametrize("error_number", [errno.EPERM, errno.EACCES, errno.ENOSPC])
def test_existing_aggregate_when_copying_access_metadata_fails(tmp_path, monkeypatch, error_number):
    source = tmp_path / "source"
    datum = _write_prediction(source)
    target = tmp_path / "preds.json"
    previous = b'{"previous": {"model_patch": "old"}}'
    target.write_bytes(previous)
    old_inode = target.stat().st_ino

    def fail_metadata_copy(original, staged, original_stat):
        assert original == target
        assert original_stat.st_ino == old_inode
        assert target.read_bytes() == previous
        assert json.loads(staged.read_bytes()) == {"instance": datum}
        raise OSError(error_number, "cannot copy aggregate access metadata")

    monkeypatch.setattr("sweagent.run.merge_predictions._copy_output_access", fail_metadata_copy)
    args = ["merge-preds", str(source), "--output", str(target)]
    if error_number == errno.ENOSPC:
        with pytest.raises(OSError, match="cannot copy aggregate access metadata") as failed:
            main(args)
        assert failed.value.errno == error_number
        assert target.read_bytes() == previous
    else:
        main(args)
        assert json.loads(target.read_bytes()) == {"instance": datum}
    assert target.stat().st_ino == old_inode
    assert set(tmp_path.iterdir()) == {source, target}
