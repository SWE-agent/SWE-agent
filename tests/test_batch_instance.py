import json

import pytest
from swerex.deployment.config import DockerDeploymentConfig

from sweagent.agent.problem_statement import TextProblemStatement
from sweagent.environment.repo import GithubRepoConfig, PreExistingRepoConfig
from sweagent.run.batch_instances import BatchInstance, SimpleBatchInstance, SWEBenchInstances, _slice_spec_to_slice


def test_simple_batch_from_swe_bench_to_full_batch_instance(test_data_sources_path):
    sb_instance = json.loads((test_data_sources_path / "swe-bench-dev-easy.json").read_text())[0]
    instance = SimpleBatchInstance.from_swe_bench(sb_instance).to_full_batch_instance(
        DockerDeploymentConfig(image="python:3.11")
    )
    assert isinstance(instance.env.repo, PreExistingRepoConfig)
    assert instance.env.repo.repo_name == "testbed"
    assert isinstance(instance.env.deployment, DockerDeploymentConfig)
    assert instance.env.deployment.image == "docker.io/swebench/sweb.eval.x86_64.pydicom_1776_pydicom-1458:latest"
    assert isinstance(instance.problem_statement, TextProblemStatement)
    assert instance.problem_statement.text == sb_instance["problem_statement"]
    assert instance.problem_statement.id == "pydicom__pydicom-1458"


@pytest.mark.parametrize("repo_name", ["go-github", "github", "github-action-build-chain"])
def test_simple_batch_treats_repo_names_containing_github_as_existing_repos(repo_name):
    instance = SimpleBatchInstance(
        image_name="python:3.11",
        problem_statement="Fix the bug",
        instance_id="repo-name-with-github",
        repo_name=repo_name,
    ).to_full_batch_instance(DockerDeploymentConfig(image="python:3.11"))

    assert isinstance(instance.env.repo, PreExistingRepoConfig)
    assert instance.env.repo.repo_name == repo_name


def test_simple_batch_treats_github_urls_as_github_repos():
    instance = SimpleBatchInstance(
        image_name="python:3.11",
        problem_statement="Fix the bug",
        instance_id="github-url",
        repo_name="https://github.com/SWE-agent/test-repo",
    ).to_full_batch_instance(DockerDeploymentConfig(image="python:3.11"))

    assert isinstance(instance.env.repo, GithubRepoConfig)
    assert instance.env.repo.github_url == "https://github.com/SWE-agent/test-repo"


def test_slice_spec_to_slice():
    assert _slice_spec_to_slice("10") == slice(10)
    assert _slice_spec_to_slice("10:20") == slice(10, 20)
    assert _slice_spec_to_slice("10:20:3") == slice(10, 20, 3)
    with pytest.raises(ValueError):
        _slice_spec_to_slice("10:20:3:4")


@pytest.mark.slow
def test_get_swe_bench_instances():
    for subset in ["lite", "verified", "full"]:
        for split in ["dev", "test"]:
            if subset in ["verified", "multilingual"] and split == "dev":
                continue
            print(subset, split)
            instance_config = SWEBenchInstances(subset=subset, split=split)  # type: ignore
            instances = instance_config.get_instance_configs()
            assert len(instances) > 0
            assert all(isinstance(instance, BatchInstance) for instance in instances)
