import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

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
