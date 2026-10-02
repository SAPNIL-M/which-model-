from pathlib import Path

import pytest

from app.config import load_config


def test_config_requires_key_for_live_model(tmp_path: Path):
    path = tmp_path / "models.yaml"
    path.write_text(
        """
models:
  - id: test
    display_name: Test
    kind: gemini
    provider_model_id: test-model
    api_key_env: TEST_KEY
    is_open: false
    license_type: closed
    live_enabled: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="TEST_KEY"):
        load_config(path, {})


def test_config_loads_with_key(tmp_path: Path):
    path = tmp_path / "models.yaml"
    path.write_text(
        """
models:
  - id: test
    display_name: Test
    kind: gemini
    provider_model_id: test-model
    api_key_env: TEST_KEY
    is_open: false
    license_type: closed
    live_enabled: true
""",
        encoding="utf-8",
    )
    assert load_config(path, {"TEST_KEY": "secret"}).models[0].id == "test"
