import json
import os
import subprocess
import time
import urllib.request
import webbrowser
from tkinter import messagebox

BASE = os.path.dirname(os.path.abspath(__file__))
PYTHONW = os.path.join(BASE, ".venv", "Scripts", "pythonw.exe")
APP = os.path.join(BASE, "app.py")
LOG = os.path.join(BASE, "server.log")
URL = "http://127.0.0.1:8765/"
HEALTH = URL + "api/health"


def voiceforge_running():
    try:
        with urllib.request.urlopen(HEALTH, timeout=0.7) as response:
            return json.load(response).get("app") == "VoiceForge"
    except Exception:
        return False


def port_in_use():
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=0.4):
            return True
    except OSError:
        return False


if not voiceforge_running():
    if port_in_use():
        messagebox.showerror("VoiceForge", "Port 8765 is already used by another application. Close it, then try again.")
        raise SystemExit(1)
    if not os.path.isfile(PYTHONW):
        messagebox.showerror("VoiceForge", "VoiceForge is not installed yet. Run install.bat first.")
        raise SystemExit(1)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(LOG, "a", encoding="utf-8") as log:
        subprocess.Popen([PYTHONW, APP], cwd=BASE, stdout=log, stderr=log,
                         creationflags=flags, close_fds=True)
    for _ in range(120):
        if voiceforge_running():
            break
        time.sleep(0.25)
    else:
        messagebox.showerror("VoiceForge", "VoiceForge did not start. Check server.log for details.")
        raise SystemExit(1)
webbrowser.open(URL)
