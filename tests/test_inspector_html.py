from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

VIEWER = Path(__file__).resolve().parents[1] / "sweagent" / "inspector" / "fileViewer.js"

NODE_CHECK = r"""
const fs = require("fs");
const vm = require("vm");
const context = {
  console,
  Date,
  Math,
  setTimeout,
  clearTimeout,
  document: {},
  window: { location: { protocol: "http:", hostname: "127.0.0.1", port: "8000" } },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);
const html = context.createTrajectoryItem({
  response: "<script>response</script>",
  action: "<script>action</script>",
  observation: "see ![x](data:image/png\" onload=\"alert(1);base64,aaaa)",
  execution_time: "<script>time</script>",
  query: [{
    role: "<img src=x onerror=alert(1)>",
    content: "hello",
    tool_calls: [{
      id: "<script>id</script>",
      function: { name: "<script>name</script>", arguments: "{\"a\":\"<b>\"}" },
    }],
  }],
}, 0);
const bad = ["<script>", "<img src=x", "onload=\""];
for (const needle of bad) {
  if (html.includes(needle)) {
    console.error("unescaped " + needle);
    process.exit(1);
  }
}
if (!html.includes("&lt;script&gt;response")) process.exit(2);
if (!html.includes("&lt;script&gt;name")) process.exit(3);
console.log("ok");
"""


def test_inspector_escapes_untrusted_trajectory_fields():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "-e", NODE_CHECK, str(VIEWER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
