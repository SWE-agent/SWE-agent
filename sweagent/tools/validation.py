import shlex
from pathlib import Path

from sweagent.exceptions import FormatError


def validate_path(path_str: str, workspace_dir: str | Path, is_create: bool = False, env=None) -> Path:
    """Validates local or container path arguments for agent core.

    Rules:
    - Absolute paths outside the workspace raise FormatError.
    - Relative paths escaping the workspace raise FormatError.
    - Non-existent files for reading/editing raise FormatError.
    - For creation, the file itself does not need to exist, but the parent directory must exist and be inside the workspace.
    - Valid paths inside the workspace are allowed.
    """
    workspace = Path(workspace_dir).resolve()

    # Resolve the path relative to the workspace if it's relative, or resolve directly if it's absolute
    try:
        raw_path = Path(path_str)
        if raw_path.is_absolute():
            resolved_path = raw_path.resolve()
        else:
            resolved_path = (workspace / raw_path).resolve()
    except Exception as e:
        raise FormatError(f"Failed to resolve path '{path_str}': {e}")

    # Check that resolved_path is strictly within the workspace
    try:
        resolved_path.relative_to(workspace)
    except ValueError:
        raise FormatError(f"Access denied: path '{path_str}' escapes the workspace directory '{workspace}'.")

    if is_create:
        # Parent directory must exist
        parent_dir = resolved_path.parent
        # Also ensure parent directory doesn't escape the workspace!
        try:
            parent_dir.relative_to(workspace)
        except ValueError:
            raise FormatError(
                f"Access denied: parent directory '{parent_dir}' escapes the workspace directory '{workspace}'."
            )

        if env is not None:
            container_parent = parent_dir.as_posix()
            exists = env.communicate(f"test -d {shlex.quote(container_parent)} && echo 'yes'").strip()
            if exists != "yes":
                raise FormatError(f"Parent directory '{container_parent}' does not exist for creating '{path_str}'.")
        else:
            if not parent_dir.exists():
                raise FormatError(f"Parent directory '{parent_dir}' does not exist for creating '{path_str}'.")
            if not parent_dir.is_dir():
                raise FormatError(f"Parent path '{parent_dir}' is not a directory.")
    else:
        # File must exist
        if env is not None:
            container_path = resolved_path.as_posix()
            exists = env.communicate(f"test -e {shlex.quote(container_path)} && echo 'yes'").strip()
            if exists != "yes":
                raise FormatError(f"File '{container_path}' does not exist.")
            is_file = env.communicate(f"test -f {shlex.quote(container_path)} && echo 'yes'").strip()
            if is_file != "yes":
                raise FormatError(f"Path '{container_path}' is not a file.")
        else:
            if not resolved_path.exists():
                raise FormatError(f"File '{path_str}' does not exist.")
            if not resolved_path.is_file():
                raise FormatError(f"Path '{path_str}' is not a file.")

    return resolved_path
