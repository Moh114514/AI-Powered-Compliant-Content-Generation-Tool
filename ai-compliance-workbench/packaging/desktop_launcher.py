"""Windows desktop launcher for the bundled compliance workbench."""
from __future__ import annotations

import multiprocessing
import os
import socket
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path
import tempfile

import tkinter as tk
from tkinter import messagebox

import uvicorn


HOST = "127.0.0.1"
PORT_RANGE = range(8765, 8800)


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
        threading.Thread(target=self.server.run, daemon=True, name="workbench-server").start()
        threading.Thread(target=self._wait_until_ready, daemon=True, name="startup-check").start()
        self.root.mainloop()

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not self.server.should_exit:
            try:
                with urllib.request.urlopen(f"{self.url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        self.root.after(0, self._ready)
                        return
            except Exception:
                time.sleep(0.25)
        self.root.after(0, self._startup_failed)

    def _ready(self) -> None:
        self.status.set(f"运行中：{self.url}")
        self.open_button.configure(state="normal")
        if os.getenv("AI_COMPLIANCE_NO_BROWSER") != "1":
            self.open_browser()

    def _startup_failed(self) -> None:
        self.status.set("启动失败")
        messagebox.showerror("启动失败", "本地服务未能在 30 秒内启动，请退出后重试。")

    def open_browser(self) -> None:
        webbrowser.open(f"{self.url}/generate")

    def open_config_folder(self) -> None:
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.user_data_dir))

    def exit_app(self) -> None:
        self.server.should_exit = True
        self.root.after(150, self.root.destroy)


def main() -> None:
    multiprocessing.freeze_support()
    try:
        DesktopLauncher().start()
    except Exception as exc:
        error_log = Path(tempfile.gettempdir()) / "AI_Compliance_Workbench_startup_error.log"
        error_log.write_text(traceback.format_exc(), encoding="utf-8")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "AI 医美内容合规工作台",
            f"程序启动失败：\n{exc}\n\n错误日志：{error_log}",
        )
        root.destroy()


if __name__ == "__main__":
    main()
