from __future__ import annotations

import copy
import re
from abc import abstractmethod
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sweagent.types import History, HistoryItem


class AbstractHistoryProcessor(Protocol):
    @abstractmethod
    def __call__(self, history: History) -> History:
        raise NotImplementedError


# Utility functions
# -----------------


def _get_content_stats(entry: HistoryItem) -> tuple[int, int]:
    if isinstance(entry["content"], str):
        return len(entry["content"].splitlines()), 0
    n_text_lines = sum(len(item["text"].splitlines()) for item in entry["content"] if item.get("type") == "text")
    n_images = sum(1 for item in entry["content"] if item.get("type") == "image_url")
    return n_text_lines, n_images


def _get_content_text(entry: HistoryItem) -> str:
    if isinstance(entry["content"], str):
        return entry["content"]
    assert len(entry["content"]) == 1, "Expected single message in content"
    return entry["content"][0]["text"]


def _set_content_text(entry: HistoryItem, text: str) -> None:
    if isinstance(entry["content"], str):
        entry["content"] = text
    else:
        assert len(entry["content"]) == 1, "Expected single message in content"
        entry["content"][0]["text"] = text


def _clear_cache_control(entry: HistoryItem) -> None:
    if isinstance(entry["content"], list):
        for item in entry["content"]:
            item.pop("cache_control", None)
    entry.pop("cache_control", None)


