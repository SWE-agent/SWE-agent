from collections.abc import Callable

from unidiff import PatchSet


class PatchFormatter:
    def __init__(
        self,
        patch: str,
        read_method: Callable[[str], str],
    ):
        """Given the final patch and access to the container that contains the repository,
        extract relevant lines from the modified file.

        Args:
            patch: The patch as a string.
            read_method: Callable with path to file (relative to repository root) as argument
                that returns the file content as a string.
        """
        self._patch = PatchSet(patch)
        self._patched_files: dict[str, str] = {}
        self._original_files: dict[str, str] = {}
        self._patch_applied = True
        self._read_file = read_method
        self._read_files(original=False)

    @staticmethod
    def _merge_intervals(starts: list[int], stops: list[int]) -> tuple[list[int], list[int]]:
        """Given two lists of integers, starts and stops, merges all overlapping intervals.

        For example `starts=[1, 5, 18]`, `stops=[10, 13, 20]`
        should return `starts=[1, 18]`, `stops=[13, 20]`
        """
        if not starts:
            assert not stops
            return [], []

        intervals = sorted(zip(starts, stops))
        merged = []
        for start, stop in intervals:
            if not merged or merged[-1][1] < start:
                # No overlap
                merged.append([start, stop])
            else:
                # Overlap
                merged[-1][1] = max(merged[-1][1], stop)
        # Unzip again
        merged_starts, merged_stops = zip(*merged)
        return list(merged_starts), list(merged_stops)

    def format_file(self, text: str, starts: list[int], stops: list[int], *, linenos: bool = True) -> str:
        """Reads file and returns string representation of the relevant lines.

        Args:
            path: The path to the file within the repo location
            starts: The starting line numbers of the relevant lines. The first line is line 1.
            stops: The stopping line numbers of the relevant lines. The stop is not inclusive.
                The first line is line 1.
            linenos: Whether to include line numbers
        """
        if not starts:
            assert not stops
            return ""

        assert len(starts) == len(stops)
        assert all(start >= 1 for start in starts)
        assert all(start < stop for start, stop in zip(starts, stops))
        starts, stops = self._merge_intervals(starts, stops)
        assert all(hunk1_start < hunk2_start for hunk1_start, hunk2_start in zip(starts, starts[1:]))
        out: list[str] = []
        if starts[0] > 1:
            # Count from 1
            out.append(f"[{starts[0] - 1} lines above omitted]")
        last_stop: int | None = None
        lines = text.splitlines()
        for start, stop in zip(starts, stops):
            assert start >= 1
            if last_stop is not None:
                n_omitted = start - last_stop
                # Check that we have non-overlapping hunks
                assert n_omitted >= 0
                if n_omitted:
                    out.append(f"\n[{n_omitted} lines omitted]\n")
            # Count from 1
            these_lines = lines[start - 1 : stop - 1]
            if linenos:
                out.append("\n".join([f"{i:6d}: {l}" for i, l in enumerate(these_lines, start=start)]))
            else:
                out.append("\n".join(these_lines))
            last_stop = stop
        if last_stop <= len(lines):
            # Stop is not inclusive
            omitted = len(lines) - last_stop + 1
            assert omitted > 0
            out.append(f"[{omitted} lines below omitted]")
        return "\n".join(out)

    def _get_hunk_lines(self, original: bool, *, context_length: int) -> dict[str, tuple[list[int], list[int]]]:
        """Get the starts and stops for all files in the patch.

        Args:
            original: Whether to read the original file or the patched file
            context_length: The number of lines to include above and below the hunk

        Returns:
            A dictionary with the file path as key and a tuple of lists of starts and stops as value.
        """
        out: dict[str, tuple[list[int], list[int]]] = {}
        for patch in self._patch:
            if not patch.is_modified_file:
                continue
            starts: list[int] = []
            stops: list[int] = []
            for hunk in patch:
                if original:
                    # 1 is the lowest line number
                    start = max(1, hunk.source_start - context_length)
                    stop = hunk.source_start + hunk.source_length + context_length
                else:
                    start = max(1, hunk.target_start - context_length)
                    stop = hunk.target_start + hunk.target_length + context_length
                starts.append(start)
                stops.append(stop)
            out[patch.path] = (starts, stops)
        return out

    def _read_files(self, original: bool) -> None:
        for patch in self._patch:
            path = patch.path
            if not patch.is_modified_file:
                continue
            if original:
                msg = "Original file reading not implemented"
                raise NotImplementedError(msg)
            else:
                assert self._patch_applied
                self._patched_files[path] = self._read_file(path)

    @staticmethod
    def concat_files_strings(files: dict[str, str]) -> str:
        """Concatenate multiple `read_files` outputs into a single string."""
        out = []
        for path, content in files.items():
            out.append(f"[File: {path}]\n{content}")
        return "\n\n".join(out)

    def get_files_str(self, *, original: bool, context_length: int | None = 50, linenos: bool = True) -> str:
        hunk_lines = self._get_hunk_lines(original=original, context_length=context_length)
        sources = self._original_files if original else self._patched_files
        return self.concat_files_strings(
            {path: self.format_file(text, *hunk_lines[path], linenos=linenos) for path, text in sources.items()}
        )
