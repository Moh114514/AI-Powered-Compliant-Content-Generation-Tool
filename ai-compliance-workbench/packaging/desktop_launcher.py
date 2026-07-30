"""Windows desktop launcher for the bundled compliance workbench."""
from __future__ import annotations

import multiprocessing
import io
import logging
import os
import platform
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
import tempfile

import tkinter as tk
from tkinter import messagebox

import uvicorn


HOST = "127.0.0.1"
PORT_RANGE = range(8765, 8800)
STARTUP_LOG_NAME = "AI_Compliance_Workbench_startup_error.log"


def write_startup_log(
    reason: str,
    *,
    details: str = "",
    user_data_dir: Path | None = None,
    log_path: Path | None = None,
) -> Path | None:
    """Write a best-effort startup diagnostic without exposing secret values."""
    local_app_data = os.getenv("LOCALAPPDATA", "")
    candidates = [log_path] if log_path else [
        Path(tempfile.gettempdir()) / STARTUP_LOG_NAME,
        (user_data_dir / STARTUP_LOG_NAME) if user_data_dir else None,
    ]
    report = "\n".join([
        "AI Compliance Workbench startup diagnostics",
        f"timestamp: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"reason: {reason}",
        f"os: {platform.platform()}",
        f"architecture: {platform.machine()}",
        f"python: {sys.version}",
        f"frozen: {bool(getattr(sys, 'frozen', False))}",
        f"executable: {sys.executable}",
        f"working_directory: {Path.cwd()}",
        f"temp_directory: {tempfile.gettempdir()}",
        f"local_app_data: {local_app_data or '<not set>'}",
        f"user_data_directory: {user_data_dir or '<not available>'}",
        f"llm_api_key_present: {bool(os.getenv('LLM_API_KEY'))}",
        "",
        "details:",
        details.strip() or "<no additional details>",
        "",
    ])
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(report, encoding="utf-8")
            return candidate
        except OSError:
            continue
    return None


def available_port() -> int:
    for port in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("8765-8799 端口均被占用，请关闭占用程序后重试。")


