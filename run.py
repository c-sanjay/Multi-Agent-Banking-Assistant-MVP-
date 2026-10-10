"""Start backend + UI together:  python run.py   (Ctrl+C stops both)"""
import subprocess
import sys

procs = [
    subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"]),
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py", "--server.port", "8501"]),
]
try:
    for p in procs:
        p.wait()
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        p.terminate()
