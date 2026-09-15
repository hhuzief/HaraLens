"""Start both services, verify HTTP responses, and stop owned child processes."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for(url: str, process: subprocess.Popen[bytes]) -> bytes:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited with {process.returncode}; inspect .smoke logs")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
                if response.status == 200:
                    return response.read()
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Service startup timed out: {url}; inspect .smoke logs")


def main() -> None:
    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    log_dir = ROOT / ".smoke"
    log_dir.mkdir(exist_ok=True)
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "haralens.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
            "--no-access-log",
        ],
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "apps/streamlit/app.py",
            "--server.address=127.0.0.1",
            f"--server.port={ui_port}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ],
    ]
    processes: list[subprocess.Popen[bytes]] = []
    with ExitStack() as stack:
        try:
            for name, command in zip(["api", "streamlit"], commands, strict=True):
                output = stack.enter_context((log_dir / f"{name}.log").open("wb"))
                processes.append(
                    subprocess.Popen(  # noqa: S603
                        command,
                        cwd=ROOT,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                )
            health = json.loads(
                wait_for(f"http://127.0.0.1:{api_port}/api/v1/health", processes[0])
            )
            if health["status"] != "ok" or health["service"] != "HaraLens":
                raise RuntimeError(f"Unexpected health response: {health}")
            ui_health = wait_for(f"http://127.0.0.1:{ui_port}/_stcore/health", processes[1])
            if ui_health != b"ok":
                raise RuntimeError(f"Unexpected Streamlit health: {ui_health!r}")
            page = wait_for(f"http://127.0.0.1:{ui_port}/", processes[1])
            if b"<html" not in page.lower():
                raise RuntimeError("Streamlit did not serve HTML")
            print(f"PASS FastAPI HTTP 200: {health}")
            print("PASS Streamlit health HTTP 200, body=ok; root serves HTML")
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            print("Stopped all owned service processes")


if __name__ == "__main__":
    main()
