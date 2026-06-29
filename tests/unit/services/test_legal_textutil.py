from pathlib import Path
import subprocess

from app.services.legal_textutil import run_textutil_stdout


def test_run_textutil_stdout_uses_fixed_safe_command(tmp_path):
    source = tmp_path / "sample.doc"
    source.write_bytes(b"sample")
    calls = []

    def fake_runner(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "法规\n第一条 正文", "")

    result = run_textutil_stdout(source, runner=fake_runner)

    assert result.returncode == 0
    assert result.stdout == "法规\n第一条 正文"
    assert calls == [
        (
            [
                "/usr/bin/textutil",
                "-convert",
                "txt",
                "-stdout",
                "-encoding",
                "UTF-8",
                str(source),
            ],
            {
                "check": False,
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": 30.0,
            },
        )
    ]


def test_run_textutil_stdout_preserves_nonzero_exit_and_stderr(tmp_path):
    source = tmp_path / "sample.doc"
    source.write_bytes(b"sample")

    def fake_runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "conversion failed")

    result = run_textutil_stdout(source, runner=fake_runner)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "conversion failed"
    assert result.succeeded is False
