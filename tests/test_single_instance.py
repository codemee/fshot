import subprocess
import sys
import uuid

import pytest

from fshot.single_instance import WindowsInstance


pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows native IPC')


def test_second_process_forwards_before_gui_and_can_restart():
    name = 'Local\\FShot.test.' + uuid.uuid4().hex
    primary = WindowsInstance(name)
    try:
        assert primary.primary
        assert not primary.activation_pending()
        code = """
import sys
from fshot import single_instance
original = single_instance.WindowsInstance
single_instance.WindowsInstance = lambda: original(sys.argv[1])
from fshot.entrypoint import main
assert main() == 0
assert 'fshot.app' not in sys.modules
assert not any(m.startswith('PySide6') for m in sys.modules)
"""
        result = subprocess.run([sys.executable, '-c', code, name], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert primary.activation_pending()
        assert not primary.activation_pending()
    finally:
        primary.close()
    replacement = WindowsInstance(name)
    try:
        assert replacement.primary
    finally:
        replacement.close()


def test_crashed_owner_does_not_leave_stale_lock():
    name = 'Local\\FShot.test.' + uuid.uuid4().hex
    result = subprocess.run([
        sys.executable, '-c',
        'import os,sys; from fshot.single_instance import WindowsInstance; owner=WindowsInstance(sys.argv[1]); assert owner.primary; os._exit(0)',
        name,
    ], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    owner = WindowsInstance(name)
    try:
        assert owner.primary
    finally:
        owner.close()
