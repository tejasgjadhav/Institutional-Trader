"""Run a harness script with patient fetching (27-Sep-2026): a 30 s socket timeout so a dangling
read fails instead of hanging, and HTTP 429 answered by waiting 60 s and retrying (up to 40 times)
instead of dropping the leg after ~30 s. Usage: patient_run.py <script> <arg>."""
import socket, runpy, sys, time
socket.setdefaulttimeout(30)
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import engine.expired_options as eo
from engine.data_fetcher import SESSION
def patient(url, params=None, attempts=6):
    for i in range(40):
        try:
            r = SESSION.get(url, params=params, timeout=25)
            if r.status_code == 429:
                time.sleep(60); continue
            r.raise_for_status(); return r.json()
        except Exception:
            time.sleep(5)
    return {}
eo._get_json = patient
script, arg = sys.argv[1], sys.argv[2]
sys.argv = [script, arg]
runpy.run_path(script, run_name="__main__")
