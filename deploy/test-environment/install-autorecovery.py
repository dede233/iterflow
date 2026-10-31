"""配置独立测试环境开机恢复并验证；不重启主机、Docker、firewalld或正式服务。"""

import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import traceback
from pathlib import Path
from urllib.request import urlopen

CONTROL = Path("/opt/iterflow/acceptance-control/20261012")
sys.path.insert(0, str(CONTROL))
import control

PAYLOAD = Path(__file__).resolve().parent
UNIT_NAMES = ("iterflow-test-stack.service", "iterflow-test-nginx.service")
NGINX = "/www/server/nginx/sbin/nginx"
os.umask(0o077)


def write(path, data):
    control.write(
        path,
        data
        if isinstance(data, str)
        else json.dumps(data, ensure_ascii=False, indent=2),
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def systemctl(*args):
    return control.run(["systemctl"] + list(args))


def snapshot(state):
    original = (CONTROL / "production-readonly.py").read_text()
    prefix = "from app.core.database import engine\nassert engine.dialect.name == 'mysql'\nwith engine.connect() as guard:\n    assert guard.exec_driver_sql('SELECT DATABASE()').scalar() == 'iterflow_acceptance'\n"
    code = prefix + original
    compile(code, "<test-readonly>", "exec")
    return json.loads(
        control.dc(
            state, "run", "--rm", "--no-deps", "-T", "api", "python", "-", stdin=code
        ).stdout
    )


def request_ready():
    response = urlopen("https://sx-kc.xyz:8444/", timeout=10)
    assert response.status == 200
    return True


def wait_ready():
    for _ in range(60):
        try:
            return request_ready()
        except (OSError, AssertionError):
            time.sleep(1)
    raise RuntimeError("测试 HTTPS 恢复超时")


def protected_binary(args, path, stderr):
    with path.open("xb") as out, stderr.open("ab") as err:
        result = subprocess.run(args, stdout=out, stderr=err, timeout=600, check=False)
    assert result.returncode == 0, "独立测试备份失败，查看受保护日志"
    path.chmod(0o600)


def install():
    state = control.load()
    assert state["retention"]["keep"] and state.get("cleanup_hold")
    assert control.production_snapshot() == state["baseline"]
    stage = Path(state["stage"])
    evidence = Path(state["evidence"]) / "autorecovery-20261012"
    assert not evidence.exists()
    evidence.mkdir(mode=0o700)
    manifest = json.loads((PAYLOAD / "manifest.json").read_text())
    for name, expected in manifest.items():
        assert digest(PAYLOAD / name) == expected
    for name in UNIT_NAMES:
        assert not (Path("/etc/systemd/system") / name).exists()
    permanent_before = set(
        control.run(
            ["firewall-cmd", "--permanent", "--zone=public", "--list-ports"]
        ).stdout.split()
    )
    runtime_before = set(
        control.run(["firewall-cmd", "--zone=public", "--list-ports"]).stdout.split()
    )
    assert "8444/tcp" in runtime_before and "8444/tcp" not in permanent_before
    before_containers = {}
    for service in ("db", "redis", "api", "web"):
        c = json.loads(
            control.run(
                ["docker", "inspect", state["project"] + "-" + service + "-1"]
            ).stdout
        )[0]
        assert c["State"]["Running"] and c["State"]["Health"]["Status"] == "healthy"
        assert c["Config"]["Labels"]["com.docker.compose.project"] == state["project"]
        before_containers[service] = {
            "id": c["Id"],
            "image": c["Image"],
            "mounts": c["Mounts"],
        }
    for name in ("acceptance.yml", "review-nginx.conf"):
        shutil.copyfile(str(stage / name), str(evidence / (name + ".before")))
    pid = int((stage / "review.pid").read_text().strip())
    assert pid == state["review"]["pid"]
    assert str(Path(f"/proc/{pid}/exe").resolve()) == NGINX
    assert (
        str(stage / "review-nginx.conf").encode()
        in Path(f"/proc/{pid}/cmdline").read_bytes()
    )
    for name in ("autorecovery.py", "review-nginx.template"):
        shutil.copyfile(str(PAYLOAD / name), str(stage / name))
        (stage / name).chmod(0o600)
    override = (stage / "acceptance.yml").read_text()
    assert override.count("restart: 'no'") == 4
    write(
        stage / "acceptance.yml",
        override.replace("restart: 'no'", "restart: unless-stopped"),
    )
    control.dc(state, "config", "--quiet")
    for service in ("db", "redis", "api", "web"):
        control.run(
            [
                "docker",
                "update",
                "--restart",
                "unless-stopped",
                state["project"] + "-" + service + "-1",
            ]
        )
    spec = importlib.util.spec_from_file_location(
        "boot", str(stage / "autorecovery.py")
    )
    boot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boot)
    boot.existing_storage(state)
    boot.prepare_nginx()
    for name in UNIT_NAMES:
        target = Path("/etc/systemd/system") / name
        shutil.copyfile(str(PAYLOAD / name), str(target))
        target.chmod(0o644)
    control.run(
        ["systemd-analyze", "verify"]
        + [str(Path("/etc/systemd/system") / name) for name in UNIT_NAMES]
    )
    control.run(["firewall-cmd", "--permanent", "--zone=public", "--add-port=8444/tcp"])
    assert set(
        control.run(
            ["firewall-cmd", "--permanent", "--zone=public", "--list-ports"]
        ).stdout.split()
    ) == permanent_before | {"8444/tcp"}
    assert (
        set(
            control.run(
                ["firewall-cmd", "--zone=public", "--list-ports"]
            ).stdout.split()
        )
        == runtime_before
    )
    systemctl("daemon-reload")
    systemctl("enable", *UNIT_NAMES)
    control.run(
        [
            NGINX,
            "-p",
            str(stage) + "/",
            "-c",
            str(evidence / "review-nginx.conf.before"),
            "-s",
            "quit",
        ]
    )
    for _ in range(30):
        if not Path(f"/proc/{pid}").exists():
            break
        time.sleep(1)
    else:
        raise RuntimeError("原独立测试 Nginx 未退出")
    systemctl("start", "iterflow-test-nginx.service")
    wait_ready()
    assert systemctl("is-enabled", *UNIT_NAMES).stdout.split() == ["enabled", "enabled"]
    assert systemctl("is-active", *UNIT_NAMES).stdout.split() == ["active", "active"]
    assert control.production_snapshot() == state["baseline"]
    write(
        evidence / "installation.json",
        {
            "status": "PASS",
            "manifest": manifest,
            "production_baseline_preserved": True,
            "permanent_port_only_added": "8444/tcp",
            "runtime_firewall_unchanged": True,
            "before_containers": before_containers,
        },
    )
    print("AUTORECOVERY_INSTALLATION_AND_ISOLATION_PASS", flush=True)


