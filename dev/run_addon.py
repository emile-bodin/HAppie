"""Run the add-on on this machine against the local dev Home Assistant.

  python dev/run_addon.py           # echte AH (inloggen via het paneel)
  python dev/run_addon.py --mock-ah # nep-AH-lijst, echte HA

Panel: http://localhost:8099
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / "dev" / ".env"
if not env_file.exists():
    sys.exit("dev/.env ontbreekt; draai eerst: python dev/setup_ha.py")

env = dict(os.environ)
for line in env_file.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

env["SUPERVISOR_TOKEN"] = env["HA_TOKEN"]
env.setdefault("PORT", "8099")
if "--mock-ah" in sys.argv:
    env["HAPPIE_MOCK"] = "ah"
    env["DATA_DIR"] = str(ROOT / ".devdata" / "mock-ah")
else:
    env["DATA_DIR"] = str(ROOT / ".devdata" / "real")
Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

WSL_DIR = "/mnt/" + ROOT.drive[0].lower() + ROOT.as_posix()[2:]

# Start the dev HA container in WSL and keep WSL alive while we run;
# WSL shuts the VM down (and HA with it) when no Windows process uses it.
keepalive = None
if "--no-ha" not in sys.argv:
    subprocess.call(
        ["wsl", "-d", "Ubuntu", "--cd", WSL_DIR, "--", "docker", "compose", "-f", "dev/docker-compose.yml", "up", "-d"]
    )
    keepalive = subprocess.Popen(["wsl", "-d", "Ubuntu", "--", "sleep", "infinity"])

print(f"Paneel: http://localhost:{env['PORT']}  ->  HA: {env['HA_URL']}", flush=True)
try:
    code = subprocess.call([sys.executable, "-u", str(ROOT / "happie" / "app" / "main.py")], env=env)
except KeyboardInterrupt:
    code = 0
finally:
    if keepalive:
        keepalive.terminate()
sys.exit(code)
