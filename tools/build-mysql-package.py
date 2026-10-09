"""Build a frozen Git snapshot, amd64 images, and a credential-free bundle folder."""

import argparse
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--skip-save", action="store_true", help="CI smoke folder, not an offline bundle"
)
args = parser.parse_args()
output = args.output
if not output.is_absolute() or output.exists() or output.is_relative_to(root):
    raise SystemExit("Require a new absolute output directory outside the checkout")
commit = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=root, text=True
).strip()
output.mkdir(parents=True, mode=0o755)


def run(*command):
    subprocess.run(command, check=True)


def inspect(image):
    item = json.loads(subprocess.check_output(["docker", "image", "inspect", image]))[0]
    if (item["Os"], item["Architecture"]) != ("linux", "amd64"):
        raise SystemExit("Image is not linux/amd64: " + image)
    return {
        "tag": image,
        "id": item["Id"],
        "architecture": item["Architecture"],
        "os": item["Os"],
        "registry_digests": item.get("RepoDigests", []),
        "size": item["Size"],
    }


def official_amd64(reference, local_tag):
    manifest = json.loads(
        subprocess.check_output(
            ["docker", "buildx", "imagetools", "inspect", reference, "--raw"]
        )
    )
    if "manifests" in manifest:
        candidates = [
            m
            for m in manifest["manifests"]
            if m["platform"].get("architecture") == "amd64"
            and m["platform"].get("os") == "linux"
        ]
        assert len(candidates) == 1
        repository = reference.rsplit(":", 1)[0]
        pinned = repository + "@" + candidates[0]["digest"]
        run("docker", "pull", pinned)
        run("docker", "tag", pinned, local_tag)
    else:
        # MySQL 5.7.44 is a single amd64 manifest. Preserve any existing tag.
        try:
            inspect(reference)
        except subprocess.CalledProcessError:
            run("docker", "pull", "--platform", "linux/amd64", reference)
        run("docker", "tag", reference, local_tag)
    return inspect(local_tag)


with tempfile.TemporaryDirectory(prefix="iterflow-mysql57-build-") as directory:
    source = Path(directory)
    archive = subprocess.check_output(
        ["git", "archive", commit, "backend", "frontend", "deploy/mysql57"], cwd=root
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(source, filter="data")
    tags = {
        "api": "iterflow-api:mysql57-" + commit[:12],
        "web": "iterflow-web:mysql57-" + commit[:12],
        "redis": "iterflow-mysql57-redis:8.2.2-amd64",
        "mysql_client": "iterflow-mysql57-client:5.7.44-amd64",
    }
    for service in ("api", "web"):
        context = source / ("backend" if service == "api" else "frontend")
        run(
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            tags[service],
            str(context),
        )
    images = [inspect(tags[service]) for service in ("api", "web")]
    images.append(official_amd64("redis:8.2.2-alpine3.22", tags["redis"]))
    images.append(official_amd64("mysql:5.7.44", tags["mysql_client"]))
    # Only frozen, tracked deployment templates; real .env/cnf/CA/dumps never copied.
    for path in (source / "deploy/mysql57").rglob("*"):
        if path.is_file() and path.name != ".gitignore":
            target = output / path.relative_to(source / "deploy/mysql57")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            target.chmod(path.stat().st_mode & 0o777)
    (output / "images.env").write_text(
        f"API_IMAGE={tags['api']}\nWEB_IMAGE={tags['web']}\nREDIS_IMAGE={tags['redis']}\n"
        f"MYSQL_CLIENT_IMAGE={tags['mysql_client']}\nBUILD_SHA={commit}\n"
        "MYSQL_DATABASE_NAME=iterflow\nAPI_PORT=8000\nWEB_PORT=8080\nWEB_BIND_HOST=127.0.0.1\n"
    )
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "source_commit": commit,
                "platform": "linux/amd64",
                "images": images,
                "offline_images": not args.skip_save,
                "remote_verified": False,
            },
            indent=2,
        )
        + "\n"
    )
    if not args.skip_save:
        run("docker", "save", "-o", str(output / "images.tar"), *tags.values())
print(
    "Bundle folder built; requires actual startup verification before final packaging:",
    output,
)
