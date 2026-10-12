"""Bound retention across dated output files and size-based rotations."""

from comfy_launcher.logging_setup import logs_dir, server_log


def test_total_server_log_retention() -> None:
    for day in range(1, 13):
        (logs_dir() / f"comfyui_2000-01-{day:02d}.log").write_text("history", encoding="utf-8")
    logger, _ = server_log()
    handler = logger.handlers[0]
    handler.maxBytes = 32
    try:
        for _ in range(20):
            logger.info("A complete line that triggers size-based log rotation.")
            assert len(list(logs_dir().glob("comfyui_*.log*"))) <= 10
    finally:
        handler.close()
        logger.removeHandler(handler)
