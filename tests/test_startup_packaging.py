import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from types import SimpleNamespace

import pytest

from fshot import startup_trace


def test_tracing_is_opt_in_and_records_each_stage_once(monkeypatch, tmp_path):
    trace = tmp_path / 'trace.jsonl'
    monkeypatch.setattr(startup_trace, '_seen', set())
    monkeypatch.delenv('FSHOT_STARTUP_TRACE', raising=False)
    startup_trace.mark('python_entry')
    assert not trace.exists()
    monkeypatch.setenv('FSHOT_STARTUP_TRACE', str(trace))
    startup_trace.mark('python_entry')
    startup_trace.mark('python_entry')
    startup_trace.mark('tray_ready')
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    assert [row['event'] for row in rows] == ['python_entry', 'tray_ready']
    assert rows[1]['elapsed_ms'] >= rows[0]['elapsed_ms'] >= 0


def test_unwritable_trace_does_not_break_startup(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_trace, '_seen', set())
    monkeypatch.setenv('FSHOT_STARTUP_TRACE', str(tmp_path / 'missing' / 'trace.jsonl'))
    startup_trace.mark('python_entry')


def test_version_dispatch_does_not_import_gui():
    code = "import sys; from fshot.entrypoint import main; sys.argv=['fshot','--version']; assert main()==0; assert not any(m.startswith('PySide6') for m in sys.modules); assert 'fshot.capture' not in sys.modules"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('FShot ')


def test_windows_zip_preserves_complete_folder_and_license(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'build_app.py'
    spec = importlib.util.spec_from_file_location('fshot_build_app', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'DIST', tmp_path)
    folder = tmp_path / 'FShot'
    (folder / '_internal').mkdir(parents=True)
    (folder / 'FShot.exe').write_bytes(b'launcher')
    (folder / '_internal' / 'Qt.dll').write_bytes(b'dependency')
    archive = module.package_windows_directory('1.2.3')
    assert archive.name == 'FShot-1.2.3-windows-x64.zip'
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.read('FShot/FShot.exe') == b'launcher'
        assert bundle.read('FShot/_internal/Qt.dll') == b'dependency'
        assert bundle.read('FShot/LICENSE') == (module.ROOT / 'LICENSE').read_bytes()


@pytest.mark.parametrize('gui_ok', [True, False])
def test_macos_checks_packaged_gui_before_building_dmg(monkeypatch, tmp_path, gui_ok):
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'build_app.py'
    spec = importlib.util.spec_from_file_location('fshot_macos_build', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'DIST', tmp_path)
    monkeypatch.setattr(module, 'sys', SimpleNamespace(platform='darwin', executable=sys.executable, argv=['build_app.py']))
    monkeypatch.setattr(sys, 'argv', ['build_app.py'])
    monkeypatch.setattr(module, 'generate_icons', lambda: None)
    calls = []
    packaged = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if command[-1] == '--self-test' and not gui_ok:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(module.subprocess, 'run', run)
    monkeypatch.setattr(module, 'build_macos_dmg', lambda version: packaged.append(version))
    if gui_ok:
        assert module.main() == 0
        assert packaged == [module.project_version()]
    else:
        with pytest.raises(subprocess.CalledProcessError):
            module.main()
        assert not packaged
    checks = calls[1:]
    assert [command[-1] for command, _ in checks] == ['--version', '--self-test']
    assert all(command[0] == str(tmp_path / 'FShot.app' / 'Contents' / 'MacOS' / 'FShot') for command, _ in checks)
    assert checks[0][1]['cwd'] == checks[1][1]['cwd']
    assert all(options['check'] is True for _, options in checks)