def _set_cache_control(entry: HistoryItem) -> None:
    if not isinstance(entry["content"], list):
        entry["content"] = [  # type: ignore
            {
                "type": "text",
                "text": _get_content_text(entry),
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        entry["content"][0]["cache_control"] = {"type": "ephemeral"}
    if entry["role"] == "tool":
        # Workaround for weird bug
        entry["content"][0].pop("cache_control", None)
        entry["cache_control"] = {"type": "ephemeral"}


# History processors
# ------------------


class DefaultHistoryProcessor(BaseModel):
    type: Literal["default"] = "default"
    """Do not change. Used for (de)serialization."""

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        return history


class LastNObservations(BaseModel):
    """Elide all but the last n observations or remove tagged observations.

    This is our most classic history processor, used in the original paper
    to elide but the last 5 observations.
    Elided observations are replaced by "Old environment output: (n lines omitted)".

    Typical configuration:

    ```yaml
    agent:
      history_processors:
        - type: last_n_observations
          n: 5
    ```

    as for example in use in the SWE-agent 0.7 config at
    https://github.com/SWE-agent/SWE-agent/blob/main/config/sweagent_0_7/07.yaml

    For most use cases, you only need to set `n`.

    Note that using this history processor will break prompt caching (as the
    history of every query will change every time due to the elided observations).
    There are some workarounds possible with the `polling` parameter.

    However, most SotA models can now fit a lot of context, so generally this
    history processor is not always needed anymore.
    """

    n: int
    """Number of observations to keep."""

    polling: int = 1
    """How many steps to keep between updating the number of observations to keep.
    This is useful for caching, as we want to remove more and more messages, but every
    time we change the history, we need to cache everything again.
    Effectively, we will now keep between `n` and `n+polling` observations.
    """

    always_remove_output_for_tags: set[str] = {"remove_output"}
    """Any observation with a `tags` field containing one of these strings will be elided,
    even if it is one of the last n observations.
    """

    always_keep_output_for_tags: set[str] = {"keep_output"}
    """Any observation with a `tags` field containing one of these strings will be kept,
    even if it is not one of the last n observations.
    """

    type: Literal["last_n_observations"] = "last_n_observations"
    """Do not change. Used for (de)serialization."""

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    @field_validator("n")
    def validate_n(cls, n: int) -> int:
        if n <= 0:
            msg = "n must be a positive integer"
            raise ValueError(msg)
        return n

    def _get_omit_indices(self, history: History) -> list[int]:
        observation_indices = [
            idx
            for idx, entry in enumerate(history)
            if entry.get("message_type") == "observation" and not entry.get("is_demo", False)
        ]
        last_removed_idx = max(0, (len(observation_indices) // self.polling) * self.polling - self.n)
        # Note: We never remove the first observation, as it is the instance template
        return observation_indices[1:last_removed_idx]

    def __call__(self, history: History) -> History:
        new_history = []
        omit_content_idxs = self._get_omit_indices(history)
        for idx, entry in enumerate(history):
            tags = set(entry.get("tags", []))
            if ((idx not in omit_content_idxs) or (tags & self.always_keep_output_for_tags)) and not (
                tags & self.always_remove_output_for_tags
            ):
                new_history.append(entry)
            else:
                data = entry.copy()
                assert data.get("message_type") == "observation", (
                    f"Expected observation for dropped entry, got: {data.get('message_type')}"
                )
                num_text_lines, num_images = _get_content_stats(data)
                data["content"] = f"Old environment output: ({num_text_lines} lines omitted)"
                if num_images > 0:
                    data["content"] += f" ({num_images} images omitted)"
                new_history.append(data)
        return new_history


class TagToolCallObservations(BaseModel):
    """Adds tags to history items for specific tool calls."""

    type: Literal["tag_tool_call_observations"] = "tag_tool_call_observations"
    """Do not change. Used for (de)serialization."""

    tags: set[str] = {"keep_output"}
    """Add the following tag to all observations matching the search criteria."""

    function_names: set[str] = set()
    """Only consider observations made by tools with these names."""

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    def _add_tags(self, entry: HistoryItem) -> None:
        tags = set(entry.get("tags", []))
        tags.update(self.tags)
        entry["tags"] = list(tags)

    def _should_add_tags(self, entry: HistoryItem) -> bool:
        if entry.get("message_type") != "action":
            return False
        function_calls = entry.get("tool_calls", [])
        if not function_calls:
            return False
        function_names = {call["function"]["name"] for call in function_calls}  # type: ignore
        return bool(self.function_names & function_names)

    def __call__(self, history: History) -> History:
        for entry in history:
            if self._should_add_tags(entry):
                self._add_tags(entry)
        return history


class ClosedWindowHistoryProcessor(BaseModel):
    """For each value in history, keep track of which windows have been shown.
    We want to mark windows that should stay open (they're the last window for a particular file)
    Then we'll replace all other windows with a simple summary of the window (i.e. number of lines)
    """

    type: Literal["closed_window"] = "closed_window"
    """Do not change. Used for (de)serialization."""

    _pattern = re.compile(r"^(\d+)\:.*?(\n|$)", re.MULTILINE)
    _file_pattern = re.compile(r"\[File:\s+(.*)\s+\(\d+\s+lines\ total\)\]")

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history):
        new_history = list()
        windows = set()
        for entry in reversed(history):
            data = entry.copy()
            if data["role"] != "user":
                new_history.append(entry)
                continue
            if data.get("is_demo", False):
                new_history.append(entry)
                continue
            matches = list(self._pattern.finditer(entry["content"]))
            if len(matches) >= 1:
                file_match = self._file_pattern.search(entry["content"])
                if file_match:
                    file = file_match.group(1)
                else:
                    continue
                if file in windows:
                    start = matches[0].start()
                    end = matches[-1].end()
                    data["content"] = (
                        entry["content"][:start]
                        + f"Outdated window with {len(matches)} lines omitted...\n"
                        + entry["content"][end:]
                    )
                windows.add(file)
            new_history.append(data)
        return list(reversed(new_history))


class CacheControlHistoryProcessor(BaseModel):
    """This history processor adds manual cache control marks to the history.
    Use this when running with anthropic claude.
    """

    type: Literal["cache_control"] = "cache_control"
    """Do not change. Used for (de)serialization."""

    last_n_messages: int = 2
    """Add cache control to the last n user messages (and clear it for anything else).
    In most cases this should be set to 2 (caching for multi-turn conversations).
    When resampling and running concurrent instances, you want to set it to 1.
    If set to <= 0, any set cache control will be removed from all messages.
    """

    last_n_messages_offset: int = 0
    """E.g., set to 1 to start cache control after the second to last user message.
    This can be useful in rare cases, when you want to modify the last message after
    we've got the completion and you want to avoid cache mismatch.
    """

    tagged_roles: list[str] = ["user", "tool"]
    """Only add cache control to messages with these roles."""

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        new_history = []
        n_tagged = 0
        for i_entry, entry in enumerate(reversed(history)):
            # Clear cache control from previous messages
            _clear_cache_control(entry)
            if (
                n_tagged < self.last_n_messages
                and entry["role"] in self.tagged_roles
                and i_entry >= self.last_n_messages_offset
            ):
                _set_cache_control(entry)
                n_tagged += 1
            new_history.append(entry)
        return list(reversed(new_history))


class RemoveRegex(BaseModel):
    """This history processor can remove arbitrary content from history items"""

    remove: list[str] = ["<diff>.*</diff>"]
    """Regex patterns to remove from history items"""

    keep_last: int = 0
    """Keep the last n history items unchanged"""

    type: Literal["remove_regex"] = "remove_regex"
    """Do not change. Used for (de)serialization."""

    # pydantic config
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        new_history = []
        for i_entry, entry in enumerate(reversed(history)):
            entry = copy.deepcopy(entry)
            if i_entry < self.keep_last:
                new_history.append(entry)
            else:
                if isinstance(entry["content"], list):
                    for item in entry["content"]:
                        if item["type"] == "text":
                            for pattern in self.remove:
                                item["text"] = re.sub(pattern, "", item["text"], flags=re.DOTALL)
                else:
                    assert isinstance(entry["content"], str), "Expected string content"
                    for pattern in self.remove:
                        entry["content"] = re.sub(pattern, "", entry["content"], flags=re.DOTALL)
                new_history.append(entry)
        return list(reversed(new_history))


class ImageParsingHistoryProcessor(BaseModel):
    """Parse embedded base64 images from markdown and convert to multi-modal format."""

    type: Literal["image_parsing"] = "image_parsing"
    allowed_mime_types: set[str] = {"image/png", "image/jpeg", "image/webp"}

    _pattern = re.compile(r"(!\[([^\]]*)\]\(data:)([^;]+);base64,([^)]+)(\))")
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        return [self._process_entry(entry) for entry in history]

    def _process_entry(self, entry: HistoryItem) -> HistoryItem:
        if entry.get("role") not in ["user", "tool"]:
            return entry
        entry = copy.deepcopy(entry)
        content = _get_content_text(entry)
        segments = self._parse_images(content)
        if any(seg["type"] == "image_url" for seg in segments):
            entry["content"] = segments
        return entry

    def _parse_images(self, content: str) -> list[dict]:
        segments = []
        last_end = 0
        has_images = False

        def add_text(text: str) -> None:
            """Add text to the last segment if it's text, otherwise create new text segment."""
            if text and segments and segments[-1]["type"] == "text":
                segments[-1]["text"] += text
            elif text:
                segments.append({"type": "text", "text": text})

        for match in self._pattern.finditer(content):
            markdown_prefix, alt_text, mime_type, base64_data, markdown_suffix = match.groups()
            add_text(content[last_end : match.start()])
            mime_type = "image/jpeg" if mime_type == "image/jpg" else mime_type
            if mime_type in self.allowed_mime_types:
                add_text(markdown_prefix)
                segments.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}})
                add_text(markdown_suffix)
                has_images = True
            else:
                add_text(match.group(0))
            last_end = match.end()
        add_text(content[last_end:])
        return segments if has_images else [{"type": "text", "text": content}]


HistoryProcessor = Annotated[
    DefaultHistoryProcessor
    | LastNObservations
    | ClosedWindowHistoryProcessor
    | TagToolCallObservations
    | CacheControlHistoryProcessor
    | RemoveRegex
    | ImageParsingHistoryProcessor,
    Field(discriminator="type"),
]
