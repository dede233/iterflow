"""仅管理 state.json 指定并被用户保留的独立测试环境，兼容主机 Python 3.6。"""

import ipaddress
import json
import os
import sys
import traceback
from pathlib import Path

CONTROL = Path("/opt/iterflow/acceptance-control/20261012")
sys.path.insert(0, str(CONTROL))
import control

NGINX = "/www/server/nginx/sbin/nginx"
SERVICES = ("db", "redis", "api", "web")


def context():
    state = control.load()
    assert state["retention"]["keep"] and state.get("cleanup_hold")
    stage = Path(state["stage"])
    assert stage.is_dir() and not stage.is_symlink()
    for name in ("compose.yml", "acceptance.yml", "images.env"):
        path = stage / name
        assert path.is_file() and (path.stat().st_mode & 0o777) == 0o600
    return state, stage


def inspect(state, service):
    result = control.run(["docker", "inspect", state["project"] + "-" + service + "-1"])
    container = json.loads(result.stdout)[0]
    assert (
        container["Config"]["Labels"]["com.docker.compose.project"] == state["project"]
    )
    assert container["HostConfig"]["RestartPolicy"]["Name"] == "unless-stopped"
    return container


def existing_storage(state):
    for suffix in ("dbdata", "uploads", "redisdata"):
        name = state["project"] + "_" + suffix
        volume = json.loads(control.run(["docker", "volume", "inspect", name]).stdout)[
            0
        ]
        assert volume["Name"] == name
        assert (
            volume.get("Labels", {}).get("com.docker.compose.project")
            == state["project"]
        )
        mount = Path(volume["Mountpoint"])
        assert mount.is_dir() and not mount.is_symlink()
        if suffix == "dbdata":
            assert (mount / "mysql").is_dir()
            assert (mount / "iterflow_acceptance").is_dir()
    for service in SERVICES:
        inspect(state, service)


def start_stack():
    state, _ = context()
    existing_storage(state)
    control.dc(state, "config", "--quiet")
    control.dc(
        state,
        "up",
        "-d",
        "--no-recreate",
        "--no-build",
        "--pull",
        "never",
        "--wait",
        "--wait-timeout",
        "240",
        *SERVICES,
    )
    for service in SERVICES:
        container = inspect(state, service)
        assert container["State"]["Running"]
        assert container["State"]["Health"]["Status"] == "healthy"
    code = "from app.core.database import engine\nwith engine.connect() as conn:\n    assert engine.dialect.name == 'mysql'\n    assert conn.exec_driver_sql('SELECT DATABASE()').scalar() == 'iterflow_acceptance'\n"
    control.run(
        ["docker", "exec", "-i", state["project"] + "-api-1", "python", "-"], stdin=code
    )
    print("TEST_STACK_HEALTH_AND_DATABASE_TARGET_PASS", flush=True)


def stop_stack():
    state, _ = context()
    existing_storage(state)
    control.dc(state, "stop", "-t", "30", "web", "api", "redis", "db")
    print("TEST_STACK_STOPPED_VOLUMES_PRESERVED", flush=True)


def prepare_nginx():
    state, stage = context()
    for service in SERVICES:
        container = inspect(state, service)
        assert (
            container["State"]["Running"]
            and container["State"]["Health"]["Status"] == "healthy"
        )
    web = inspect(state, "web")
    network = state["project"] + "_default"
    address = web["NetworkSettings"]["Networks"][network]["IPAddress"]
    assert ipaddress.ip_address(address).is_private
    assert (
        control.run(
            ["firewall-cmd", "--zone=public", "--query-port=8444/tcp"]
        ).stdout.strip()
        == "yes"
    )
    template = (stage / "review-nginx.template").read_text()
    assert template.count("@@WEB_IP@@") == 1 and template.count("@@STAGE@@") == 2
    config = template.replace("@@WEB_IP@@", address).replace("@@STAGE@@", str(stage))
    assert config.count("listen 8444 ssl;") == 1 and "listen 8443" not in config
    pending = stage / "review-nginx.pending.conf"
    control.write(pending, config)
    control.run([NGINX, "-t", "-p", str(stage) + "/", "-c", str(pending)])
    pending.replace(stage / "review-nginx.conf")
    return state, stage


def nginx():
    state, stage = prepare_nginx()
    state["review"]["pid"] = os.getpid()
    state["review"]["managed_by_systemd"] = True
    state["review"]["service"] = "iterflow-test-nginx.service"
    control.write(control.STATE, json.dumps(state, ensure_ascii=False, indent=2))
    os.execv(
        NGINX,
        [
            NGINX,
            "-p",
            str(stage) + "/",
            "-c",
            str(stage / "review-nginx.conf"),
            "-g",
            "daemon off;",
        ],
    )


def reload_nginx():
    _state, stage = prepare_nginx()
    pid = int((stage / "review.pid").read_text().strip())
    process = Path("/proc") / str(pid)
    assert str((process / "exe").resolve()) == NGINX
    assert (
        str(stage / "review-nginx.conf").encode() in (process / "cmdline").read_bytes()
    )
    control.run(
        [
            NGINX,
            "-p",
            str(stage) + "/",
            "-c",
            str(stage / "review-nginx.conf"),
            "-s",
            "reload",
        ]
    )
    print("TEST_NGINX_RELOADED", flush=True)


if __name__ == "__main__":
    actions = {
        "start-stack": start_stack,
        "stop-stack": stop_stack,
        "nginx": nginx,
        "reload": reload_nginx,
    }
    try:
        assert len(sys.argv) == 2 and sys.argv[1] in actions
        actions[sys.argv[1]]()
    except Exception:  # noqa: BLE001 -- 最外层只写受保护日志，避免journal泄露错误细节。
        state = control.load()
        control.write(
            Path(state["stage"]) / "autorecovery-last-error.log", traceback.format_exc()
        )
        print("TEST_AUTORECOVERY_FAILED_SEE_PROTECTED_LOG", flush=True)
        raise SystemExit(1)
