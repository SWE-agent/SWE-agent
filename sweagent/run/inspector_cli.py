"""This is a command line tool to inspect trajectory JSON files."""

import argparse
import collections
import copy
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from sweagent.utils.files import load_file
from sweagent.utils.serialization import _yaml_serialization_with_linebreaks


def _move_items_top(d: dict, keys: list[str]) -> dict:
    """Reorder items in a dictionary.

    The first keys will be those specified in `keys`, the rest will
    be in the same order as in the original dictionary.
    """
    new_d = {}
    for key in keys:
        if key in d:
            new_d[key] = d[key]
    for key in d.keys():
        if key not in keys:
            new_d[key] = d[key]
    return new_d


class TrajectoryViewer(Static):
    BINDINGS = [
        Binding("right,l", "next_item", "Step++"),
        Binding("left,h", "previous_item", "Step--"),
        Binding("0", "first_item", "Step=0"),
        Binding("$", "last_item", "Step=-1"),
        Binding("v", "toggle_view", "Toggle view"),
        Binding("j,down", "scroll_down", "Scroll down"),
        Binding("k,up", "scroll_up", "Scroll up"),
    ]

    def __init__(self, path: Path, title: str, overview_stats: dict, *, gold_patch: str | None = None):
        """View a single trajectory."""
        super().__init__()
        self.i_step = -1
        self.trajectory = json.loads(path.read_text())
        self.show_full = False
        self.title = title
        self.overview_stats = overview_stats
        self.gold_patch = gold_patch

    def load_trajectory(self, path: Path, title: str, overview_stats: dict, *, gold_patch: str | None = None):
        """Load a new trajectory and update the viewer."""
        print("Loading", path)
        self.trajectory = json.loads(path.read_text())
        self.title = title
        self.gold_patch = gold_patch
        self.overview_stats = overview_stats
        self.scroll_top()
        self.i_step = -1
        self.update_content()

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(id="content", markup=False)

    def on_mount(self) -> None:
        self.update_content()

    @property
    def n_steps(self) -> int:
        return len(self.trajectory["trajectory"])

    def _show_step_yaml(self, item: dict) -> None:
        """Show full yaml of trajectory item"""
        content_str = _yaml_serialization_with_linebreaks(
            _move_items_top(item, ["thought", "action", "observation", "response", "execution_time"])
        )
        syntax = Syntax(content_str, "yaml", theme="monokai", word_wrap=True)
        content = self.query_one("#content")
        content.update(syntax)  # type: ignore
        self.app.sub_title = f"{self.title} - Step {self.i_step + 1}/{self.n_steps} - Full View"

    def _show_step_simple(self, item: dict) -> None:
        # Simplified view - show action and observation as plain text
        thought = item.get("thought", "")
        action = item.get("action", "")
        observation = item.get("observation", "")

        content_str = f"THOUGHT:\n{thought}\n\nACTION:\n{action}\n\nOBSERVATION:\n{observation}"
        content = self.query_one("#content")
        content.update(content_str)  # type: ignore

        self.app.sub_title = f"{self.title} - Step {self.i_step + 1}/{self.n_steps} - Simple View"

    def _show_info(self):
        info = copy.deepcopy(self.trajectory["info"])
        info["result"] = self.overview_stats["result"]
        info["gold_patch"] = self.gold_patch
        info = _move_items_top(info, ["result", "exit_status", "model_stats", "submission", "gold_patch"])
        syntax = Syntax(_yaml_serialization_with_linebreaks(info), "yaml", theme="monokai", word_wrap=True)
        content = self.query_one("#content")
        content.update(syntax)  # type: ignore
        next_help = "Press l to see step 1" if self.i_step < 0 else f"Press h to see step {self.n_steps}"
        self.app.sub_title = f"{self.title} - Info ({next_help})"

    def update_content(self) -> None:
        print(self.i_step)
        if self.i_step < 0 or self.i_step >= self.n_steps:
            return self._show_info()

        item = self.trajectory["trajectory"][self.i_step]

        if self.show_full:
            return self._show_step_yaml(item)

        return self._show_step_simple(item)

    def action_next_item(self) -> None:
        if self.i_step < self.n_steps:
            self.i_step += 1
            self.scroll_top()
            self.update_content()

    def action_previous_item(self) -> None:
        if self.i_step > -1:
            self.i_step -= 1
            self.scroll_top()
            self.update_content()

    def action_toggle_view(self) -> None:
        self.show_full = not self.show_full
        self.update_content()

    def action_first_item(self) -> None:
        self.i_step = 0
        self.update_content()

    def action_last_item(self) -> None:
        self.i_step = self.n_steps - 1
        self.update_content()

    def scroll_top(self) -> None:
        """Resets scrolling viewport"""
        vs = self.query_one(VerticalScroll)
        vs.scroll_home(animate=False)

    def action_scroll_down(self) -> None:
        vs = self.query_one(VerticalScroll)
        vs.scroll_to(y=vs.scroll_target_y + 15)

    def action_scroll_up(self) -> None:
        vs = self.query_one(VerticalScroll)
        vs.scroll_to(y=vs.scroll_target_y - 15)


