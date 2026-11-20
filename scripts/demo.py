"""Start and manage the Windows Heimdal demo from one console."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
import venv
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DASHBOARD = "https://localhost:8443"
COLLECTOR = "http://localhost:9001"


def prepare_build():
    npm = shutil.which("npm.cmd")
    if npm is None:
        raise RuntimeError("Install Node.js 22.12 or newer, then reopen the launcher.")
    if not PYTHON.is_file():
        print("Creating the Python environment...")
        venv.EnvBuilder(with_pip=True).create(PYTHON.parents[1])
    print("Checking Python dependencies...")
    subprocess.run([PYTHON, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                    "-r", "requirements.lock"], cwd=ROOT, check=True)
    lock_hash = sha256((ROOT / "frontend" / "package-lock.json").read_bytes()).hexdigest()
    stamp = ROOT / "frontend" / "node_modules" / ".heimdal-lock"
    if not stamp.is_file() or stamp.read_text(encoding="ascii") != lock_hash:
        print("Installing dashboard dependencies...")
        subprocess.run([npm, "--prefix", "frontend", "ci"], cwd=ROOT, check=True)
        stamp.write_text(lock_hash, encoding="ascii")
    subprocess.run([npm, "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True)


def require_free_port(port):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(f"Port {port} is busy. Stop the older demo before starting another.") from None


def start_service(runtime, module, log_name, *options):
    with (runtime / log_name).open("wb") as log:
        return subprocess.Popen(
            [PYTHON, "-m", module, "--runtime", runtime, *options],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )


def stop_service(process):
    if process is None or process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        process.terminate()
        process.wait(timeout=5)


def wait_for(opener, process, request, log_path):
    deadline = time.monotonic() + 15
    while process.poll() is None and time.monotonic() < deadline:
        try:
            with opener.open(request, timeout=1) as response:
                if response.status == 200:
                    return
        except URLError as error:
            if isinstance(error.reason, ssl.SSLCertVerificationError):
                raise RuntimeError("The demo certificate is invalid or expired. Start with a fresh runtime "
                                   "using --runtime .heimdal/fresh-demo.") from None
        except TimeoutError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Service failed to start. See {log_path}.")


def open_pages(ca):
    cert = ssl.PEM_cert_to_DER_cert(ca.read_text(encoding="ascii"))
    trusted = any(encoding == "x509_asn" and body == cert and
                  (trust is True or "1.3.6.1.5.5.7.3.1" in trust)
                  for body, encoding, trust in ssl.enum_certificates("ROOT"))
    if not trusted:
        answer = input("Trust this locally generated demo CA for your Windows user? [y/N] ").strip().lower()
        if answer != "y":
            print("Browser pages were not opened. Choose option 3 when you are ready.")
            return
        result = subprocess.run(["certutil.exe", "-user", "-addstore", "Root", ca], check=False)
        if result.returncode:
            print("Windows did not add the demo CA. See docs/RUNBOOK.md for browser setup.")
            return
    webbrowser.open(DASHBOARD)
    webbrowser.open(COLLECTOR + "/scenarios")


def copy_token(token, destination):
    subprocess.run(["clip.exe"], input=token.encode("ascii"), check=True)
    print(f"Copied the token. Paste it into the {destination} field.")


def run_demo(runtime, open_browser):
    require_free_port(8443)
    require_free_port(9001)
    prepare_build()
    if not runtime.exists():
        subprocess.run([PYTHON, "-m", "scripts.security.bootstrap", "--runtime", runtime], cwd=ROOT, check=True)
    operator = json.loads((runtime / "operator-alpha.json").read_bytes())
    settings = json.loads((runtime / "collector-alpha.json").read_bytes())
    if settings["saas_url"] != DASHBOARD or settings["local_port"] != 9001:
        raise RuntimeError("This runtime uses custom ports. Choose a fresh runtime with --runtime .heimdal/fresh-demo.")
    ca = runtime / "ca.pem"
    tls = ssl.create_default_context(cafile=str(ca))
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls))
    fleet_request = Request(DASHBOARD + "/api/v1/fleet",
                            headers={"Authorization": "Bearer " + operator["token"]})
    local_request = Request(COLLECTOR + "/api/local/scenarios",
                            headers={"Authorization": "Bearer " + settings["local_token"]})

    def start_collector():
        return start_service(runtime, "backend.collector.daemon", "collector.log", "--scenarios")

    saas = collector = None
    try:
        saas = start_service(runtime, "backend.saas.main", "saas.log", "--dashboard", "frontend/dist")
        wait_for(opener, saas, fleet_request, runtime / "saas.log")
        collector = start_collector()
        wait_for(opener, collector, local_request, runtime / "collector.log")
        print(f"Demo ready. Dashboard: {DASHBOARD} | Tenant ID: {operator['tenant_id']}")
        print(f"Local scenario runner: {COLLECTOR}/scenarios")
        if open_browser:
            open_pages(ca)
        while True:
            print("\n1  Copy dashboard operator token")
            print("2  Copy local session token")
            print("3  Open dashboard and scenario runner")
            print("4  Stop/start collector for the offline check")
            print("Q  Stop the demo")
            choice = input("Choose: ").strip().lower()
            if choice == "q":
                return
            if choice == "1":
                copy_token(operator["token"], "Operator token")
            elif choice == "2":
                copy_token(settings["local_token"], "Local session token")
            elif choice == "3":
                open_pages(ca)
            elif choice == "4":
                if collector.poll() is None:
                    stop_service(collector)
                    print("Collector stopped. Wait about 56 seconds and check the fleet for Poor.")
                else:
                    require_free_port(9001)
                    collector = start_collector()
                    wait_for(opener, collector, local_request, runtime / "collector.log")
                    print("Collector restarted.")
    finally:
        try:
            stop_service(collector)
        finally:
            stop_service(saas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(".heimdal/scenario-demo"))
    parser.add_argument("--no-browser", action="store_true", help="Start without opening browser pages")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info < (3, 11):
        parser.exit(1, "This launcher needs Windows and Python 3.11 or newer. See docs/RUNBOOK.md.\n")
    runtime = (ROOT / args.runtime).resolve()
    if (ROOT / ".heimdal") not in runtime.parents:
        parser.error("Choose a runtime inside .heimdal so demo credentials stay out of Git.")
    try:
        run_demo(runtime, not args.no_browser)
    except (KeyboardInterrupt, EOFError):
        print("\nDemo stopped.")
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Could not run the demo: {error}\n")


if __name__ == "__main__":
    main()
