from __future__ import annotations

from sweagent.acp.server import AcpAgentHook, _format_prompt_text
from sweagent.types import StepOutput


def test_acp_format_prompt_text():
    prompt = [
        {"type": "text", "text": "Fix the bug in the parser."},
        {
            "type": "resource_link",
            "name": "parser.py",
            "uri": "file:///repo/parser.py",
            "description": "Target file",
        },
    ]
    text = _format_prompt_text(prompt)
    assert "Fix the bug in the parser." in text
    assert "parser.py" in text
    assert "file:///repo/parser.py" in text
    assert "Target file" in text


def test_acp_agent_hook_emits_tool_flow():
    updates: list[dict[str, object]] = []
    hook = AcpAgentHook(session_id="sess_1", send_update=updates.append)
    step = StepOutput(output="Working on it.", action="ls -la", observation="file1\nfile2")
    hook.on_actions_generated(step=step)
    hook.on_action_started(step=step)
    hook.on_action_executed(step=step)

    update_types = [update["sessionUpdate"] for update in updates]
    assert update_types == ["agent_message_chunk", "tool_call", "tool_call_update", "tool_call_update"]
    tool_call_id = updates[1]["toolCallId"]
    assert updates[2]["toolCallId"] == tool_call_id
    assert updates[3]["toolCallId"] == tool_call_id
    assert updates[3]["status"] == "completed"
    assert updates[3]["content"][0]["content"]["text"] == "file1\nfile2"


def test_acp_agent_hook_uses_tool_call_ids():
    updates: list[dict[str, object]] = []
    hook = AcpAgentHook(session_id="sess_2", send_update=updates.append)
    step = StepOutput(
        output="Running command.",
        action="ls",
        observation="ok",
        tool_calls=[{"id": "call_123", "function": {"name": "bash", "arguments": {"command": "ls"}}}],
        tool_call_ids=["call_123"],
    )
    hook.on_actions_generated(step=step)
    hook.on_action_started(step=step)

    assert updates[1]["toolCallId"] == "call_123"
    assert updates[1]["rawInput"]["name"] == "bash"