class TrajectorySelectorScreen(ModalScreen[int]):
    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel"),
    ]

    def __init__(self, paths: list[Path], current_index: int, overview_stats: dict):
        super().__init__()
        self.paths = paths
        self.current_index = current_index
        self.overview_stats = overview_stats
        self.all_items = []  # Store all items for filtering
        self.filtered_indices = []

    def _get_list_item_texts(self, paths: list[Path]) -> list[str]:
        """Remove the common prefix from a list of paths."""
        prefix = os.path.commonpath([str(p) for p in paths])
        labels = []
        for p in paths:
            ostat = self.overview_stats[p.stem]
            ostat_str = f"{ostat['exit_status']} {ostat['result']} ${ostat['cost']:.2f} {ostat['api_calls']} calls"
            shortened_path = str(p)[len(prefix) :].lstrip("/\\")
            if Path(shortened_path).stem == Path(shortened_path).parent.name:
                # We have the instance ID twice (in the folder and the traj)
                shortened_path = Path(shortened_path).stem
            labels.append(f"{shortened_path} - {ostat_str}")

        return labels

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(
                "Press <TAB> to switch between search and list. Use <ARROW KEY>/<ENTER> to select.",
                id="title",
                markup=False,
            )
            yield Input(placeholder="Type to filter (auto-select if only one item remains)...", id="filter-input")
            yield ListView(
                *[ListItem(Static(p, markup=False)) for p in self._get_list_item_texts(self.paths)],
                id="trajectory-list",
                initial_index=self.current_index,
            )
        # Store all items for later filtering
        self.all_items = self._get_list_item_texts(self.paths)
        self.filtered_indices = list(range(len(self.all_items)))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter list items based on input"""
        filter_text = event.value.lower()
        list_view = self.query_one("#trajectory-list", ListView)

        # Filter items and keep track of original indices
        self.filtered_indices = [i for i, item in enumerate(self.all_items) if filter_text in item.lower()]
        filtered_items = [self.all_items[i] for i in self.filtered_indices]

        if len(filtered_items) == 1:
            # Find the index of the filtered item in the original list
            selected_index = self.all_items.index(filtered_items[0])
            self.dismiss(selected_index)
            return

        # Update ListView with filtered items
        list_view.clear()
        for item in filtered_items:
            list_view.append(ListItem(Static(item, markup=False)))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Map the filtered index back to the original index
        original_index = self.filtered_indices[event.list_view.index]
        print(f"Selected index: {original_index}")
        self.dismiss(original_index)

    CSS = """
    #dialog {
        background: $surface;
        padding: 1;
        border: thick $primary;
        width: 100%;
        height: 100%;
    }

    #title {
        text-align: center;
        padding: 1;
    }

    #filter-input {
        dock: top;
        margin: 1 0;
    }

    ListView {
        height: 100%;
        border: solid $primary;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: $accent;
    }
    """


class FileViewerScreen(ModalScreen):
    BINDINGS = [
        Binding("q,escape", "dismiss", "Back"),
        Binding("j,down", "scroll_down", "Scroll down"),
        Binding("k,up", "scroll_up", "Scroll up"),
        Binding("e", "open_editor", "Open in $EDITOR"),
    ]

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            text = self.path.read_text()
            truncated = False
            if len(text) > 10_000:
                # More than ~1000 lines
                self.app.notify(
                    "File is too large to display. Showing first 10k chars. Use e to open in editor.",
                    severity="warning",
                )
                text = text[:10_000]
                truncated = True
            if self.path.exists():
                if self.path.suffix == ".traj" and not truncated:
                    # Syntax highlighting breaks if we truncate
                    content_str = _yaml_serialization_with_linebreaks(json.loads(text))
                    syntax = Syntax(content_str, "yaml", theme="monokai", word_wrap=True)
                    yield Static(syntax, markup=False)
                else:
                    yield Static(text, markup=False)
            else:
                yield Static(f"No file found at {self.path}", markup=False)

    def action_scroll_down(self) -> None:
        vs = self.query_one(VerticalScroll)
        vs.scroll_to(y=vs.scroll_target_y + 15)

    def action_scroll_up(self) -> None:
        vs = self.query_one(VerticalScroll)
        vs.scroll_to(y=vs.scroll_target_y - 15)

    def action_open_editor(self) -> None:
        editor = os.environ.get("EDITOR")
        if not editor:
            self.app.notify("No editor found in $EDITOR environment variable, cannot perform action", severity="error")
            return
        try:
            subprocess.run([editor, str(self.path)], check=True)
        except subprocess.CalledProcessError:
            pass

    CSS = """
    ScrollableContainer {
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 1;
        border: thick $primary;
    }
    """


class TrajectoryInspectorApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("L", "next_traj", "Traj++"),
        Binding("H", "previous_traj", "Traj--"),
        Binding("t", "show_traj_selector", "Select Traj"),
        Binding("o", "show_log", "View Log"),
        Binding("r", "show_full", "Show full"),
    ]

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
    }

    #viewer {
        width: 100%;
        height: 100%;
    }

    ScrollView {
        width: 100%;
        height: 100%;
        border: solid green;
    }
    """

    def __init__(self, input_path: str | Path, data_path: Path | None = None):
        super().__init__()
        self.input_path = Path(input_path)
        if not self.input_path.exists():
            msg = f"{self.input_path} doesn't exist"
            raise FileNotFoundError(msg)
        self.available_traj_paths = self._get_available_trajs()
        if not self.available_traj_paths:
            msg = "No trajectory *.traj files available"
            raise ValueError(msg)
        self.trajectory_index = 0
        self.overview_stats = collections.defaultdict(dict)
        self._build_overview_stats()
        self._data = load_file(data_path)

    def get_gold_patch(self, instance_id: str) -> str | None:
        if self._data is None:
            return None
        return self._data.get(instance_id, {}).get("patch", None)

    def _build_overview_stats(self):
        results_path = self.input_path / "results.json"
        results = None
        if results_path.exists():
            results = json.loads(results_path.read_text())
        for traj in self.available_traj_paths:
            instance_id = traj.stem
            if results is None:
                result = "❓"
            elif instance_id in results["resolved_ids"]:
                result = "✅"
            else:
                result = "❌"
            self.overview_stats[instance_id]["result"] = result

        def _get_info(traj: Path) -> tuple[str, dict]:
            traj_info = json.loads(traj.read_text()).get("info", {})
            return traj.stem, traj_info

        with ThreadPoolExecutor() as executor:
            # Map returns results in the same order as inputs
            all_infos = executor.map(_get_info, self.available_traj_paths)

        for instance_id, info in all_infos:
            self.overview_stats[instance_id]["info"] = info
            self.overview_stats[instance_id]["exit_status"] = info.get("exit_status", "?")
            self.overview_stats[instance_id]["api_calls"] = info.get("model_stats", {}).get("api_calls", 0)
            self.overview_stats[instance_id]["cost"] = info.get("model_stats", {}).get("instance_cost", 0)

    def _get_viewer_title(self, index: int) -> str:
        instance_id = self.available_traj_paths[index].stem
        if len(instance_id) > 20:
            instance_id = "..." + instance_id[-17:]
        return f"Traj {index + 1}/{len(self.available_traj_paths)} - {instance_id}"

    def _load_traj(self):
        instance_id = self.available_traj_paths[self.trajectory_index].stem
        traj_viewer = self.query_one(TrajectoryViewer)
        traj_viewer.load_trajectory(
            self.available_traj_paths[self.trajectory_index],
            self._get_viewer_title(self.trajectory_index),
            self.overview_stats[instance_id],
            gold_patch=self.get_gold_patch(instance_id),
        )

    def _get_available_trajs(self) -> list[Path]:
        if self.input_path.is_file():
            return [self.input_path]
        elif self.input_path.is_dir():
            return sorted(self.input_path.rglob("*.traj"))
        raise ValueError

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield TrajectoryViewer(
                self.available_traj_paths[self.trajectory_index],
                self._get_viewer_title(self.trajectory_index),
                self.overview_stats[self.available_traj_paths[self.trajectory_index].stem],
            )
        yield Footer()

    def action_next_traj(self):
        self.trajectory_index = (self.trajectory_index + 1) % len(self.available_traj_paths)
        self._load_traj()

    def action_previous_traj(self):
        self.trajectory_index = (self.trajectory_index - 1) % len(self.available_traj_paths)
        self._load_traj()

    async def action_show_traj_selector(self) -> None:
        selector = TrajectorySelectorScreen(self.available_traj_paths, self.trajectory_index, self.overview_stats)

        def handler(index: int | None):
            if index is not None:
                self.trajectory_index = index
                self._load_traj()

        await self.push_screen(selector, handler)  # This returns when the modal is dismissed

    async def action_show_log(self) -> None:
        current_traj = self.available_traj_paths[self.trajectory_index]
        log_path = current_traj.with_suffix(".debug.log")
        log_viewer = FileViewerScreen(log_path)
        await self.push_screen(log_viewer)

    async def action_show_full(self) -> None:
        """Show full yaml of trajectory file"""
        current_traj = self.available_traj_paths[self.trajectory_index]
        viewer = FileViewerScreen(current_traj)
        await self.push_screen(viewer)


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Inspect trajectory JSON files")
    parser.add_argument(
        "trajectory_path",
        help="Path to the trajectory JSON file or directory containing trajectories",
        default=os.getcwd(),
        nargs="?",
    )
    parser.add_argument("-d", "--data_path", type=Path, help="Path to the data file to load gold patches from")
    parsed_args = parser.parse_args(args)

    app = TrajectoryInspectorApp(parsed_args.trajectory_path)
    app.run()


if __name__ == "__main__":
    main()
