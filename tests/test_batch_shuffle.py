from swerex.deployment.config import DockerDeploymentConfig

from sweagent.run.batch_instances import SimpleBatchInstance


def test_batch_shuffle_preserves_global_random_state():
    import random

    from sweagent.run.batch_instances import _filter_batch_items

    instances = [
        SimpleBatchInstance(
            image_name="python:3.11", problem_statement="Fix", instance_id=str(i)
        ).to_full_batch_instance(DockerDeploymentConfig(image="python:3.11"))
        for i in range(10)
    ]
    original_ids = [item.problem_statement.id for item in instances]
    random_state = random.getstate()
    try:
        shuffled = _filter_batch_items(instances, filter_=".*", shuffle=True)
        assert random.getstate() == random_state
        assert [item.problem_statement.id for item in shuffled] == ["7", "3", "2", "8", "5", "6", "9", "4", "0", "1"]
        assert [item.problem_statement.id for item in instances] == original_ids
        assert _filter_batch_items(list(reversed(instances)), filter_=".*", shuffle=True) == shuffled
    finally:
        random.setstate(random_state)
