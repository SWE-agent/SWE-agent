import importlib.machinery
import importlib.util
import sys
from pathlib import Path


def make_python_tool_importable(file_path: str | Path, module_name: str | None = None) -> None:
    """Import a Python executable script and add it to sys.modules.

    Args:
        file_path: Path to the executable script (relative or absolute)
        module_name: Name of the module to import the script as. If None, the filename stem is used.
    """
    # Convert to absolute path if needed
    abs_path = Path(file_path).resolve().as_posix()
    module_name = Path(file_path).stem if module_name is None else module_name

    if module_name in sys.modules:
        return  # Module already imported

    if not Path(abs_path).exists():
        msg = f"Could not load module spec for {file_path}"
        raise ImportError(msg)

    loader = importlib.machinery.SourceFileLoader(module_name, abs_path)
    spec = importlib.util.spec_from_file_location(module_name, abs_path, loader=loader)
    if spec is None:
        msg = f"Could not load module spec for {file_path}"
        raise ImportError(msg)
    spec_loader = spec.loader
    if spec_loader is None:
        msg = f"Could not load module spec for {file_path}"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec_loader.exec_module(module)
