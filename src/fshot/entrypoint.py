"""Lightweight dispatch before loading the GUI."""
from __future__ import annotations

import sys
from fshot.startup_trace import mark


def main() -> int:
    mark('python_entry')
    if '--version' in sys.argv:
        from fshot import __version__
        print(f'FShot {__version__}')
        return 0
    if '--self-test' in sys.argv:
        from fshot.packaging_smoke import main as smoke_main
        return smoke_main()
    instance = None
    try:
        if sys.platform == 'win32':
            from fshot.single_instance import WindowsInstance
            instance = WindowsInstance()
            if not instance.primary:
                instance.activate()
                mark('activation_forwarded')
                return 0
        from fshot.app import main as app_main
        mark('imports_ready')
        return app_main(instance=instance)
    finally:
        if instance is not None:
            instance.close()
