"""Configuration migrations, validation and Windows argument round trips."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from comfy_launcher.config import (
    Config,
    config_path,
    find_python,
    format_args,
    load_config,
    parse_args,
    save_config,
)


def test_roundtrip_and_backup(config: Config) -> None:
    save_config(config)
    assert load_config() == config
    save_config(replace(config, language="en"))
    assert load_config().language == "en"
    assert json.loads(config_path().with_suffix(".json.bak").read_text("utf-8"))["language"] == "ar"
    assert "تجربة" in config_path().read_text("utf-8")


def test_missing_config() -> None:
    assert load_config() is None


def test_legacy_additive_migration(config: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True)
    old = asdict(config)
    for key in ("schema_version", "open_browser_on_start", "minimize_to_tray"):
        old.pop(key)
    old["obsolete_option"] = "ignored"
    path.write_text(json.dumps(old), encoding="utf-8-sig")
    loaded = load_config()
    assert loaded.schema_version == 1
    assert loaded.open_browser_on_start and loaded.minimize_to_tray


def test_corrupt_file_is_preserved(config: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True)
    path.write_text("broken JSON", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config()
    save_config(config)
    backup = list(path.parent.glob("config.invalid-*.json"))
    assert len(backup) == 1
    assert backup[0].read_text("utf-8") == "broken JSON"
    assert load_config() == config


@pytest.mark.parametrize(
    "changes",
    [
        {"port": 0},
        {"port": 65536},
        {"port": True},
        {"port": "8188"},
        {"startup_timeout": 1},
        {"startup_timeout": False},
        {"browser": "unknown"},
        {"language": "xx"},
        {"app_mode": "true"},
        {"extra_args": "--lowvram"},
        {"extra_args": ["--cpu", "--lowvram"]},
        {"extra_args": [3]},
        {"extra_args": ["\x00"]},
        {"extra_args": ["--listen", "192.0.2.1"]},
        {"extra_args": ["--listen=::"]},
        {"python_exe": "missing.exe"},
        {"comfy_dir": "missing"},
    ],
)
def test_validation_rejects_bad_settings(config: Config, changes: dict) -> None:
    with pytest.raises(ValueError):
        replace(config, **changes).validate()


@pytest.mark.parametrize(
    "location",
    ["venv/Scripts", ".venv/Scripts", "python_embeded", "python_embedded", "ComfyUI/venv/Scripts"],
)
def test_interpreter_layouts(tmp_path: Path, location: str) -> None:
    comfy = tmp_path / "ComfyUI"
    comfy.mkdir()
    interpreter = tmp_path / location / "python.exe"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.touch()
    assert find_python(comfy) == interpreter.resolve()


@pytest.mark.parametrize(
    "args",
    [
        ["--output-directory", r"C:\Some Folder\نتائج"],
        ["--input-directory", "folder with trailing slash\\"],
        ["--extra-model-paths-config", 'path with "quotes" and spaces.yaml'],
        ["--cpu", "--preview-method", "auto"],
        [""],
        [],
    ],
)
def test_argument_quoting_roundtrip(args: list[str]) -> None:
    assert parse_args(format_args(args)) == args
