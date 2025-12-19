"""Run SWE-agent as an ACP (Agent Client Protocol) stdio server."""

from __future__ import annotations

import json
import logging
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sweagent import __version__
from sweagent.agent.agents import DefaultAgent, RetryAgent, get_agent_from_config
from sweagent.agent.hooks.abstract import AbstractAgentHook
from sweagent.agent.problem_statement import GithubIssue, TextProblemStatement
from sweagent.agent.reviewer import ReviewSubmission, ScoreRetryLoop
from sweagent.environment.repo import LocalRepoConfig
from sweagent.environment.swe_env import SWEEnv
from sweagent.run.common import BasicCLI, ConfigHelper
from sweagent.run.run_single import RunSingleConfig
from sweagent.types import StepOutput
from sweagent.utils.config import load_environment_variables
from sweagent.utils.github import _is_github_issue_url
from sweagent.utils.log import get_logger, register_thread_name, set_stream_handler_levels


ACP_PROTOCOL_VERSION = 1


class AcpCancelled(RuntimeError):
    """Raised when an ACP prompt is cancelled."""


def _format_prompt_text(prompt: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in prompt:
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text", "")
            if text:
                parts.append(text)
        elif block_type == "resource_link":
            name = block.get("name") or block.get("title") or "resource"
            uri = block.get("uri", "")
            description = block.get("description")
            line = f"[resource] {name}"
            if uri:
                line += f" ({uri})"
            if description:
                line += f"\n{description}"
            parts.append(line)
        elif block_type == "resource":
            resource = block.get("resource", {})
            text = resource.get("text")
            if text:
                uri = resource.get("uri", "")
                header = f"[resource] {uri}" if uri else "[resource]"
                parts.append(f"{header}\n{text}")
            else:
                parts.append("[resource] (non-text resource omitted)")
        elif block_type:
            parts.append(f"[unsupported content: {block_type}]")
    return "\n\n".join(part for part in parts if part)


def _infer_tool_kind(tool_name: str | None, action: str | None) -> str:
    candidate = (tool_name or action or "").lower()
    if any(token in candidate for token in ("read", "cat", "show")):
        return "read"
    if any(token in candidate for token in ("write", "edit", "apply", "patch")):
        return "edit"
    if any(token in candidate for token in ("delete", "remove", "rm")):
        return "delete"
    if any(token in candidate for token in ("move", "rename", "mv")):
        return "move"
    if any(token in candidate for token in ("search", "grep", "rg", "find")):
        return "search"
    if any(token in candidate for token in ("bash", "shell", "exec", "run", "python")):
        return "execute"
    if "think" in candidate:
        return "think"
    if any(token in candidate for token in ("fetch", "curl", "wget", "http")):
        return "fetch"
    return "other"


class AcpAgentHook(AbstractAgentHook):
    def __init__(self, *, session_id: str, send_update: Callable[[dict[str, Any]], None]):
        self._session_id = session_id
        self._send_update = send_update
        self._tool_call_counter = 0
        self._active_tool_call_ids: list[str] = []

    def _next_tool_call_id(self) -> str:
        self._tool_call_counter += 1
        return f"swea_call_{self._tool_call_counter}"

    def _emit_tool_call(
        self,
        *,
        tool_call_id: str,
        title: str,
        kind: str,
        raw_input: dict[str, Any] | None,
    ) -> None:
        update: dict[str, Any] = {
            "sessionUpdate": "tool_call",
            "toolCallId": tool_call_id,
            "title": title,
            "kind": kind,
            "status": "pending",
        }
        if raw_input is not None:
            update["rawInput"] = raw_input
        self._send_update(update)

    def _emit_tool_call_update(
        self,
        *,
        tool_call_id: str,
        status: str,
        content_text: str | None = None,
        raw_output: dict[str, Any] | None = None,
    ) -> None:
        update: dict[str, Any] = {
            "sessionUpdate": "tool_call_update",
            "toolCallId": tool_call_id,
            "status": status,
        }
        if content_text:
            update["content"] = [
                {
                    "type": "content",
                    "content": {"type": "text", "text": content_text},
                }
            ]
        if raw_output is not None:
            update["rawOutput"] = raw_output
        self._send_update(update)

    def on_actions_generated(self, *, step: StepOutput) -> None:
        self._active_tool_call_ids = []
        output = step.output.strip()
        if output:
            self._send_update(
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": output},
                }
            )

        action = step.action.strip()
        if action.lower() == "exit":
            return

        if step.tool_calls:
            for idx, tool_call in enumerate(step.tool_calls):
                tool_call_id = tool_call.get("id")
                if not tool_call_id and step.tool_call_ids:
                    tool_call_id = step.tool_call_ids[idx]
                if not tool_call_id:
                    tool_call_id = self._next_tool_call_id()
                tool_name = (tool_call.get("function") or {}).get("name") or "tool"
                kind = _infer_tool_kind(tool_name, action)
                self._active_tool_call_ids.append(tool_call_id)
                raw_input = tool_call.get("function") or tool_call
                self._emit_tool_call(
                    tool_call_id=tool_call_id,
                    title=tool_name,
                    kind=kind,
                    raw_input=raw_input,
                )
        elif action:
            tool_call_id = self._next_tool_call_id()
            kind = _infer_tool_kind(None, action)
            self._active_tool_call_ids = [tool_call_id]
            self._emit_tool_call(
                tool_call_id=tool_call_id,
                title=action,
                kind=kind,
                raw_input={"command": action},
            )

    def on_action_started(self, *, step: StepOutput) -> None:
        for tool_call_id in self._active_tool_call_ids:
            self._emit_tool_call_update(tool_call_id=tool_call_id, status="in_progress")

    def on_action_executed(self, *, step: StepOutput) -> None:
        observation = step.observation.strip()
        raw_output = {"output": step.observation} if step.observation else None
        for tool_call_id in self._active_tool_call_ids:
            self._emit_tool_call_update(
                tool_call_id=tool_call_id,
                status="completed",
                content_text=observation or None,
                raw_output=raw_output,
            )
        self._active_tool_call_ids = []


