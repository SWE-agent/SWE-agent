from __future__ import annotations

import json
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from uuid import uuid4

import flask  # noqa
import yaml
from flask import Flask, make_response, render_template, request, session
from flask_cors import CORS
from flask_socketio import SocketIO

from sweagent import CONFIG_DIR, PACKAGE_DIR
from sweagent.agent.problem_statement import problem_statement_from_simplified_input
from sweagent.api.hooks import AgentUpdateHook, EnvUpdateHook, MainUpdateHook, WebUpdate
from sweagent.api.utils import AttrDict, ThreadWithExc
from sweagent.environment.repo import repo_from_simplified_input

# baaaaaaad
sys.path.append(str(PACKAGE_DIR.parent))
from sweagent.run.run_single import RunSingle, RunSingleConfig

app = Flask(__name__, template_folder=Path(__file__).parent)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
# Setting these variables outside of `if __name__ == "__main__"` because when run Flask server with
# `flask run` it will skip the if block. Therefore, the app will return an error for missing `secret_key`
# Setting it here will allow both `flask run` and `python server.py` to work
app.secret_key = "super secret key"
app.config["SESSION_TYPE"] = "memcache"

THREADS: dict[str, MainThread] = {}


def ensure_session_id_set():
    """Ensures a session ID is set for this user"""
    session_id = session.get("session_id", None)
    if not session_id:
        session_id = uuid4().hex
        session["session_id"] = session_id
    return session_id


class MainThread(ThreadWithExc):
    def __init__(self, settings: RunSingleConfig, wu: WebUpdate):
        super().__init__()
        self._wu = wu
        self._settings = settings

    def run(self) -> None:
        # fixme: This actually redirects all output from all threads to the socketio, which is not what we want
        with redirect_stdout(self._wu.log_stream):
            with redirect_stderr(self._wu.log_stream):
                try:
                    main = RunSingle.from_config(self._settings)
                    main.add_hook(MainUpdateHook(self._wu))
                    main.agent.add_hook(AgentUpdateHook(self._wu))
                    main.env.add_hook(EnvUpdateHook(self._wu))
                    main.run()
                except Exception as e:
                    short_msg = str(e)
                    max_len = 350
                    if len(short_msg) > max_len:
                        short_msg = f"{short_msg[:max_len]}... (see log for details)"
                    traceback_str = traceback.format_exc()
                    self._wu.up_log(traceback_str)
                    self._wu.up_agent(f"Error: {short_msg}")
                    self._wu.up_banner("Critical error: " + short_msg)
                    self._wu.finish_run()
                    raise

    def stop(self):
        while self.is_alive():
            self.raise_exc(SystemExit)
            time.sleep(0.1)
        self._wu.finish_run()
        self._wu.up_agent("Run stopped by user")


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    print("Client connected")


@app.route("/run", methods=["GET", "OPTIONS"])
def run():
    session_id = ensure_session_id_set()
    if request.method == "OPTIONS":  # CORS preflight
        return _build_cors_preflight_response()
    # While we're running as a local UI, let's make sure that there's at most
    # one run at a time
    global THREADS
    for thread in THREADS.values():
        if thread.is_alive():
            thread.stop()
    wu = WebUpdate(socketio)
    wu.up_agent("Starting the run")
    # Use Any type to silence annoying false positives from mypy
    run: Any = AttrDict.from_nested_dicts(json.loads(request.args["runConfig"]))
    print(run)
    print(run.environment)
    print(run.environment.base_commit)
    model_name: str = run.agent.model.model_name
    test_run: bool = run.extra.test_run
    if test_run:
        model_name = "instant_empty_submit"
    default_config = yaml.safe_load(Path(CONFIG_DIR / "default.yaml").read_text())
    config = {
        **default_config,
        "agent": {
            "model": {
                "model_name": model_name,
            },
        },
        "environment": {
            "image_name": run.environment.image_name,
            "script": run.environment.script,
        },
    }
    config["problem_statement"] = problem_statement_from_simplified_input(
        input=run.problem_statement.input,
        type=run.problem_statement.type,
    )
    config["environment"]["repo"] = repo_from_simplified_input(
        input=run.environment.repo_path,
        base_commit=run.environment.base_commit,
        type="auto",
    )
    config = RunSingleConfig.model_validate(**config)
    thread = MainThread(config, wu)
    THREADS[session_id] = thread
    thread.start()
    return "Commands are being executed", 202


@app.route("/stop")
def stop():
    session_id = ensure_session_id_set()
    global THREADS
    print(f"Stopping session {session_id}")
    print(THREADS)
    thread = THREADS.get(session_id)
    if thread and thread.is_alive():
        print(f"Thread {thread} is alive")
        thread.stop()
    else:
        print(f"Thread {thread} is not alive")
    return "Stopping computation", 202


def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response


def run_from_cli(args: list[str] | None = None):
    app.debug = True
    socketio.run(app, port=8000, debug=True, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    run_from_cli()
