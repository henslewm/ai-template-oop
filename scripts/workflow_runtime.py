"""Offline Docker adapter, invoked only by the trusted coordinator.

Worker input is a packet-linked export in a fresh Docker-managed volume, never
a repository mount. No inherited credentials, network, Git or model call.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import uuid

import work_packet as wp
from cli_exit import interrupts_held
from workflow_scope import Ownership, SessionScope, MAX_EXPORT, digest, verify_baseline


def docker(*args, data=None, timeout=60):
    result = subprocess.run(["docker", *args], input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise ValueError("Docker refused: " + result.stderr.decode(errors="replace")[:1000])
    return result.stdout + result.stderr if args[0] == "logs" else result.stdout


def inspect(container):
    return json.loads(docker("inspect", container))[0]


def stopped(container):
    state = inspect(container)["State"]
    return not state["Running"] and not state["Paused"] and not state["Restarting"] and state["Status"] in {"created", "exited", "dead"}


def assert_boundary(container, volume, image):
    info = inspect(container)
    host, config = info["HostConfig"], info["Config"]
    if (host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
            or host["Privileged"] or host.get("CapAdd") or host["CapDrop"] != ["ALL"]
            or host["SecurityOpt"] != ["no-new-privileges"]
            or host.get("Binds") or host.get("VolumesFrom")
            or host.get("PidMode") or host.get("Devices")
            or config["User"] != "1000:1000" or info["Image"] != image):
        raise ValueError("Runtime boundary differs from verified policy")
    mounts = info["Mounts"]
    volumes = [m for m in mounts if m["Type"] != "tmpfs"]
    if len(volumes) != 1 or volumes[0]["Type"] != "volume" or volumes[0]["Name"] != volume or volumes[0]["Destination"] != "/session":
        raise ValueError("Unexpected filesystem mount")
    expected = json.loads(docker("image", "inspect", image))[0]["Config"]["Env"]
    if sorted(config["Env"]) != sorted(expected):
        raise ValueError("Unexpected inherited or supplied environment")
    if host.get("Ulimits") != [{"Name": "fsize", "Hard": 2097152, "Soft": 2097152}]:
        raise ValueError("Missing worker file size bound")
    if host["LogConfig"] != {"Type": "local", "Config": {"max-file": "2", "max-size": "1m"}}:
        raise ValueError("Unexpected worker log bound")
    if host["Memory"] != 536870912 or host["PidsLimit"] != 64 or host["NanoCpus"] != 1000000000:
        raise ValueError("Unexpected runtime resource bounds")


def state_directory(scope):
    # All worktrees of a repository use one durable host-only ownership database.
    common = subprocess.run(
        ["git", "-C", str(scope.root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=True, capture_output=True, text=True).stdout.strip()
    identity = str(Path(common).resolve()).casefold() if os.name == "nt" else str(Path(common).resolve())
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "state"))
    return base / "ai-template-workflow" / digest(identity.encode())


def check_state(scope, state):
    if state.resolve() != state_directory(scope).resolve():
        raise ValueError("Use the canonical repository ownership directory; alternate ledgers are refused")
    for parent in [state, *state.parents]:
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Ownership directory cannot contain links")


def prepare(scope, packet, graph, state, image, argv):
    check_state(scope, state)
    scope.verify_base()
    export, baseline = scope.export(packet, graph)
    if not image.startswith("sha256:") or len(image) != 71:
        raise ValueError("Use a locally verified immutable image ID")
    if not argv or argv[0] not in {"python", "sh", "cline"}:
        raise ValueError("Only verified Python, POSIX shell or Cline entry points are supported")
    run = state / ("run-" + uuid.uuid4().hex)
    run.mkdir(parents=True, exist_ok=False)
    (run / "scope.json").write_text(wp.canonical(scope.data), encoding="utf-8")
    (run / "packet.json").write_text(wp.canonical(packet), encoding="utf-8")
    (run / "baseline.json").write_text(wp.canonical(baseline), encoding="utf-8")
    (run / "input.tar").write_bytes(export)
    volume = "workflow-" + uuid.uuid4().hex
    docker("volume", "create", volume)
    # Docker cp from stdin normalizes UIDs on this Windows engine. A fixed trusted
    # initializer sets writable-file UIDs before any untrusted worker is created.
    initializer = ("import json,os; from pathlib import Path; "
                   "s=json.loads(Path('/session/scope.json').read_text()); "
                   "[os.chown('/session/workspace/'+p,1000,1000) for p in s['write_paths']]")
    setup = docker("create", "--network", "none", "--read-only", "--user", "0:0",
                   "--cap-drop", "ALL", "--cap-add", "CHOWN", "--security-opt", "no-new-privileges",
                   "--mount", "type=volume,source=" + volume + ",destination=/session",
                   "--entrypoint", "python", image, "-c", initializer).decode().strip()
    docker("cp", "-a", "-", setup + ":/session", data=export)
    docker("start", "-a", setup)
    if inspect(setup)["State"]["ExitCode"] != 0 or not stopped(setup):
        raise ValueError("Trusted scope initialization failed")
    container = docker("create", "--network", "none", "--read-only", "--user", "1000:1000",
                       "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                       "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
                       "--ulimit", "fsize=2097152:2097152",
                       "--log-driver", "local", "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
                       "--mount", "type=volume,source=" + volume + ",destination=/session",
                       "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=67108864",
                       "--tmpfs", "/out:rw,noexec,nosuid,nodev,uid=1000,gid=1000,size=67108864",
                       "--workdir", "/session/workspace", "--entrypoint", argv[0], image, *argv[1:]).decode().strip()
    assert_boundary(container, volume, image)
    ownership = Ownership(state)
    token = ownership.claim(scope, container)
    record = {"container": container, "setup_container": setup, "volume": volume,
              "image": image, "ownership_token": token, "scope_sha256": scope.hash,
              "task_id": packet["task_id"], "argv": argv, "status": "prepared"}
    (run / "runtime.json").write_text(wp.canonical(record), encoding="utf-8")
    return run


def preserve(container, run):
    archive = docker("cp", container + ":/session/workspace", "-", timeout=60)
    target = run / ("output-" + uuid.uuid4().hex + ".tar")
    target.write_bytes(archive)  # Preserve opaque bytes; never extract untrusted worker paths on the host.
    return target


def bundle_from_archive(scope, baseline, archive):
    changes = []
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        members = tar.getmembers()
        seen = set()
        for member in members:
            name = member.name
            if name in {"workspace", "workspace/"} and member.isdir():
                continue
            if not name.startswith("workspace/"):
                raise ValueError("Output archive escaped workspace")
            path = name[10:].rstrip("/")
            from workflow_scope import checked_path, digest, MAX_FILE
            checked_path(path)
            if path.casefold() in seen:
                raise ValueError("Duplicate archive entry")
            seen.add(path.casefold())
            if member.isdir():
                if not any(p.startswith(path + "/") for p in baseline):
                    raise ValueError("Unexpected output directory")
                continue
            if not member.isfile() or member.size > MAX_FILE or path not in baseline:
                raise ValueError("Linked, oversized or unexpected output file")
            total += member.size
            if total > MAX_EXPORT:
                raise ValueError("Output archive exceeded scope size")
            data = tar.extractfile(member).read()
            if digest(data) != baseline[path] and not (baseline[path] is None and data == b""):
                if path not in scope.data["write_paths"]:
                    raise ValueError("Immutable scope input changed")
                import base64
                changes.append({"path": path, "before_sha256": baseline[path],
                                "content_base64": base64.b64encode(data).decode()})
        if not set(baseline).issubset(seen):
            raise ValueError("Output deleted a supplied file")
    return {"scope_sha256": scope.hash, "base_commit": scope.data["base_commit"], "changes": changes}


def execute(run, state, timeout):
    if not 1 <= timeout <= 300:
        raise ValueError("Offline execution timeout must be 1 through 300 seconds")
    record = wp.read_json(run / "runtime.json")
    scope = SessionScope.load(wp.read_json(run / "scope.json"))
    if scope.hash != record["scope_sha256"]:
        raise ValueError("Changed run scope")
    check_state(scope, state)
    scope.verify_base()
    verify_baseline(scope, wp.read_json(run / "baseline.json"))
    assert_boundary(record["container"], record["volume"], record["image"])
    if inspect(record["container"])["State"]["Status"] != "created":
        raise ValueError("A prepared container starts once")
    ownership = Ownership(state)
    with ownership.transaction() as db:
        row = ownership.row(db, record["ownership_token"])
        if row["scope_hash"] != scope.hash or row["container"] != record["container"]:
            raise ValueError("Ownership does not match run")
    start_attempted = False

    def start_container(container):
        nonlocal start_attempted
        # Docker may start the container before its CLI times out or is interrupted.
        start_attempted = True
        docker("start", container)

    timed_out = False
    try:
        ownership.start(record["ownership_token"], start_container)
        deadline = time.monotonic() + timeout
        while not stopped(record["container"]):
            if time.monotonic() >= deadline:
                timed_out = True
                docker("kill", record["container"])
                break
            time.sleep(0.1)
    finally:
        # A refused ownership check must leave the claim for explicit recovery.
        if start_attempted:
            with interrupts_held():
                if not stopped(record["container"]):
                    docker("kill", record["container"])
                if not stopped(record["container"]):
                    raise ValueError("Container tree not confirmed stopped")
                (run / "stdout.log").write_bytes(docker("logs", record["container"]))
                ownership.finish(record["ownership_token"], stopped, lambda c: preserve(c, run))
    record["status"] = "timed_out" if timed_out else "exited"
    record["exit_code"] = inspect(record["container"])["State"]["ExitCode"]
    (run / "runtime.json").write_text(wp.canonical(record), encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--scope", required=True, type=Path)
    prep.add_argument("--packet", required=True, type=Path)
    prep.add_argument("--graph", nargs="*", default=[], type=Path)
    prep.add_argument("--state", required=True, type=Path)
    prep.add_argument("--image", required=True)
    prep.add_argument("argv", nargs=argparse.REMAINDER)
    directory = commands.add_parser("state-directory", help="Print the one shared repository control directory")
    directory.add_argument("--scope", required=True, type=Path)
    for command in ("execute", "heartbeat", "recover", "bundle"):
        sub = commands.add_parser(command)
        sub.add_argument("--run", required=True, type=Path)
        sub.add_argument("--state", required=True, type=Path)
        if command == "execute":
            sub.add_argument("--timeout", type=int, default=60)
        if command == "heartbeat":
            sub.add_argument("--lease-seconds", type=int, default=300)
    args = parser.parse_args()
    try:
        if args.command == "state-directory":
            print(state_directory(SessionScope.load(wp.read_json(args.scope))))
        elif args.command == "prepare":
            argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            run = prepare(SessionScope.load(wp.read_json(args.scope)), wp.read_json(args.packet),
                          [wp.read_json(p) for p in args.graph], args.state, args.image, argv)
            print(json.dumps({"run": str(run), "started": False}))
        else:
            run = args.run
            record = wp.read_json(run / "runtime.json")
            check_state(SessionScope.load(wp.read_json(run / "scope.json")), args.state)
            if args.command == "execute":
                result = execute(run, args.state, args.timeout)
                print(json.dumps(result))
                return 2 if result["exit_code"] or result["status"] == "timed_out" else 0
            ownership = Ownership(args.state)
            if args.command == "heartbeat":
                ownership.heartbeat(record["ownership_token"], args.lease_seconds)
            elif args.command == "recover":
                ownership.finish(record["ownership_token"], stopped, lambda c: preserve(c, run), recovering=True)
            else:
                if not stopped(record["container"]):
                    raise ValueError("Cannot collect output from a live process")
                archive = docker("cp", record["container"] + ":/session/workspace", "-")
                bundle = bundle_from_archive(SessionScope.load(wp.read_json(run / "scope.json")),
                                             wp.read_json(run / "baseline.json"), archive)
                target = run / ("bundle-" + uuid.uuid4().hex + ".json")
                target.write_text(wp.canonical(bundle), encoding="utf-8")
                print(json.dumps({"bundle": str(target), "accepted": False, "applied": False}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print("RUNTIME REFUSED: " + str(exc))
        return 1


if __name__ == "__main__":
    import cli_exit
    raise SystemExit(cli_exit.run(main))
