# SWE-agent command line interface

All functionality of SWE-agent is available via the command line interface via the `sweagent` command.

You can run `sweagent --help` to see all subcommands.

## Running SWE-agent

* `sweagent run`: Run SWE-agent on a single issue ([tutorial](hello_world.md)).
* `sweagent run-batch`: Run SWE-agent on a batch of issues ([tutorial](batch_mode.md)).
* `sweagent run-replay`: Replay a trajectory file or a demo file. This means that you take all actions from the trajectory and execute them again in the environment. Useful for debugging your [tools](../config/tools.md) or for building new [demonstrations](../config/demonstrations.md).

## Inspecting runs

* `sweagent inspect` or `sweagent i`: Open the command line inspector ([more information](inspector.md)).
* `sweagent inspector` or `sweagent I`: Open the web-based inspector ([more information](inspector.md)).
* `sweagent quick-stats` or `sweagent qs`: When executed in a directory with trajectories, displays a summary of `exit_status` and more

## Advanced scripts

* `sweagent merge-preds`: Merge multiple prediction files into a single file.
* `sweagent traj-to-demo`: Convert a trajectory file to an easy to edit demo file ([more information on demonstrations](../config/demonstrations.md)).
* `sweagent remove-unfinished`: Remove unfinished trajectories
