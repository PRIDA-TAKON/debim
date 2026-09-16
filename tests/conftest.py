"""
Pytest configuration and shared fixtures
"""

import pytest
from pathlib import Path

@pytest.fixture
def sample_project_path() -> Path:
    return Path(__file__).parent.parent / "examples" / "townhouse" / "project.yaml"

@pytest.fixture
def sample_prices_path() -> Path:
    return Path(__file__).parent.parent / "examples" / "townhouse" / "prices.json"
