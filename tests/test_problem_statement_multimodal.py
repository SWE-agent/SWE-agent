from unittest.mock import Mock, patch

import requests

from sweagent.agent.problem_statement import SWEBenchMultimodalProblemStatement


class TestSWEBenchMultimodalProblemStatement:
    example_image_url = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Candide1759.jpg/330px-Candide1759.jpg"
    )

    def test_initialization(self):
        """Test basic initialization of multimodal problem statement."""
        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=[self.example_image_url], id="test_id"
        )
        assert problem_statement.text == "Test problem statement"
        assert problem_statement.issue_images == [self.example_image_url]
        assert problem_statement.id == "test_id"
        assert problem_statement.type == "swe_bench_multimodal"

    def test_get_problem_statement_no_images(self):
        """Test get_problem_statement when no images are present."""
        problem_statement = SWEBenchMultimodalProblemStatement(text="Test problem statement", issue_images=[])
        result = problem_statement.get_problem_statement()
        assert result == "Test problem statement"

    @patch("requests.get")
    def test_get_problem_statement_with_valid_image(self, mock_get):
        """Test get_problem_statement with a valid image that gets processed."""
        # mock successful HTTP response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "image/png"}
        mock_response.iter_content.return_value = [b"fake_image_data"]
        mock_get.return_value = mock_response
        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=[self.example_image_url]
        )
        result = problem_statement.get_problem_statement()
        # should contain original text plus the base64 image
        assert "Test problem statement" in result
        assert f"![{self.example_image_url}](data:image/png;base64," in result

    @patch("requests.get")
    def test_get_problem_statement_with_network_error(self, mock_get):
        """Test that network errors are handled gracefully with warnings."""
        # mock network error
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=[self.example_image_url]
        )
        result = problem_statement.get_problem_statement()
        assert result == "Test problem statement"

    @patch("requests.get")
    def test_get_problem_statement_with_invalid_mime_type(self, mock_get):
        """Test that invalid MIME types are handled gracefully."""
        # mock response with invalid MIME type
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_response
        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=["http://example.com/document.html"]
        )
        result = problem_statement.get_problem_statement()
        assert result == "Test problem statement"

    @patch("requests.get")
    def test_caching_behavior(self, mock_get):
        """Test that get_problem_statement caches results and doesn't re-download images."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "image/png"}
        mock_response.iter_content.return_value = [b"fake_image_data"]
        mock_get.return_value = mock_response
        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=[self.example_image_url]
        )
        result1 = problem_statement.get_problem_statement()
        assert mock_get.call_count == 1
        result2 = problem_statement.get_problem_statement()
        assert mock_get.call_count == 1  # should still be 1, not 2, because of caching
        assert result1 == result2
        assert "Test problem statement" in result1
        assert f"![{self.example_image_url}](data:image/png;base64," in result1

    def test_invalid_url_handling(self):
        """Test that invalid URLs are handled gracefully."""
        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=["not_a_url", "ftp://invalid_scheme.com/image.png"]
        )
        result = problem_statement.get_problem_statement()
        assert result == "Test problem statement"

    @patch("requests.get")
    def test_large_image_handling(self, mock_get):
        """Test that large images are rejected."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "image/png", "content-length": "20971520"}  # 20MB
        mock_get.return_value = mock_response

        problem_statement = SWEBenchMultimodalProblemStatement(
            text="Test problem statement", issue_images=["http://example.com/huge_image.png"]
        )

        result = problem_statement.get_problem_statement()
        assert result == "Test problem statement"
