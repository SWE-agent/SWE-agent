import json
from pathlib import Path

import pytest

from sweagent.run.common import save_predictions
from sweagent.run.run import main
from sweagent.types import AgentRunResult


@pytest.mark.slow
def test_expert_instances(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "expert_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.type",
        "expert_file",
        "--instances.path",
        str(ds_path),
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
    ]
    main(cmd)
    for _id in ["simple_test_problem", "simple_test_problem_2"]:
        assert (tmp_path / f"{_id}" / f"{_id}.traj").exists(), list(tmp_path.iterdir())


@pytest.mark.slow
def test_simple_instances(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "simple_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.path",
        str(ds_path),
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
    ]
    main(cmd)
    assert (tmp_path / "simple_test_problem" / "simple_test_problem.traj").exists(), list(tmp_path.iterdir())


def test_empty_instances_simple(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "simple_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.path",
        str(ds_path),
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
        "--instances.filter",
        "doesnotmatch",
    ]
    with pytest.raises(ValueError, match="No instances to run"):
        main(cmd)


def test_empty_instances_expert(test_data_sources_path: Path, tmp_path: Path):
    ds_path = test_data_sources_path / "expert_instances.yaml"
    assert ds_path.exists()
    cmd = [
        "run-batch",
        "--agent.model.name",
        "instant_empty_submit",
        "--instances.path",
        str(ds_path),
        "--instances.type",
        "expert_file",
        "--output_dir",
        str(tmp_path),
        "--raise_exceptions",
        "True",
        "--instances.filter",
        "doesnotmatch",
    ]
    with pytest.raises(ValueError, match="No instances to run"):
        main(cmd)


@pytest.mark.parametrize(("instance_filter", "expected_ids"), [(".*", {"group", "group/case"}), ("^group$", {"group"})])
def test_merge_selected_predictions_from_nested_instance_directories(
    tmp_path: Path, instance_filter: str, expected_ids: set[str]
):
    ids = ["group", "group/case"]
    source = tmp_path / "instances.json"
    source.write_text(
        json.dumps([{"image_name": "", "problem_statement": f"Task {iid}", "instance_id": iid} for iid in ids])
    )
    output = tmp_path / "outputs"
    for iid in ids:
        save_predictions(output, iid, AgentRunResult(info={"submission": f"patch for {iid}"}, trajectory=[]))
        trajectory = output / iid / f"{iid}.traj"
        trajectory.write_text(json.dumps({"info": {"exit_status": "submitted"}}))

    main(
        [
            "run-batch",
            "--agent.model.name",
            "instant_empty_submit",
            "--instances.type",
            "file",
            "--instances.path",
            str(source),
            "--instances.deployment.type",
            "dummy",
            "--instances.filter",
            instance_filter,
            "--output_dir",
            str(output),
            "--progress_bar",
            "False",
        ]
    )
    data = json.loads((output / "preds.json").read_text())
    assert {iid: item["model_patch"] for iid, item in data.items()} == {iid: f"patch for {iid}" for iid in expected_ids}


def test_merge_preds_cli_searches_subdirectories(tmp_path: Path):
    save_predictions(tmp_path, "group/case", AgentRunResult(info={"submission": "patch"}, trajectory=[]))

    main(["merge-preds", str(tmp_path)])

    data = json.loads((tmp_path / "preds.json").read_text())
    assert data["group/case"]["model_patch"] == "patch"


# This doesn't work because we need to retrieve environment variables from the environment
# in order to format our templates.
# def test_run_batch_swe_bench_instances(tmp_path: Path):
#     cmd = [
#         "run-batch",
#         "--agent.model.name",
#         "instant_empty_submit",
#         "--instances.subset",
#         "lite",
#         "--instances.split",
#         "test",
#         "--instances.slice",
#         "0:1",
#         "--output_dir",
#         str(tmp_path),
#         "--raise_exceptions",
#         "--instances.deployment.type",
#         "dummy",
#     ]
#     main(cmd)
