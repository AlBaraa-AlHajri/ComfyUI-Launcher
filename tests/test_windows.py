"""Windows native handle and packaging resource checks."""

import os

import pytest
from PIL import Image

from comfy_launcher.paths import resource


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex")
def test_single_instance_activation_and_release() -> None:
    from comfy_launcher.single_instance import SingleInstance

    primary = SingleInstance()
    secondary = SingleInstance()
    try:
        assert primary.primary
        assert not secondary.primary
        assert not primary.requested()
        secondary.activate()
        assert primary.requested()
        assert not primary.requested()
    finally:
        secondary.close()
        primary.close()
    fresh = SingleInstance()
    try:
        assert fresh.primary
    finally:
        fresh.close()


def test_all_icon_sizes_present() -> None:
    with Image.open(resource("assets/icon.ico")) as icon:
        assert icon.ico.sizes() == {(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)}
