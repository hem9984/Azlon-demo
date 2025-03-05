#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Pytest configuration file for the backend test suite
"""

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def env_setup():
    """Set up environment variables for testing."""
    with patch.dict(
        os.environ,
        {
            "MINIO_ENDPOINT": "localhost:9000",
            "MINIO_ROOT_USER": "minio_test_user",
            "MINIO_ROOT_PASSWORD": "minio_test_password",
            "MINIO_USE_SSL": "false",
            "E2B_API_KEY": "test_api_key",
            "BUCKET_NAME": "test-bucket",
        },
    ):
        yield
