"""Tests for the logging system."""

import logging
import os
from unittest import TestCase, mock

from sweagent.utils.log import get_logger, set_default_levels


class TestLogging(TestCase):
    """Test the logging system."""

    def setUp(self):
        """Set up test environment."""
        # Clear any existing handlers
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_verbosity_levels(self):
        """Test that verbosity levels are properly set."""
        # Test default level
        logger = get_logger("test")
        assert logger.getEffectiveLevel() == logging.DEBUG

        # Test setting via function
        set_default_levels(stream_level="INFO")
        logger = get_logger("test2")
        assert logger.getEffectiveLevel() == logging.INFO

        # Test environment variable override
        with mock.patch.dict(os.environ, {"SWE_AGENT_LOG_STREAM_LEVEL": "ERROR"}):
            set_default_levels()  # Reset to use env vars
            logger = get_logger("test3")
            assert logger.getEffectiveLevel() == logging.ERROR

        # Test explicit level overrides env var
        with mock.patch.dict(os.environ, {"SWE_AGENT_LOG_STREAM_LEVEL": "ERROR"}):
            set_default_levels(stream_level="DEBUG")
            logger = get_logger("test4")
            assert logger.getEffectiveLevel() == logging.DEBUG
