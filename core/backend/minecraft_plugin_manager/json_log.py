"""Structured JSON logging — writes ef_log_v1 events to JSONL file.

ef-metrics core component tails these files independently.
No external dependencies — uses Python's built-in logging module.
"""

import json
import logging
import os
import socket
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_TOOL_NAME = "minecraft-plugin-manager"


class JSONFormatter(logging.Formatter):
    """Format log records as ef_log_v1 JSON lines."""

    def format(self, record):
        msg = {
            "schema": "ef_log_v1",
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "tool": _TOOL_NAME,
            "logger": record.name,
            "hostname": socket.gethostname(),
        }
        tid = _trace_id.get("")
        if tid:
            msg["trace_id"] = tid
        if isinstance(record.msg, dict):
            msg.update(record.msg)
        else:
            msg["message"] = record.getMessage()
        return json.dumps(msg, default=str)


def new_trace() -> str:
    """Generate and set a new trace ID."""
    tid = uuid.uuid4().hex[:16]
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    return _trace_id.get("")


def setup_logging(also_stdout: bool = True):
    """Configure JSON logging to file and optionally stdout."""
    log_dir = os.environ.get("EF_METRICS_LOG_DIR", "/var/log/ef")
    formatter = JSONFormatter()
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # File handler
    try:
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(log_dir, f"{_TOOL_NAME}.jsonl"), mode="a")
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except OSError:
        pass  # Can't write file — stdout only

    if also_stdout:
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        root.addHandler(sh)
