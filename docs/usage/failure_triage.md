# Diagnosing failed runs

An unresolved task is an evaluation result, not a diagnosis. A trajectory can
contain a plausible model action followed by a broken tool response, or a working
tool followed by an incorrect code change. Inspect the earliest failed boundary
before assigning a cause.

This guide uses the following descriptive categories for bug reports. These are
manual triage labels, not fields emitted by SWE-agent or automatic classifications.

| Category | Evidence to inspect | Example |
| --- | --- | --- |
| Tool / agent-computer interface (ACI) | The action, execution result, and observation supplied to the model | An edit tool rejects a valid range, or a history processor removes output needed for the next step. |
| Loop / control | Retry messages, attempt transitions, stop conditions, and submission handling | A retry loses tool-call context, or the run continues after its configured stopping condition. |
| Environment / deployment | Startup logs, runtime exceptions, repository state, and dependency installation | The container fails to start, or a required executable is unavailable. |
| Provider / request | API exceptions, request settings, token limits, and retry logs | A provider rejects an oversized prompt or exhausts a rate limit. |
| Model / solution | The proposed action or patch, with evidence that the preceding interfaces worked | The model edits the wrong function or implements an incorrect algorithm. |

A run can involve more than one category. Record the first observed failure and
any downstream effects separately; retain uncertainty when the trace cannot
distinguish them.

## Gather the evidence

1. Open the trajectory in the [inspector](inspector.md), or read its JSON using the
   [output-file guide](trajectories.md). Compare the step's `action`, `observation`,
   `response`, and `state`; inspect `query` for the input at that step and `history`
   for the retained conversation. Use the trace logs for exception details.
2. Locate the earliest unexpected behavior. For a tool failure, include the exact
   command, relevant input file, expected result, actual output, and traceback.
   For a retry or submission problem, include the steps immediately before and
   after the transition.
3. Record the SWE-agent and SWE-ReX versions, configuration, model/provider,
   deployment type, and repository revision. Redact API keys and sensitive data
   from configuration and logs before sharing them.
4. Reduce the reproduction. Where possible, run the tool directly or use a dummy
   model/runtime to check the interface without another paid model call. If you
   compare runs, hold the model, task, and configuration constant except for the
   interface under investigation.

## Interpret exit statuses carefully

`info.exit_status` describes how the run stopped. It does not prove why the task
failed or whether a submitted patch is correct.

| Exit status | What it records | What to check next |
| --- | --- | --- |
| `submitted` | A submission was collected | Inspect the patch and evaluation result. |
| `submitted (exit_cost)` or another `submitted (...)` status | A patch was recovered after an exit condition | Inspect the enclosed exit reason and the steps before autosubmission. |
| `exit_format` | The format/requery loop exhausted its allowed attempts | Inspect parser errors, blocked actions, and shell syntax errors in the logs. |
| `exit_command_timeout` | Execution reached the consecutive-timeout limit | Check the commands, execution timeout, and runtime interruption results. |
| `exit_total_execution_time` | The cumulative execution budget was exceeded | Check recorded step execution times and the configured budget. |
| `exit_context` | An input/context limit was reached | Check request size, tool definitions, and history processors. |
| `exit_environment_error` | A SWE-ReX exception stopped the step | Inspect the runtime traceback and deployment state. |
| `exit_error` | A runtime or otherwise unhandled exception stopped the step | Use the traceback to locate the failing component. |

Batch startup failures can occur before a trajectory exists. Inspect
`run_batch_exit_statuses.yaml`, `run_batch.log`, and the instance logs as well as
`.traj` files. A collection of trajectories alone may omit such failures.

For a report, include a short causal sequence such as: "the tool returned an
incorrect line range; the next model action used that range; the edit failed."
This makes the interface problem reproducible without assuming every later
incorrect action has an independent model cause.
