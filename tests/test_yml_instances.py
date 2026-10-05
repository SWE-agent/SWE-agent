import pytest
import yaml

from sweagent.run.batch_instances import InstancesFromFile
from sweagent.utils.files import load_file


@pytest.mark.parametrize("suffix", [".yml", ".yaml"])
def test_batch_instances_accept_yaml_extensions(tmp_path, suffix):
    rows = [{"image_name": "python:3.11", "problem_statement": "Fix the bug", "instance_id": "example"}]
    path = tmp_path / f"instances{suffix}"
    path.write_text(yaml.safe_dump(rows))
    assert load_file(str(path)) == rows
    instances = InstancesFromFile(path=path).get_instance_configs()
    assert len(instances) == 1
    assert instances[0].problem_statement.id == "example"
    assert instances[0].problem_statement.text == "Fix the bug"


def test_unknown_extension_still_rejected(tmp_path):
    path = tmp_path / "instances.txt"
    path.write_text("[]")
    with pytest.raises(NotImplementedError, match="Unsupported file extension"):
        load_file(path)
