import yaml
from pydantic import BaseModel

from sweagent.run.common import dump_config_yaml
from sweagent.utils.serialization import merge_nested_dicts


class _SampleConfig(BaseModel):
    name: str
    count: int = 1


def test_saved_config_yaml_reloads_as_a_mapping():
    text = dump_config_yaml(_SampleConfig(name="repeat"))
    loaded = yaml.safe_load(text)

    assert loaded == {"name": "repeat", "count": 1}
    assert merge_nested_dicts({}, loaded)["name"] == "repeat"


def test_dumping_the_json_string_is_not_a_mapping():
    text = yaml.dump(_SampleConfig(name="repeat").model_dump_json(), indent=2)
    loaded = yaml.safe_load(text)

    assert isinstance(loaded, str)