class DesktopLauncher:
    def __init__(self) -> None:
        from app.core import config
        from app.main import app

        self.user_data_dir = config.PROJECT_ROOT
        self.port = available_port()
        self.url = f"http://{HOST}:{self.port}"
        self.server_error = ""
        self.last_probe_error = ""
        self.failure_reported = False
        self.exiting = False
        self.uvicorn_output = io.StringIO()
        self.uvicorn_handler = logging.StreamHandler(self.uvicorn_output)
        self.uvicorn_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        for logger_name in ("uvicorn", "uvicorn.error"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.INFO)
            logger.addHandler(self.uvicorn_handler)
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=HOST,
                port=self.port,
                loop="asyncio",
                http="h11",
                log_level="warning",
                log_config=None,
                access_log=False,
            )
        )
        self.root = tk.Tk()
        self.root.title("AI 医美内容合规工作台")
        self.root.geometry("430x250")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.status = tk.StringVar(value="正在启动本地服务…")
        self._build_window()

    def _build_window(self) -> None:
        frame = tk.Frame(self.root, padx=24, pady=22)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="AI 医美内容合规工作台", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        tk.Label(
            frame,
            text="程序会在本机运行，并通过默认浏览器打开工作台。",
            font=("Microsoft YaHei UI", 10),
            fg="#4b5563",
            pady=10,
        ).pack(anchor="w")
        tk.Label(
            frame,
            textvariable=self.status,
            font=("Microsoft YaHei UI", 10),
            fg="#1d4ed8",
            pady=6,
        ).pack(anchor="w")
        buttons = tk.Frame(frame, pady=14)
        buttons.pack(fill="x")
        self.open_button = tk.Button(
            buttons,
            text="打开工作台",
            font=("Microsoft YaHei UI", 10),
            width=15,
            state="disabled",
            command=self.open_browser,
        )
        self.open_button.pack(side="left")
        tk.Button(
            buttons,
            text="配置目录",
            font=("Microsoft YaHei UI", 10),
            width=10,
            command=self.open_config_folder,
        ).pack(side="left", padx=8)
        tk.Button(
            buttons,
            text="退出程序",
            font=("Microsoft YaHei UI", 10),
            width=12,
            command=self.exit_app,
        ).pack(side="right")
        tk.Label(
            frame,
            text="关闭此窗口并退出后，本地服务将停止。",
            font=("Microsoft YaHei UI", 9),
            fg="#9ca3af",
        ).pack(anchor="w")

    def start(self) -> None:
        threading.Thread(target=self._run_server, daemon=True, name="workbench-server").start()
        threading.Thread(target=self._wait_until_ready, daemon=True, name="startup-check").start()
        self.root.mainloop()

    def _run_server(self) -> None:
        try:
            self.server.run()
        except BaseException:
            self.server_error = traceback.format_exc()
        finally:
            if not self.server.started and not self.server_error:
                self.server_error = (
                    "uvicorn.Server.run() exited before the server reported a successful startup.\n"
                    f"should_exit={self.server.should_exit}"
                )

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not self.exiting:
            try:
                with urllib.request.urlopen(f"{self.url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        self.root.after(0, self._ready)
                        return
            except Exception as exc:
                self.last_probe_error = f"{type(exc).__name__}: {exc}"
                if self.server.should_exit:
                    break
                time.sleep(0.25)
        if not self.exiting:
            self.root.after(0, self._startup_failed)

    def _ready(self) -> None:
        self._detach_log_handler()
        self.status.set(f"运行中：{self.url}")
        self.open_button.configure(state="normal")
        if os.getenv("AI_COMPLIANCE_NO_BROWSER") != "1":
            self.open_browser()

    def _startup_failed(self) -> None:
        if self.failure_reported or self.exiting:
            return
        self.failure_reported = True
        self.status.set("启动失败")
        details = "\n".join([
            f"url: {self.url}",
            f"port: {self.port}",
            f"server_started: {self.server.started}",
            f"server_should_exit: {self.server.should_exit}",
            f"last_health_probe_error: {self.last_probe_error or '<none>'}",
            "",
            "server_thread_error:",
            self.server_error or "<no exception escaped from server thread>",
            "",
            "uvicorn_output:",
            self.uvicorn_output.getvalue().strip() or "<no uvicorn output captured>",
        ])
        error_log = write_startup_log(
            "Local service did not become healthy within 30 seconds.",
            details=details,
            user_data_dir=self.user_data_dir,
        )
        self._detach_log_handler()
        log_message = str(error_log) if error_log else "日志写入失败，请检查 TEMP 和 LOCALAPPDATA 目录权限。"
        messagebox.showerror(
            "启动失败",
            f"本地服务未能正常启动。\n\n诊断日志：\n{log_message}",
        )

    def _detach_log_handler(self) -> None:
        for logger_name in ("uvicorn", "uvicorn.error"):
            logging.getLogger(logger_name).removeHandler(self.uvicorn_handler)

    def open_browser(self) -> None:
        webbrowser.open(f"{self.url}/generate")

    def open_config_folder(self) -> None:
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.user_data_dir))

    def exit_app(self) -> None:
        self.exiting = True
        self._detach_log_handler()
        self.server.should_exit = True
        self.root.after(150, self.root.destroy)


def main() -> None:
    multiprocessing.freeze_support()
    try:
        DesktopLauncher().start()
    except Exception as exc:
        error_log = write_startup_log(
            "Unhandled exception while initializing the desktop launcher.",
            details=traceback.format_exc(),
        )
        root = tk.Tk()
        root.withdraw()
        log_message = str(error_log) if error_log else "日志写入失败，请检查 TEMP 目录权限。"
        messagebox.showerror(
            "AI 医美内容合规工作台",
            f"程序启动失败：\n{exc}\n\n诊断日志：\n{log_message}",
        )
        root.destroy()


if __name__ == "__main__":
    main()
