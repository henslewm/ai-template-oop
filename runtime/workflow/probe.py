"""Offline runtime probe: fail on any unexpected access; never print file contents."""
import json
import os
from pathlib import Path
import socket
import subprocess

results = {}
def check(name, passed):
    results[name] = bool(passed)
    if not passed:
        raise RuntimeError(name)

check("unprivileged", os.getuid() == 1000)
paths = [
    "/mnt/c/Users/hensl/Documents/GitHub/ai-template/ai-template-oop/README.md",
    "/run/desktop/mnt/host/c/Users/hensl/Documents/GitHub/ai-template/ai-template-oop/README.md",
    "/host_mnt/c/Users/hensl/Documents/GitHub/ai-template/universal-ai-project-template/AGENTS.md",
    "C:/Users/hensl/Documents/GitHub/ai-template/universal-ai-project-template/AGENTS.md",
    "/var/run/docker.sock", "/proc/1/root/mnt/c/Users/hensl/Documents/GitHub",
    "/inputs/.git", "/work/.git",
]
for n, path in enumerate(paths):
    result = subprocess.run(["sh", "-c", 'cat "$1" >/dev/null 2>&1', "probe", path])
    check(f"shell_host_read_denied_{n}", result.returncode != 0)
for name, path in [("contract", "/inputs/contracts/allowed.txt"), ("unowned", "/work/unowned.txt")]:
    result = subprocess.run(["sh", "-c", 'printf changed > "$1"', "probe", path],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    check(f"{name}_write_denied", result.returncode != 0)
check("allowed_input_readable", Path("/inputs/contracts/allowed.txt").read_text() == "allowed\n")
Path("/work/owned.txt").write_text("worker output\n")
check("owned_write_allowed", Path("/work/owned.txt").read_text() == "worker output\n")
link = Path("/out/escape")
link.symlink_to("/run/desktop/mnt/host/c/Users/hensl/Documents/GitHub/ai-template/ai-template-oop/README.md")
check("symlink_host_read_denied", not link.exists())
for label, host, port in [("public", "1.1.1.1", 443), ("host", "192.168.65.254", 2375)]:
    try:
        socket.create_connection((host, port), timeout=1).close()
    except OSError:
        check(f"{label}_network_denied", True)
    else:
        check(f"{label}_network_denied", False)
for name, argv in [("python", ["python", "--version"]), ("shell", ["sh", "-c", "id -u"]),
                   ("cline", ["cline", "--version"]), ("cline_help", ["cline", "--help"])]:
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    check(f"{name}_startup", result.returncode == 0)
    if name in {"python", "cline"}:
        results[f"{name}_version"] = result.stdout.decode().strip()
print(json.dumps(results, indent=2))
