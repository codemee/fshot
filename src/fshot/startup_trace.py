"""Optional startup tracing; safe to import before Qt or capture libraries."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

_seen: set[str] = set()
_started_ns = time.perf_counter_ns()


def mark(event: str) -> None:
    destination = os.environ.get('FSHOT_STARTUP_TRACE')
    if not destination or event in _seen:
        return
    _seen.add(event)
    now = time.perf_counter_ns()
    try:
        started = int(os.environ.get('FSHOT_STARTUP_STARTED_NS', str(_started_ns)))
        record = {'event': event, 'pid': os.getpid(), 'elapsed_ms': round((now - started) / 1_000_000, 3)}
        with Path(destination).open('a', encoding='utf-8') as output:
            output.write(json.dumps(record) + '\n')
    except (OSError, ValueError):
        # Diagnostics must never stop normal startup.
        pass
