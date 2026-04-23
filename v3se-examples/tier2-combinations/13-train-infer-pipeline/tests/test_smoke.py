from pathlib import Path

import pytest

from train_infer import config, bundler


def test_config_defaults():
    assert config.model_id()
    assert config.lora_r() == 8


def test_bundler_requires_existing_adapter(tmp_path):
    with pytest.raises(FileNotFoundError, match="Adapter dir"):
        bundler.build(tmp_path / "nope", "dummy-model",
                       tmp_path / "out.sif",
                       tpl_path=tmp_path / "nope.def")