class _JsonRpcWriter:
    def __init__(self, logger: logging.Logger):
        self._lock = threading.Lock()
        self._logger = logger

    def send(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        with self._lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        self._logger.debug("ACP -> %s", line)


@dataclass
class PromptState:
    request_id: Any
    cancel_event: threading.Event
    env: SWEEnv | None = None
    thread: threading.Thread | None = None


@dataclass
class SessionState:
    session_id: str
    cwd: Path
    config: RunSingleConfig
    mode_id: str | None = None
    prompt: PromptState | None = None


class AcpServer:
    def __init__(self, base_config: RunSingleConfig):
        self._logger = get_logger("swea-acp", emoji="🔌")
        self._writer = _JsonRpcWriter(self._logger)
        self._base_config = base_config
        self._sessions: dict[str, SessionState] = {}

    def serve(self) -> None:
        self._logger.info("Starting ACP stdio server")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            self._logger.debug("ACP <- %s", line)
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._logger.warning("Ignoring invalid JSON-RPC line")
                continue
            self._handle_message(message)

    def _handle_message(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if not method:
            return
        if "id" in message:
            self._handle_request(message)
        else:
            self._handle_notification(message)

    def _handle_request(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
                self._send_result(request_id, result)
            elif method == "session/new":
                result = self._handle_session_new(params)
                self._send_result(request_id, result)
            elif method == "session/prompt":
                self._handle_session_prompt(request_id, params)
            elif method == "session/set_mode":
                result = self._handle_session_set_mode(params)
                self._send_result(request_id, result)
            else:
                self._send_error(request_id, -32601, f"Unknown method: {method}")
        except ValueError as exc:
            self._send_error(request_id, -32602, str(exc))
        except Exception as exc:
            self._logger.exception("ACP request failed: %s", method)
            self._send_error(request_id, -32603, str(exc))

    def _handle_notification(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params") or {}
        if method == "session/cancel":
            self._handle_session_cancel(params)
            return
        self._logger.debug("Ignoring notification: %s", method)

    def _send_result(self, request_id: Any, result: dict[str, Any]) -> None:
        self._writer.send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send_error(self, request_id: Any, code: int, message: str) -> None:
        self._writer.send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})

    def _send_update(self, session_id: str, update: dict[str, Any]) -> None:
        self._writer.send(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {"sessionId": session_id, "update": update},
            }
        )

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": ACP_PROTOCOL_VERSION,
            "agentCapabilities": {
                "loadSession": False,
                "mcpCapabilities": {"http": False, "sse": False},
                "promptCapabilities": {"audio": False, "embeddedContext": False, "image": False},
                "sessionCapabilities": {},
            },
            "agentInfo": {"name": "swe-agent", "title": "SWE-agent", "version": __version__},
            "authMethods": [],
        }

    def _handle_session_new(self, params: dict[str, Any]) -> dict[str, Any]:
        cwd = params.get("cwd")
        if not cwd:
            raise ValueError("session/new requires cwd")
        cwd_path = Path(cwd)
        if not cwd_path.is_absolute():
            raise ValueError("cwd must be an absolute path")
        session_id = f"swea_{uuid.uuid4().hex[:12]}"
        config = self._base_config.model_copy(deep=True)
        if config.env.repo is None:
            config.env.repo = LocalRepoConfig(path=cwd_path)
        self._sessions[session_id] = SessionState(session_id=session_id, cwd=cwd_path, config=config)
        return {"sessionId": session_id}

    def _handle_session_set_mode(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("sessionId")
        mode_id = params.get("modeId")
        if not session_id or not mode_id:
            raise ValueError("session/set_mode requires sessionId and modeId")
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("Unknown sessionId")
        session.mode_id = mode_id
        return {}

    def _handle_session_prompt(self, request_id: Any, params: dict[str, Any]) -> None:
        session_id = params.get("sessionId")
        if not session_id:
            self._send_error(request_id, -32602, "sessionId is required")
            return
        session = self._sessions.get(session_id)
        if session is None:
            self._send_error(request_id, -32602, "Unknown sessionId")
            return
        if session.prompt is not None:
            self._send_error(request_id, -32000, "Session already running a prompt")
            return
        prompt = params.get("prompt")
        if not isinstance(prompt, list):
            self._send_error(request_id, -32602, "prompt must be a list")
            return
        cancel_event = threading.Event()
        prompt_state = PromptState(request_id=request_id, cancel_event=cancel_event)
        session.prompt = prompt_state
        thread = threading.Thread(
            target=self._run_prompt,
            args=(session, prompt, prompt_state),
            daemon=True,
        )
        prompt_state.thread = thread
        thread.start()

    def _handle_session_cancel(self, params: dict[str, Any]) -> None:
        session_id = params.get("sessionId")
        if not session_id:
            return
        session = self._sessions.get(session_id)
        if session is None or session.prompt is None:
            return
        session.prompt.cancel_event.set()
        if session.prompt.env is not None:
            session.prompt.env.interrupt_session()

    def _run_prompt(self, session: SessionState, prompt: list[dict[str, Any]], prompt_state: PromptState) -> None:
        register_thread_name("acp")
        stop_reason = "end_turn"
        try:
            prompt_text = _format_prompt_text(prompt)
            if _is_github_issue_url(prompt_text.strip()):
                problem_statement = GithubIssue(github_url=prompt_text.strip())
            else:
                problem_statement = TextProblemStatement(
                    text=prompt_text,
                    id=f"{session.session_id}-{uuid.uuid4().hex[:6]}",
                )
            config = session.config.model_copy(deep=True)
            config.problem_statement = problem_statement
            config.set_default_output_dir()
            load_environment_variables(config.env_var_path)
            config.output_dir.mkdir(parents=True, exist_ok=True)
            env = SWEEnv.from_config(config.env)
            prompt_state.env = env
            agent = get_agent_from_config(config.agent)
            if hasattr(agent, "replay_config"):
                agent.replay_config = config  # type: ignore[assignment]
            send_update = lambda update: self._send_update(session.session_id, update)
            agent.add_hook(AcpAgentHook(session_id=session.session_id, send_update=send_update))
            env.start()
            if isinstance(agent, RetryAgent):
                self._run_retry_agent(agent, problem_statement, config.output_dir, prompt_state.cancel_event)
            else:
                self._run_default_agent(agent, problem_statement, config.output_dir, prompt_state.cancel_event)
        except AcpCancelled:
            stop_reason = "cancelled"
        except Exception as exc:
            stop_reason = "end_turn"
            self._send_update(
                session.session_id,
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": f"SWE-agent error: {exc}"},
                },
            )
        finally:
            if prompt_state.env is not None:
                try:
                    prompt_state.env.close()
                except Exception as exc:
                    self._logger.warning("Failed to close environment: %s", exc)
            session.prompt = None
            self._send_result(prompt_state.request_id, {"stopReason": stop_reason})

    def _run_default_agent(
        self,
        agent: DefaultAgent,
        problem_statement: TextProblemStatement | GithubIssue,
        output_dir: Path,
        cancel_event: threading.Event,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        agent.setup(env=env, problem_statement=problem_statement, output_dir=output_dir)
        agent._chook.on_run_start()
        step_output = StepOutput()
        while not step_output.done:
            if cancel_event.is_set():
                raise AcpCancelled()
            step_output = agent.step()
            if cancel_event.is_set():
                raise AcpCancelled()
            agent.save_trajectory()
        if cancel_event.is_set():
            raise AcpCancelled()
        agent._chook.on_run_done(trajectory=agent.trajectory, info=agent.info)

    def _run_retry_agent(
        self,
        agent: RetryAgent,
        problem_statement: TextProblemStatement | GithubIssue,
        output_dir: Path,
        cancel_event: threading.Event,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        agent.setup(env=env, problem_statement=problem_statement, output_dir=output_dir)
        agent._chook.on_run_start()
        step_output = StepOutput()
        agent._setup_agent()
        while not step_output.done:
            if cancel_event.is_set():
                raise AcpCancelled()
            step_output = agent.step()
            if cancel_event.is_set():
                raise AcpCancelled()
            agent.save_trajectory(choose=False)
            if step_output.done:
                agent._rloop.on_submit(  # type: ignore[union-attr]
                    ReviewSubmission(
                        trajectory=agent._agent.trajectory,  # type: ignore[union-attr]
                        info=agent._agent.info,  # type: ignore[union-attr]
                        model_stats=agent._agent.model.stats,  # type: ignore[union-attr]
                    )
                )
                if isinstance(agent._rloop, ScoreRetryLoop):  # type: ignore[union-attr]
                    agent._agent.info["review"] = agent._rloop.reviews[-1].model_dump()  # type: ignore[union-attr]
                agent._finalize_agent_run()
                agent.save_trajectory(choose=False)
                if agent._rloop.retry():  # type: ignore[union-attr]
                    agent._next_attempt()
                    step_output.done = False
        if cancel_event.is_set():
            raise AcpCancelled()
        agent.save_trajectory(choose=True)
        agent._chook.on_run_done(trajectory=agent._agent.trajectory, info=agent._agent.info)  # type: ignore[union-attr]


def run_from_cli(args: list[str] | None = None) -> None:
    if args is None:
        args = sys.argv[1:]
    set_stream_handler_levels(logging.INFO)
    help_text = (
        __doc__ + "\n\n=== ACP CONFIG OPTIONS ===\n\n" + ConfigHelper().get_help(RunSingleConfig)  # type: ignore
    )
    config = BasicCLI(RunSingleConfig, help_text=help_text).get_config(args)  # type: ignore
    server = AcpServer(config)
    server.serve()
