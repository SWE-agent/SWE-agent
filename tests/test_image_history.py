import copy

import pytest

from sweagent.agent.history_processors import ImageParsingHistoryProcessor


@pytest.mark.parametrize("role", ["user", "tool"])
def test_image_parsing_preserves_existing_multimodal_content(role):
    image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,b2xk"}}
    history = [
        {
            "role": role,
            "content": [
                {"type": "text", "text": "existing image"},
                image,
                {"type": "text", "text": "new image ![new](data:image/png;base64,bmV3)"},
            ],
            "message_type": "observation",
        }
    ]
    original = copy.deepcopy(history)
    processor = ImageParsingHistoryProcessor()
    result = processor(history)
    images = [item for item in result[0]["content"] if item["type"] == "image_url"]
    assert images == [image, {"type": "image_url", "image_url": {"url": "data:image/png;base64,bmV3"}}]
    assert history == original
    assert processor(result) == result


def test_image_parsing_preserves_image_only_and_empty_content():
    processor = ImageParsingHistoryProcessor()
    for content in ([], [{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}]):
        history = [{"role": "user", "content": content, "message_type": "observation"}]
        assert processor(history) == history


@pytest.mark.parametrize("role", ["user", "tool"])
def test_image_parsing_converts_string_input_without_mutation(role):
    text = "before ![new](data:image/png;base64,bmV3) after"
    history = [{"role": role, "content": text, "message_type": "observation"}]
    processor = ImageParsingHistoryProcessor()
    result = processor(history)
    assert result[0]["content"] == [
        {"type": "text", "text": "before ![new](data:"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,bmV3"}},
        {"type": "text", "text": ") after"},
    ]
    assert history[0]["content"] == text
    assert processor(result) == result


@pytest.mark.parametrize("text", ["plain text", "", "![unsupported](data:image/gif;base64,bmV3)"])
def test_image_parsing_preserves_strings_without_supported_images(text):
    history = [{"role": "user", "content": text, "message_type": "observation"}]
    assert ImageParsingHistoryProcessor()(history) == history
