from sweagent.agent.hooks.status import SetStatusAgentHook
from sweagent.types import AgentInfo, StepOutput


def test_status_hook_cost_not_double_counted_on_retry():
    """Regression test: the status line must not double-count the previous
    attempt's cost at the start of a retry attempt.

    ``SetStatusAgentHook.on_setup_attempt`` folds the finished attempt's cost
    into ``_previous_cost``, but (before the fix) never reset ``_cost``, even
    though each retry attempt starts from a fresh agent whose per-attempt
    ``instance_cost`` starts at 0 again (see ``RetryAgent._setup_agent``).
    Because the status line shows ``_previous_cost + _cost``, every status line
    of the new attempt displayed the previous attempt's cost twice until the
    attempt's first step completed and ``on_step_done`` overwrote ``_cost``.
    """
    statuses: list[str] = []
    hook = SetStatusAgentHook("inst-1", lambda _id, msg: statuses.append(msg))

    # Attempt 1: two steps of $0.50 each -> $1.00 spent in total.
    hook.on_setup_attempt()
    for i in range(2):
        hook.on_step_start()
        hook.on_step_done(
            step=StepOutput(),
            info=AgentInfo(model_stats={"instance_cost": 0.5 * (i + 1)}),
        )
    assert statuses[-1] == "Step   2 ($0.50)"

    # Attempt 2 (retry) starts: no money spent in the new attempt yet, so the
    # status line must still show the $1.00 from attempt 1, not $2.00.
    hook.on_setup_attempt()
    statuses.clear()
    hook.on_step_start()
    assert statuses[-1] == "Attempt 2 Step   1 ($1.00)"

    # Once attempt 2's first step completes, its cost is added on top.
    hook.on_step_done(
        step=StepOutput(),
        info=AgentInfo(model_stats={"instance_cost": 0.25}),
    )
    hook.on_step_start()
    assert statuses[-1] == "Attempt 2 Step   2 ($1.25)"
