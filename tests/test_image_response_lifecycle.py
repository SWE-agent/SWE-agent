from unittest.mock import Mock

import pytest
import requests

from sweagent.agent.problem_statement import SWEBenchMultimodalProblemStatement


@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "jpg",
        "empty",
        "mime",
        "declared_size",
        "invalid_length",
        "stream_size",
        "stream_error",
        "stream_timeout",
        "http_error",
    ],
)
def test_image_download_closes_streamed_response(monkeypatch, scenario):
    response = Mock()
    response.headers = {"content-type": "image/png"}
    response.iter_content.return_value = [b"image data"]
    if scenario == "jpg":
        response.headers["content-type"] = "image/jpg; charset=utf-8"
    elif scenario == "empty":
        response.iter_content.return_value = []
    elif scenario == "invalid_length":
        response.headers["content-length"] = "invalid"
    elif scenario == "stream_timeout":
        response.iter_content.side_effect = requests.exceptions.Timeout("stream stalled")
    elif scenario == "mime":
        response.headers["content-type"] = "text/html"
    elif scenario == "declared_size":
        response.headers["content-length"] = str(11 * 1024 * 1024)
    elif scenario == "stream_size":
        response.iter_content.return_value = [b"x" * (10 * 1024 * 1024 + 1)]
    elif scenario == "stream_error":
        response.iter_content.side_effect = requests.exceptions.ConnectionError("stream interrupted")
    elif scenario == "http_error":
        response.raise_for_status.side_effect = requests.exceptions.HTTPError("not found")
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: response)
    statement = SWEBenchMultimodalProblemStatement(text="problem")
    result = statement._download_and_convert_image("https://example.com/image.png")
    assert (result is not None) == (scenario in {"success", "jpg"})
    if scenario == "jpg":
        assert "data:image/jpeg;base64," in result
    response.close.assert_called_once_with()
