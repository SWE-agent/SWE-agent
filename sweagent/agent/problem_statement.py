import base64
import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from sweagent.utils.github import _get_problem_statement_from_github_issue, _parse_gh_issue_url
from sweagent.utils.log import get_logger

logger = get_logger("swea-config", emoji="🔧")

# Constants for image processing
VALID_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",  # Some servers return jpg instead of jpeg
    "image/webp",
}


class ProblemStatement(Protocol):
    """A problem statement for a task. Any class that implements this protocol
    can be used as a problem statement.
    """

    id: str

    def get_problem_statement(self) -> str: ...

    def get_problem_statement_for_env(self) -> str:
        """Used for setting environment variables in the container.

        By default, this is the same as get_problem_statement().
        """
        return self.get_problem_statement()

    def get_extra_fields(self) -> dict[str, Any]: ...


class _BuiltinProblemStatementBase(BaseModel):
    """A base class for the builtin problem statements to avoid typing much"""

    def get_problem_statement(self) -> str: ...

    def get_problem_statement_for_env(self) -> str:
        return self.get_problem_statement()

    def get_extra_fields(self) -> dict[str, Any]:
        return {}


class EmptyProblemStatement(_BuiltinProblemStatementBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["empty"] = "empty"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    def get_problem_statement(self) -> str:
        return ""


class TextProblemStatement(_BuiltinProblemStatementBase):
    text: str

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["text"] = "text"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement id to hash of text")
            self.id = hashlib.sha256(self.text.encode()).hexdigest()[:6]

    def get_problem_statement(self) -> str:
        return self.text

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields

    def __repr__(self) -> str:
        return f"TextProblemStatement(id={self.id}, text={self.text[:30]}...)"

    def __str__(self) -> str:
        return f"id={self.id}, text={self.text[:30]}..."


class FileProblemStatement(_BuiltinProblemStatementBase):
    path: Path

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["text_file"] = "text_file"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement id to hash of file contents (path: %s)", self.path)
            self.id = hashlib.sha256(self.get_problem_statement().encode()).hexdigest()[:6]

    def get_problem_statement(self) -> str:
        return self.path.read_text()

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields


class GithubIssue(_BuiltinProblemStatementBase):
    github_url: str

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["github"] = "github"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement based on github issue url")
            owner, repo, issue_number = _parse_gh_issue_url(self.github_url)
            self.id = f"{owner}__{repo}-i{issue_number}"

    def get_problem_statement(self) -> str:
        owner, repo, issue_number = _parse_gh_issue_url(self.github_url)
        return _get_problem_statement_from_github_issue(owner, repo, issue_number, token=os.getenv("GITHUB_TOKEN"))

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields


class SWEBenchMultimodalProblemStatement(_BuiltinProblemStatementBase):
    text: str

    issue_images: list[str] = Field(default_factory=list)
    """List of image asset URLs.
    """

    disable_image_processing: bool = False
    """If True, skip image downloading and processing, treating this as a text-only problem statement.
    """

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["swe_bench_multimodal"] = "swe_bench_multimodal"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    _cached_problem_statement: str | None = PrivateAttr(default=None)

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement id to hash of text")
            self.id = hashlib.sha256(self.text.encode()).hexdigest()[:6]

    def get_problem_statement_for_env(self) -> str:
        """Return the problem statement without images.

        Images are not supported in the environment.
        """
        return self.text

    def get_problem_statement(self) -> str:
        if self.disable_image_processing:
            logger.info("Image processing disabled, returning text-only problem statement")
            return self.text

        if self._cached_problem_statement is not None:
            return self._cached_problem_statement

        processed_text = self.text
        for link in self.issue_images:
            try:
                image_markdown = self._download_and_convert_image(link)
                if image_markdown:
                    processed_text += f"\n\n{image_markdown}"
            except Exception as e:
                logger.warning(f"Failed to process image from {link}: {e}")

        # cache to avoid re-processing images
        self._cached_problem_statement = processed_text
        return processed_text

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields

    def _download_and_convert_image(self, url: str) -> str | None:
        """Download an image from URL and convert it to base64 markdown format.

        Args:
            url: The URL of the image to download

        Returns:
            Base64 markdown string if successful, None if failed

        Raises:
            Various exceptions for network/processing errors
        """
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                logger.warning(f"Invalid URL format: {url}")
                return None
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.133 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if content_type == "image/jpg":
                content_type = "image/jpeg"
            if content_type not in VALID_IMAGE_MIME_TYPES:
                logger.warning(f"Unsupported image MIME type '{content_type}' for URL: {url}. Not encoding image.")
                return None
            max_size = 10 * 1024 * 1024  # 10MB
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_size:
                logger.warning(f"Image too large ({content_length} bytes) for URL: {url}")
                return None
            image_data = b""
            for chunk in response.iter_content(chunk_size=8192):
                image_data += chunk
                if len(image_data) > max_size:
                    logger.warning(f"Image too large (>{max_size} bytes) for URL: {url}")
                    return None
            if not image_data:
                logger.warning(f"Empty image data for URL: {url}")
                return None
            b64_data = base64.b64encode(image_data).decode("ascii")
            markdown = f"![{url}](data:{content_type};base64,{b64_data})"
            logger.info(f"Successfully processed image from {url} ({len(image_data)} bytes, {content_type})")
            return markdown

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout downloading image from {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error downloading image from {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error processing image from {url}: {e}")
            return None

    def __repr__(self) -> str:
        n_images = len(self.issue_images)
        return f"SWEBenchMultimodalProblemStatement(id={self.id}, text={self.text[:30]}..., images={n_images})"

    def __str__(self) -> str:
        n_images = len(self.issue_images)
        return f"id={self.id}, text={self.text[:30]}..., images={n_images}"


ProblemStatementConfig = (
    TextProblemStatement
    | SWEBenchMultimodalProblemStatement
    | GithubIssue
    | EmptyProblemStatement
    | FileProblemStatement
)


def problem_statement_from_simplified_input(
    *, input: str, type: Literal["text", "text_file", "github_issue", "swe_bench_multimodal"]
) -> ProblemStatementConfig:
    """Get a problem statement from an `input` string and a `type`.

    Args:
        input: Url/path/text
        type: The type of problem statement
    """
    if type == "text":
        return TextProblemStatement(text=input)
    elif type == "text_file":
        return FileProblemStatement(path=Path(input))
    elif type == "github_issue":
        return GithubIssue(github_url=input)
    elif type == "swe_bench_multimodal":
        return SWEBenchMultimodalProblemStatement(text=input)
    else:
        msg = f"Unknown problem statement type: {type}"
        raise ValueError(msg)
