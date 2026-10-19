# -*- coding: utf-8 -*-
import os
import sys
import webbrowser
from threading import Timer
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def open_browser():
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    Timer(1.5, open_browser).start()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