def rehearse():
    state = control.load()
    assert control.production_snapshot() == state["baseline"]
    stage = Path(state["stage"])
    base = Path(state["evidence"]) / "autorecovery-20261012"
    record = json.loads((base / "installation.json").read_text())
    assert record["status"] == "PASS"
    assert not (base / "rehearsal.json").exists()
    evidence = base / time.strftime("rehearsal-%Y%m%dT%H%M%SZ", time.gmtime())
    evidence.mkdir(mode=0o700)
    control.dc(state, "stop", "-t", "30", "web", "api")
    before = snapshot(state)
    write(evidence / "snapshot-before.json", before)
    dump = control.run(
        [
            "docker",
            "exec",
            state["project"] + "-db-1",
            "mysqldump",
            "--defaults-extra-file=/run/secrets/root-client.cnf",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--set-gtid-purged=OFF",
            "iterflow_acceptance",
        ]
    ).stdout
    assert len(dump) > 1024 and "CREATE TABLE" in dump
    write(evidence / "database-before.sql", dump)
    code = "import sys,tarfile\nwith tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:\n    archive.add('/app/data/uploads',arcname='uploads')\n"
    args = [
        "docker",
        "compose",
        "-p",
        state["project"],
        "--env-file",
        str(stage / "images.env"),
        "-f",
        str(stage / "compose.yml"),
        "-f",
        str(stage / "acceptance.yml"),
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "api",
        "python",
        "-c",
        code,
    ]
    protected_binary(
        args, evidence / "uploads-before.tar", evidence / "protected-commands.log"
    )
    with tarfile.open(str(evidence / "uploads-before.tar")) as archive:
        assert all(
            not m.name.startswith("/") and ".." not in Path(m.name).parts
            for m in archive.getmembers()
        )
    systemctl("stop", "iterflow-test-stack.service")
    stopped = control.run(
        [
            "systemctl",
            "is-active",
            "iterflow-test-nginx.service",
            "iterflow-test-stack.service",
        ],
        allowed_failure=True,
    )
    assert stopped.stdout.split() == ["inactive", "inactive"]
    for service in ("db", "redis", "api", "web"):
        c = json.loads(
            control.run(
                ["docker", "inspect", state["project"] + "-" + service + "-1"]
            ).stdout
        )[0]
        assert not c["State"]["Running"]
    print("TEST_SERVICES_ALL_STOPPED_VOLUMES_PRESERVED", flush=True)
    systemctl("start", "iterflow-test-nginx.service")
    wait_ready()
    control.dc(state, "stop", "-t", "30", "web", "api")
    after = snapshot(state)
    write(evidence / "snapshot-after.json", after)
    assert before == after, "冷启动演练数据或附件变化"
    spec = importlib.util.spec_from_file_location(
        "boot", str(stage / "autorecovery.py")
    )
    boot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boot)
    boot.start_stack()
    systemctl("reload", "iterflow-test-nginx.service")
    wait_ready()
    pid = int(
        systemctl(
            "show", "-p", "MainPID", "--value", "iterflow-test-nginx.service"
        ).stdout.strip()
    )
    assert str(Path(f"/proc/{pid}/exe").resolve()) == NGINX
    assert (
        str(stage / "review-nginx.conf").encode()
        in Path(f"/proc/{pid}/cmdline").read_bytes()
    )
    os.kill(pid, signal.SIGKILL)
    for _ in range(60):
        newpid = int(
            systemctl(
                "show", "-p", "MainPID", "--value", "iterflow-test-nginx.service"
            ).stdout.strip()
        )
        if newpid and newpid != pid:
            break
        time.sleep(1)
    else:
        raise RuntimeError("独立 Nginx 异常退出后未自动恢复")
    wait_ready()
    state = control.load()
    assert state["review"]["pid"] == newpid
    assert state["review"]["managed_by_systemd"]
    assert control.production_snapshot() == state["baseline"]
    containers = {}
    for service in ("db", "redis", "api", "web"):
        c = boot.inspect(state, service)
        old = record["before_containers"][service]
        mounts = sorted(c["Mounts"], key=lambda m: m["Destination"])
        old_mounts = sorted(old["mounts"], key=lambda m: m["Destination"])
        assert (
            c["Id"] == old["id"] and c["Image"] == old["image"] and mounts == old_mounts
        )
        assert c["State"]["Running"] and c["State"]["Health"]["Status"] == "healthy"
        containers[service] = {
            "id": c["Id"],
            "image": c["Image"],
            "restart": "unless-stopped",
            "healthy": True,
        }
    final = {
        "status": "PASS",
        "project": state["project"],
        "units": list(UNIT_NAMES),
        "enabled": True,
        "active": True,
        "cold_start_all_four_services": True,
        "nginx_unexpected_exit_auto_recovered": True,
        "nginx_reload": True,
        "main_pid_before": pid,
        "main_pid_after": newpid,
        "all_database_tables_and_files_unchanged": True,
        "tables_compared": len(before["tables"]),
        "files_compared": len(before["files"]),
        "containers_and_images_and_mounts_preserved": containers,
        "backup": {
            "path": str(evidence),
            "sha256": {
                name: digest(evidence / name)
                for name in ("database-before.sql", "uploads-before.tar")
            },
        },
        "production_baseline_preserved": True,
        "host_reboot_performed": False,
        "docker_firewalld_or_production_services_restarted": False,
        "no_migration_seed_restore": True,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write(evidence / "rehearsal.json", final)
    write(base / "rehearsal.json", final)
    state["autorecovery"] = final
    write(control.STATE, state)
    write(
        stage / "AUTORECOVERY.md",
        "独立测试环境由 iterflow-test-stack.service 与 iterflow-test-nginx.service 开机恢复，容器策略 unless-stopped。已通过全服务冷启动及独立入口异常退出恢复演练，数据库和附件未改变，正式环境保持原样；未重启整台服务器。更新测试容器后用 systemctl reload iterflow-test-nginx 刷新代理地址。定期备份尚未配置。\n",
    )
    print("TEST_COLD_START_DATA_PRESERVATION_AND_NGINX_CRASH_RECOVERY_PASS", flush=True)
    print(json.dumps(final, indent=2), flush=True)


if __name__ == "__main__":
    try:
        assert sys.argv[1] in ("install", "rehearse")
        (install if sys.argv[1] == "install" else rehearse)()
    except Exception:  # noqa: BLE001 -- 失败终止并保留私有证据，不忽略错误。
        state = control.load()
        write(
            Path(state["evidence"]) / "autorecovery-last-failure.log",
            traceback.format_exc(),
        )
        print("OPERATION_FAILED_SEE_PROTECTED_AUTORECOVERY_LOG", flush=True)
        raise SystemExit(1)
