"""Exercise actual amd64 bundle images, only against the dedicated local proof DB."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pymysql
from sqlalchemy.engine import URL

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--bundle", type=Path, required=True)
parser.add_argument("--portable", action="store_true")
args = parser.parse_args()
bundle = args.bundle.resolve()
manifest = json.loads((bundle / "manifest.json").read_text())
container = (
    "iterflow-mysql57-portable-db" if args.portable else "iterflow-mysql57-proof-db"
)
db_project = "iterflow-mysql57-portable" if args.portable else "iterflow-mysql57-proof"
test_port = 57358 if args.portable else 57357
info = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]
assert info["Config"]["Labels"]["com.docker.compose.project"] == db_project
assert info["Config"]["Image"] == "mysql:5.7.44" and info["State"]["Running"]
password = (root / "tools/mysql57-proof/.env").read_text().strip().split("=", 1)[1]
admin = pymysql.connect(
    host="127.0.0.1", port=test_port, user="root", password=password, autocommit=True
)
suffix = uuid4().hex[:12]
db_name = "iterflow_mysql57_pkg_" + suffix
migration_user, runtime_user = "iterflow_mig_" + suffix, "iterflow_run_" + suffix
migration_password, runtime_password = secrets.token_hex(24), secrets.token_hex(24)
project = "iterflow-mysql57-package-" + suffix
admin_name, admin_password = "pkg-admin", secrets.token_hex(24)
proof = {
    "status": "FAIL",
    "source_commit": manifest["source_commit"],
    "platform": "linux/amd64",
    "scope": "isolated local empty database, synthetic accounts and separate volumes only",
    "remote_verified": False,
    "validation_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip(),
    "proxy_readiness_probes": [],
}


def wait_proxy(client, headers):
    """Readiness probes only; business writes and persistence checks never retry."""
    deadline = time.monotonic() + 30
    statuses = []
    while True:
        try:
            response = client.get("/api/v1/auth/me", headers=headers, timeout=3)
            status = response.status_code
        except httpx.TransportError:
            status = "transport-unavailable"
        statuses.append(status)
        if status == 200:
            proof["proxy_readiness_probes"].append(statuses)
            return
        assert status in (502, 503, 504, "transport-unavailable"), (
            f"Unexpected readiness HTTP {status}"
        )
        assert time.monotonic() < deadline, (
            f"Proxy readiness deadline exceeded: {statuses}"
        )
        time.sleep(0.25)


def sql(statement, parameters=()):
    with admin.cursor() as cursor:
        cursor.execute(statement, parameters)
        return cursor.fetchall()


def restore_package(stage, dump, files, headers, requirement_id, file_id):
    """Restore only into another newly created local test DB and new volumes."""
    restored = db_name + "_restore"
    restore_project = project + "-restore"
    sql(f"CREATE DATABASE `{restored}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
    sql(f"GRANT ALL PRIVILEGES ON `{restored}`.* TO %s@'%%'", (migration_user,))
    restore_stage = stage / "restore"
    restore_stage.mkdir(mode=0o700)
    for name in (
        "compose.yml",
        "images.env",
        ".env.runtime",
        ".env.migration",
        "mysql-client.cnf",
        "test-network.yml",
    ):
        shutil.copy2(stage / name, restore_stage / name)
    shutil.copytree(stage / "tls", restore_stage / "tls")
    for name in ("images.env", ".env.runtime", ".env.migration"):
        path = restore_stage / name
        path.write_text(
            path.read_text()
            .replace(db_name, restored)
            .replace("API_PORT=57300", "API_PORT=57301")
            .replace("WEB_PORT=57380", "WEB_PORT=57381")
        )
    # A restore helper belongs only to this disposable test project. The shipped
    # backup service keeps its read-only attachment mount; `compose run -v` does
    # not reliably override the inherited mount's access mode.
    (restore_stage / "restore-only.yml").write_text(
        "services:\n"
        "  storage-restore:\n"
        "    image: ${API_IMAGE}\n"
        "    platform: linux/amd64\n"
        "    profiles: [ops]\n"
        '    entrypoint: [python, -c, "import sys,tarfile; '
        "tarfile.open(fileobj=sys.stdin.buffer,mode='r|').extractall('/app/data',filter='data')\"]\n"
        "    volumes: [uploads:/app/data/uploads]\n"
        "    security_opt: [no-new-privileges:true]\n"
        "    cap_drop: [ALL]\n"
    )
    compose = [
        "docker",
        "compose",
        "-p",
        restore_project,
        "--env-file",
        str(restore_stage / "images.env"),
        "-f",
        str(restore_stage / "compose.yml"),
        "-f",
        str(restore_stage / "test-network.yml"),
        "-f",
        str(restore_stage / "restore-only.yml"),
    ]

    def dc(*arguments, **kwargs):
        return subprocess.run([*compose, *arguments], check=True, **kwargs)

    try:
        dc(
            "--profile",
            "ops",
            "run",
            "--rm",
            "-T",
            "--entrypoint",
            "mysql",
            "client",
            "--defaults-extra-file=/run/secrets/mysql-client.cnf",
            restored,
            input=dump,
        )
        for (table,) in sql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
            (restored,),
        ):
            rights = (
                "SELECT"
                if table in {"alembic_version", "iterflow_file_key_node"}
                else "SELECT, INSERT, UPDATE, DELETE"
            )
            sql(f"GRANT {rights} ON `{restored}`.`{table}` TO %s@'%%'", (runtime_user,))
        dc(
            "--profile",
            "ops",
            "run",
            "--rm",
            "-T",
            "storage-restore",
            input=files,
        )
        dc(
            "--profile",
            "init",
            "run",
            "--rm",
            "migrate",
            "python",
            "-m",
            "app.cli.mysql_preflight",
        )
        dc("up", "-d", "--wait", "--wait-timeout", "300", "redis", "api", "web")
        with httpx.Client(base_url="http://127.0.0.1:57381", timeout=30) as client:
            download = f"/api/v1/files/{file_id}/download"
            assert client.get(download).status_code == 401
            assert (
                client.get(download, headers=headers).content == b"package attachment"
            )
            requirement = client.get(
                f"/api/v1/requirements/{requirement_id}", headers=headers
            ).json()
            assert (
                requirement["status"] == "ONLINE"
                and requirement["current_version_id"] is not None
            )
            uploaded = client.post(
                "/api/v1/files",
                headers=headers,
                files={
                    "file": (
                        "after-restore.txt",
                        b"restored function writes",
                        "text/plain",
                    )
                },
            )
            assert uploaded.status_code == 200, uploaded.text
            new_file = uploaded.json()["id"]
            assert (
                client.get(
                    f"/api/v1/files/{new_file}/download", headers=headers
                ).content
                == b"restored function writes"
            )
            assert (
                client.delete(f"/api/v1/files/{new_file}", headers=headers).status_code
                == 204
            )
        assert (
            sql(
                "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=%s",
                (restored,),
            )[0][0]
            == 68
        )
        dc("stop", "api")
        post_dump = dc(
            "--profile", "ops", "run", "--rm", "-T", "client", stdout=subprocess.PIPE
        ).stdout
        return {
            "package_isolated_restore": True,
            "restored_guard_triggers": 68,
            "restored_function_runtime_upload": True,
            "package_post_restore_backup_sha256": hashlib.sha256(post_dump).hexdigest(),
        }
    finally:
        dc("down", "-v", "--remove-orphans")
        sql(f"DROP DATABASE `{restored}`")


assert sql("SELECT VERSION()")[0][0] == ("5.7.44-log" if args.portable else "5.7.44")
if args.portable:
    assert sql("SELECT @@GLOBAL.innodb_large_prefix, @@GLOBAL.innodb_strict_mode")[
        0
    ] == (0, 0)
proof["database_profile"] = db_project
proof["global_innodb_settings"] = list(
    sql("SELECT @@GLOBAL.innodb_large_prefix, @@GLOBAL.innodb_strict_mode")[0]
)
sql(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
for user, secret in [
    (migration_user, migration_password),
    (runtime_user, runtime_password),
]:
    sql("CREATE USER %s@'%%' IDENTIFIED BY %s", (user, secret))
sql(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO %s@'%%'", (migration_user,))
sql("GRANT SELECT ON mysql.proc TO %s@'%%'", (migration_user,))

try:
    staging_root = root / "data/mysql57-package-smoke"
    staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=staging_root) as directory:
        stage = Path(directory)
        for name in ("compose.yml", "images.env", "tls"):
            source = bundle / name
            if source.is_dir():
                shutil.copytree(source, stage / name)
            else:
                shutil.copyfile(source, stage / name)
        image_env = (stage / "images.env").read_text()
        image_env = image_env.replace(
            "MYSQL_DATABASE_NAME=iterflow", "MYSQL_DATABASE_NAME=" + db_name
        )
        image_env = image_env.replace("API_PORT=8000", "API_PORT=57300").replace(
            "WEB_PORT=8080", "WEB_PORT=57380"
        )
        image_env += f"BACKUP_UID={os.getuid()}\nBACKUP_GID={os.getgid()}\n"
        (stage / "images.env").write_text(image_env)
        common = (
            "REDIS_URL=redis://redis:6379/0\nJWT_SECRET=" + secrets.token_hex(32) + "\n"
        )
        common += "APP_ENV=production\nALLOWED_HOSTS=127.0.0.1,localhost\nCORS_ORIGINS=\nENABLE_API_DOCS=false\nSTORAGE_DRIVER=local\n"
        for name, user, secret in [
            (".env.migration", migration_user, migration_password),
            (".env.runtime", runtime_user, runtime_password),
        ]:
            url = URL.create(
                "mysql+pymysql",
                username=user,
                password=secret,
                host=container,
                port=3306,
                database=db_name,
                query={"charset": "utf8mb4"},
            )
            content = (
                "DATABASE_URL="
                + url.render_as_string(hide_password=False)
                + "\n"
                + common
            )
            if name == ".env.migration":
                content += f"INIT_ADMIN_USERNAME={admin_name}\nINIT_ADMIN_PASSWORD={admin_password}\n"
            (stage / name).write_text(content)
            (stage / name).chmod(0o600)
        (stage / "mysql-client.cnf").write_text(
            f"[client]\nhost={container}\nuser={migration_user}\npassword={migration_password}\ndefault-character-set=utf8mb4\n"
        )
        (stage / "mysql-client.cnf").chmod(0o600)
        (stage / "test-network.yml").write_text(
            "services:\n"
            + "".join(
                f"  {service}:\n    networks: [default, proof]\n"
                for service in ("api", "migrate", "seed", "client")
            )
            + f"networks:\n  proof:\n    external: true\n    name: {db_project}_default\n"
        )
        compose = [
            "docker",
            "compose",
            "-p",
            project,
            "--env-file",
            str(stage / "images.env"),
            "-f",
            str(stage / "compose.yml"),
            "-f",
            str(stage / "test-network.yml"),
        ]

        def dc(*arguments, **kwargs):
            return subprocess.run([*compose, *arguments], check=True, **kwargs)

        try:
            dc("config", "--quiet")
            dc(
                "--profile",
                "init",
                "run",
                "--rm",
                "migrate",
                "python",
                "-m",
                "app.cli.mysql_preflight",
                "--empty",
            )
            dc("--profile", "init", "run", "--rm", "migrate")
            dc(
                "--profile",
                "init",
                "run",
                "--rm",
                "migrate",
                "python",
                "-m",
                "app.cli.mysql_preflight",
            )
            for (table,) in sql(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
                (db_name,),
            ):
                rights = (
                    "SELECT"
                    if table in {"alembic_version", "iterflow_file_key_node"}
                    else "SELECT, INSERT, UPDATE, DELETE"
                )
                sql(
                    f"GRANT {rights} ON `{db_name}`.`{table}` TO %s@'%%'",
                    (runtime_user,),
                )
            dc("--profile", "init", "run", "--rm", "seed")
            assert sql(f"SELECT COUNT(*) FROM `{db_name}`.sys_user")[0][0] == 1
            for table in (
                "rd_feedback",
                "rd_requirement",
                "rd_version",
                "rd_release",
                "sys_file",
            ):
                assert sql(f"SELECT COUNT(*) FROM `{db_name}`.`{table}`")[0][0] == 0
            dc("up", "-d", "--wait", "--wait-timeout", "300", "redis", "api", "web")
            with httpx.Client(base_url="http://127.0.0.1:57380", timeout=30) as client:
                assert client.get("/").status_code == 200
                assert httpx.get("http://127.0.0.1:57300/ready").status_code == 200
                health = httpx.get("http://127.0.0.1:57300/health").json()
                assert health["build_sha"] == manifest["source_commit"]

                def request(method, path, headers=None, expected=200, **kwargs):
                    response = client.request(
                        method, "/api/v1" + path, headers=headers, **kwargs
                    )
                    assert response.status_code == expected, (
                        f"{method} {path}: HTTP {response.status_code}"
                    )
                    return response

                def sign_in(username, secret):
                    data = request(
                        "POST",
                        "/auth/login",
                        json={"username": username, "password": secret},
                    ).json()
                    return {"Authorization": "Bearer " + data["access_token"]}

                def change_password(headers, current):
                    data = request(
                        "POST",
                        "/auth/change-password",
                        headers,
                        json={
                            "current_password": current,
                            "new_password": secrets.token_hex(24),
                        },
                    ).json()
                    return {"Authorization": "Bearer " + data["access_token"]}

                ah = change_password(
                    sign_in(admin_name, admin_password), admin_password
                )
                permissions = request("GET", "/roles/permissions", ah).json()
                role = request(
                    "POST",
                    "/roles",
                    ah,
                    json={
                        "code": "PKG_CHAIN",
                        "name": "部署包验收角色",
                        "data_scope": "ALL",
                        "permission_ids": [p["id"] for p in permissions],
                    },
                ).json()
                user_password = secrets.token_hex(24)
                user = request(
                    "POST",
                    "/users",
                    ah,
                    json={
                        "username": "pkg-user",
                        "display_name": "包验收用户",
                        "password": user_password,
                        "role_ids": [role["id"]],
                    },
                ).json()
                h = change_password(sign_in("pkg-user", user_password), user_password)
                f = request(
                    "POST",
                    "/feedbacks",
                    h,
                    json={
                        "title": "中文包主链",
                        "feedback_type": "NEW_FEATURE",
                        "urgency": "NORMAL",
                        "description": "真实 amd64 镜像主链",
                    },
                ).json()
                f = request(
                    "PATCH",
                    f"/feedbacks/{f['id']}/status",
                    h,
                    json={"status": "ACCEPTED", "revision": f["revision"]},
                ).json()
                r = request(
                    "POST",
                    f"/feedbacks/{f['id']}/convert",
                    h,
                    json={
                        "type": "CREATE_NEW",
                        "revision": f["revision"],
                        "requirement_title": "包需求",
                        "requirement_type": "FEATURE",
                        "priority": "P2",
                        "description": "发布验证",
                    },
                ).json()
                old_revision = r["revision"]
                r = request(
                    "PATCH",
                    f"/requirements/{r['id']}",
                    h,
                    json={
                        "owner_id": user["id"],
                        "priority": "P1",
                        "revision": old_revision,
                    },
                ).json()
                stale = request(
                    "PATCH",
                    f"/requirements/{r['id']}",
                    ah,
                    expected=409,
                    json={"priority": "P3", "revision": old_revision},
                ).json()
                assert stale["code"] == 40910
                v = request(
                    "POST",
                    "/versions",
                    h,
                    json={"version_no": "PKG-" + suffix, "name": "包版本"},
                ).json()
                v = request(
                    "POST",
                    f"/versions/{v['id']}/requirements",
                    h,
                    json={
                        "requirement_id": r["id"],
                        "revision": r["revision"],
                        "version_revision": v["revision"],
                    },
                ).json()
                r = request("GET", f"/requirements/{r['id']}", h).json()
                for status in ("DEVELOPING", "TESTING", "DONE"):
                    r = request(
                        "PATCH",
                        f"/requirements/{r['id']}/status",
                        h,
                        json={"status": status, "revision": r["revision"]},
                    ).json()
                for status in ("DEVELOPING", "TESTING", "READY"):
                    v = request(
                        "PATCH",
                        f"/versions/{v['id']}/status",
                        h,
                        json={"status": status, "revision": v["revision"]},
                    ).json()
                result = request(
                    "POST",
                    f"/versions/{v['id']}/publish",
                    h,
                    json={
                        "revision": v["revision"],
                        "released_at": datetime.now(UTC).isoformat(),
                        "release_notes": "amd64 包验收",
                    },
                ).json()
                assert result["release"]["result"] == "SUCCESS"
                assert (
                    request("GET", f"/requirements/{r['id']}", h).json()["status"]
                    == "ONLINE"
                )
                assert (
                    request("GET", f"/feedbacks/{f['id']}", h).json()["status"]
                    == "ONLINE"
                )
                assert any(
                    n["entity_id"] == f["id"]
                    for n in request("GET", "/notifications", h).json()
                )
                assert (
                    sql(
                        f"SELECT COUNT(*) FROM `{db_name}`.sys_operation_log WHERE action='VERSION_PUBLISH'"
                    )[0][0]
                    == 1
                )
                file = request(
                    "POST",
                    "/files",
                    h,
                    files={
                        "file": ("package.txt", b"package attachment", "text/plain")
                    },
                ).json()
                download = f"/files/{file['id']}/download"
                request("GET", download, expected=401)
                assert request("GET", download, h).content == b"package attachment"
                for _ in range(3):
                    dc("stop", "web", "api")
                    dc("restart", "redis")
                    dc(
                        "up",
                        "-d",
                        "--wait",
                        "--wait-timeout",
                        "300",
                        "redis",
                        "api",
                        "web",
                    )
                    wait_proxy(client, h)
                    assert request("GET", download, h).content == b"package attachment"
                assert request("GET", download, h).content == b"package attachment"
                assert (
                    request("GET", f"/requirements/{r['id']}", h).json()["status"]
                    == "ONLINE"
                )
                dc("stop", "api")
                dump = dc(
                    "--profile",
                    "ops",
                    "run",
                    "--rm",
                    "-T",
                    "client",
                    stdout=subprocess.PIPE,
                ).stdout
                files = dc(
                    "--profile",
                    "ops",
                    "run",
                    "--rm",
                    "-T",
                    "storage-backup",
                    stdout=subprocess.PIPE,
                ).stdout
                assert (
                    b"CREATE TABLE" in dump
                    and b"domain_rd_version_requirement" in dump
                    and len(files) > 1024
                )
                dc("start", "api")
                dc("up", "-d", "--wait", "--wait-timeout", "300", "redis", "api", "web")
                wait_proxy(client, h)
                dc("stop", "web", "api")
                restored_proof = restore_package(
                    stage, dump, files, h, r["id"], file["id"]
                )
                dc("up", "-d", "--wait", "--wait-timeout", "300", "redis", "api", "web")
                wait_proxy(client, h)
                request("DELETE", f"/files/{file['id']}", h, expected=204)
                request("GET", download, h, expected=404)
                proof.update(
                    status="PASS",
                    mysql_version="5.7.44",
                    empty_migration_seed=True,
                    least_privilege_runtime=True,
                    full_chain_15_steps=True,
                    revision_409=True,
                    notification_audit=True,
                    file_permissions=True,
                    package_restart_persistence=True,
                    package_consecutive_restarts=3,
                    backup_database_sha256=hashlib.sha256(dump).hexdigest(),
                    backup_storage_sha256=hashlib.sha256(files).hexdigest(),
                    **restored_proof,
                )
        except Exception:
            evidence = root / "docs/evidence/mysql57"
            logs = subprocess.run(
                [*compose, "logs", "--no-color", "--tail", "120"],
                capture_output=True,
                check=False,
            )
            (evidence / "package-services-failure.log").write_bytes(
                logs.stdout + logs.stderr
            )
            raise
        finally:
            dc("down", "-v", "--remove-orphans")
finally:
    sql(f"DROP DATABASE `{db_name}`")
    for user in (runtime_user, migration_user):
        sql("DROP USER %s@'%%'", (user,))
    admin.close()
    (bundle / "verification.json").write_text(json.dumps(proof, indent=2) + "\n")
print("Actual amd64 package images and local full chain: PASS (no remote connections)")
