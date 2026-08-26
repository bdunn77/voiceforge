import os
import socket
import subprocess
import time

BASE = os.path.dirname(os.path.abspath(__file__))
PYTHONW = os.path.join(BASE, ".venv", "Scripts", "pythonw.exe")
APP = os.path.join(BASE, "app.py")
LOG = os.path.join(BASE, "server.log")
URL = "http://127.0.0.1:8765/"

def running():
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=0.4):
            return True
    except OSError:
        return False

if not running():
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(LOG, "a", encoding="utf-8") as log:
        subprocess.Popen([PYTHONW, APP], cwd=BASE, stdout=log, stderr=log,
                         creationflags=flags, close_fds=True)
    for _ in range(80):
        if running():
            break
        time.sleep(0.25)

os.startfile(URL)
