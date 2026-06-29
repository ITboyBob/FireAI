from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable


TEXTUTIL_BINARY = "/usr/bin/textutil"
DEFAULT_TEXTUTIL_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True, kw_only=True)
class TextutilRunResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def run_textutil_stdout(
    source_path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout_seconds: float = DEFAULT_TEXTUTIL_TIMEOUT_SECONDS,
) -> TextutilRunResult:
    command = [
        TEXTUTIL_BINARY,
        "-convert",
        "txt",
        "-stdout",
        "-encoding",
        "UTF-8",
        str(source_path),
    ]
    result = runner(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    return TextutilRunResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
