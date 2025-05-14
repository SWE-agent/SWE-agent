import io
from copy import deepcopy
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString as LSS


def _convert_to_yaml_literal_string(d: Any) -> Any:
    """Convert any multi-line strings in nested data object to LiteralScalarString.
    This will then use the `|-` syntax of yaml.
    """
    d = deepcopy(d)
    if isinstance(d, dict):
        for key, value in d.items():
            d[key] = _convert_to_yaml_literal_string(value)
    elif isinstance(d, list):
        for i, item in enumerate(d):
            d[i] = _convert_to_yaml_literal_string(item)
    elif isinstance(d, str) and "\n" in d:
        d = LSS(d.replace("\r\n", "\n").replace("\r", "\n"))
    return d


def _yaml_serialization_with_linebreaks(data: Any) -> str:
    data = _convert_to_yaml_literal_string(data)
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = float("inf")
    yaml.default_flow_style = False
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    return buffer.getvalue()


def merge_nested_dicts(d1: dict, d2: dict) -> dict:
    """Merge two nested dictionaries, updating d1 in place.
    If a key exists in both dictionaries, the value from d2 will be used.
    """
    for key, value in d2.items():
        if isinstance(value, dict):
            d1[key] = merge_nested_dicts(d1.get(key, {}), value)
        else:
            d1[key] = value
    return d1
