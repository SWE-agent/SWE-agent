# Multimodal Support

SWE-agent supports multimodal AI models that can process both text and images. This enables the agent to work with visual context from GitHub issues, such as screenshots, diagrams, and UI mockups.

## Overview

The multimodal implementation automatically:

- **Detects multimodal instances** from SWE-bench Multimodal datasets
- **Downloads images** from GitHub issue URLs
- **Converts to base64 markdown** format for AI model consumption
- **Handles errors gracefully** with fallback to text-only processing

## Supported Image Categories

Currently, SWE-agent processes images from the `problem_statement` category, which includes:

- Screenshots showing bugs or issues
- UI mockups and design specifications
- Diagrams explaining the problem
- Error screenshots and visual evidence

!!! note "Design Choice"
    Only `problem_statement` images are processed to provide essential visual context for understanding the task, while preserving agent autonomy in determining solution approaches. Images from `patch` and `test_patch` categories may contain solution hints and are not processed.

## Configuration

### Basic Multimodal Setup

Use the pre-configured multimodal setup:

```bash
sweagent run-batch \
    --config config/default_mm_with_images.yaml \
    --instances.type swe_bench \
    --instances.subset multimodal \
    --instances.split dev
```

### Disabling Image Processing

You can disable image processing globally:

```yaml
# config/your_config.yaml
agent:
  templates:
    disable_image_processing: true
```

Or for specific instances:

```python
from sweagent.agent.problem_statement import SWEBenchMultimodalProblemStatement

problem_statement = SWEBenchMultimodalProblemStatement(
    text="Fix the rendering issue",
    issue_images=["https://example.com/screenshot.png"],
    disable_image_processing=True  # Skip image processing
)
```

## Supported Models

Multimodal support works with any vision-capable models, including:

- **Claude Sonnet 4**
- **o3** and **o4-mini**
- **Gemini 2.5** models

Example model configuration:

```yaml
# model_configs/claude-sonnet-4-20250514_mm.yaml
model:
  name: claude-sonnet-4-20250514
  # Vision capabilities automatically detected
```

## Image Processing Details

### Supported Formats
- PNG, JPEG, WebP images
- Maximum size: 10MB per image


## Example Usage

### Automatic Detection

When loading SWE-bench instances, multimodal support is automatic:

```json
{
    "instance_id": "example__repo-123",
    "problem_statement": "Fix the chart rendering bug...",
    "image_assets": {
        "problem_statement": ["http://example.com/chart.png"]
    }
}
```

### Direct Usage

```python
from sweagent.agent.problem_statement import SWEBenchMultimodalProblemStatement

problem_statement = SWEBenchMultimodalProblemStatement(
    text="Fix the rendering issue shown in the screenshots",
    issue_images=[
        "https://example.com/before.png",
        "https://example.com/after.png"
    ]
)

# This downloads images and converts them to base64 markdown
processed_text = problem_statement.get_problem_statement()
```

## Configuration Options

In order to enable multimodal processing, you need to update the following configuration options:

### History Processing

Enable image parsing in your configuration:

```yaml
agent:
  history_processors:
    - type: image_parsing  # Parse base64 encoded images in observations
```

### Tool Bundles

Include image and browser tools for visual tasks:

```yaml
agent:
  tools:
    bundles:
      - path: tools/image_tools  # includes open_image tool to let models open image files
      - path: tools/web_browser  # includes 17 browser automation tools (click_mouse, open_site, etc.)
```

The `web_browser` bundle provides tools for:
- Opening websites (`open_site`)
- Taking screenshots (`screenshot_site`)
- Interacting with web pages (`click_mouse`, `type_text`, `scroll_on_page`)
- Executing JavaScript (`execute_script_on_page`)
- And more - see the [configuration guide](../config/config.md#web-browser-tools) for the full list

### Templates Configuration

We've enabled multimodal processing when `--instances.type=swe-bench --instances.subset=multimodal` are set.

To disable this behavior, you must set `--templates.disable_image_processing=true`.