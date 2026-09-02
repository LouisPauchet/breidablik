#!/usr/bin/env python3
"""Checks GitHub Releases for a newer Breidablik version and, if found, downloads and applies
it in place. Written for Phusion Passenger shared hosting, which has no Docker and no CI
runner of its own — this is the "pull" side of deployment there, meant to run from cron (or
by hand over SSH).

Usage:
    python3 scripts/passenger_update.py                 # check, and apply if newer
    python3 scripts/passenger_update.py --check-only     # just report, change nothing
    python3 scripts/passenger_update.py --dry-run        # log what would happen, change nothing

What "apply" does, only once a newer release is confirmed available:
    1. Downloads the release's breidablik-release.tar.gz asset (built by .github/workflows/
       release.yml — includes app/, pyproject.toml, passenger_wsgi.py, alembic.ini, and the
       prebuilt frontend/.output/, since the host has no Node to build it itself).
    2. Backs up those same paths from --app-dir into --backup-dir, restored automatically if
       any step below fails.
    3. Overlays the new files over --app-dir. Anything not in that list — .env, the var/
       avatar uploads directory, a venv, .git — is left completely untouched.
    4. Reinstalls Python dependencies (`pip install -e .`), unless --skip-pip-install.
    5. Runs `alembic upgrade head`, unless --skip-migrate.
    6. Touches tmp/restart.txt so Passenger reloads the app on its next request — not done
       until every step above succeeds, so a failed update never leaves a half-applied,
       about-to-be-reloaded state.
    7. Calls POST /internal/cron/notify-update on the running app so admins get an in-app/push
       notification that the update landed.

Every path/URL/secret below can be set via flag or environment variable (flag wins) so a cron
entry doesn't need to embed them all inline. Run with --help to see every option.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

OVERLAY_PATHS = ["app", "pyproject.toml", "passenger_wsgi.py", "alembic.ini", "frontend/.output"]
DEFAULT_ASSET_NAME = "breidablik-release.tar.gz"


def log(message: str) -> None:
    print(f"[passenger_update] {message}", flush=True)


def read_local_version(app_dir: Path) -> str:
    import tomllib

    pyproject_path = app_dir / "pyproject.toml"
    if not pyproject_path.is_file():
        # No release has ever been installed here yet (a brand-new --app-dir) — treat that as
        # "older than anything published" so the very first run bootstraps the deploy instead
        # of crashing before it gets the chance to.
        return "0.0.0"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def parse_version(version: str) -> tuple:
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts) if parts else (0,)


def _api_request(url: str, token: str | None, accept: str) -> urllib.request.Request:
    request = urllib.request.Request(url, headers={"Accept": accept})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def fetch_latest_release(repo: str, token: str | None) -> dict:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = _api_request(url, token, "application/vnd.github+json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def find_asset(release: dict, asset_name: str) -> dict:
    for asset in release.get("assets", []):
        if asset.get("name") == asset_name:
            return asset
    raise RuntimeError(f"Release {release.get('tag_name')} has no asset named {asset_name!r}")


def download_asset(repo: str, asset_id: int, dest: Path, token: str | None) -> None:
    # The API asset endpoint (not the plain browser_download_url) is used because it's the
    # only one that works for a private repo's release assets when authenticated.
    url = f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}"
    request = _api_request(url, token, "application/octet-stream")
    with urllib.request.urlopen(request, timeout=180) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def extract(archive_path: Path, dest_dir: Path) -> None:
    # filter="data" (PEP 706) rejects absolute paths, `..` traversal, and symlink/hardlink
    # escapes in the archive — without it, a compromised release pipeline (or a
    # man-in-the-middle on the download) could write files anywhere this process can reach,
    # not just under dest_dir. Only degrade this to a warning if you've independently verified
    # the archive's integrity another way — don't silently extract unfiltered.
    if not hasattr(tarfile, "data_filter"):
        raise RuntimeError(
            "This Python interpreter predates tarfile's extraction filters (PEP 706) and "
            "can't safely extract the release archive. Upgrade to Python 3.11.4+ (3.12+ "
            "recommended) — the project's own pyproject.toml already requires >=3.11."
        )
    with tarfile.open(archive_path) as tar:
        tar.extractall(dest_dir, filter="data")


def backup(app_dir: Path, backup_dir: Path) -> None:
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True)
    for rel_path in OVERLAY_PATHS:
        src = app_dir / rel_path
        if not src.exists():
            continue
        dest = backup_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def restore(app_dir: Path, backup_dir: Path) -> None:
    log("Restoring the previous version after a failed step...")
    for rel_path in OVERLAY_PATHS:
        backed_up = backup_dir / rel_path
        target = app_dir / rel_path
        if target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        if backed_up.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            if backed_up.is_dir():
                shutil.copytree(backed_up, target)
            else:
                shutil.copy2(backed_up, target)


def overlay_new_files(extracted_root: Path, app_dir: Path) -> None:
    for rel_path in OVERLAY_PATHS:
        src = extracted_root / rel_path
        if not src.exists():
            raise RuntimeError(f"Release archive is missing expected path: {rel_path}")
        dest = app_dir / rel_path
        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def run_step(description: str, args: list, cwd: Path) -> None:
    log(description)
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        log(result.stdout)
        log(result.stderr)
        raise RuntimeError(f"{description} failed (exit {result.returncode})")


def notify_admins(base_url: str, cron_secret: str, version: str) -> None:
    if not base_url or not cron_secret:
        log("Skipping admin notification (no --base-url/--cron-secret configured).")
        return
    url = base_url.rstrip("/") + "/internal/cron/notify-update"
    body = json.dumps({"version": version}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Cron-Secret": cron_secret},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            log(f"Notified admins of the update ({response.status}).")
    except urllib.error.URLError as exc:
        log(f"Could not notify admins (non-fatal): {exc}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", default=os.environ.get("BREIDABLIK_REPO", "LouisPauchet/breidablik"))
    parser.add_argument(
        "--app-dir",
        default=os.environ.get("BREIDABLIK_APP_DIR", str(Path(__file__).resolve().parent.parent)),
    )
    parser.add_argument("--backup-dir", default=None, help="Defaults to <app-dir>/.update_backup")
    parser.add_argument("--asset-name", default=DEFAULT_ASSET_NAME)
    parser.add_argument(
        "--github-token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="Required for a private repo; also raises the unauthenticated rate limit",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BREIDABLIK_BASE_URL", ""),
        help="Public URL of the running app, used only for the post-update admin notification",
    )
    parser.add_argument("--cron-secret", default=os.environ.get("CRON_SECRET", ""))
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Interpreter for pip install / alembic (defaults to the one running this script — "
        "point this at the venv Passenger actually uses if that's different)",
    )
    parser.add_argument("--skip-pip-install", action="store_true")
    parser.add_argument("--skip-migrate", action="store_true")
    parser.add_argument(
        "--check-only", action="store_true", help="Only report whether an update is available"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Log what an update would do without doing it"
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    app_dir = Path(args.app_dir).resolve()
    backup_dir = Path(args.backup_dir).resolve() if args.backup_dir else app_dir / ".update_backup"

    local_version = read_local_version(app_dir)
    log(f"Current version: {local_version}")

    try:
        release = fetch_latest_release(args.repo, args.github_token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            log(f"No releases published yet for {args.repo} — nothing to update to.")
            return 0
        log(f"GitHub API error fetching the latest release: {exc}")
        return 1
    except urllib.error.URLError as exc:
        log(f"Could not reach GitHub: {exc}")
        return 1

    remote_version = release.get("tag_name", "").lstrip("v")
    log(f"Latest release: {remote_version or '(none published)'}")

    if not remote_version or parse_version(remote_version) <= parse_version(local_version):
        log("Already up to date.")
        return 0

    log(f"Update available: {local_version} -> {remote_version}")
    if args.check_only:
        return 0

    asset = find_asset(release, args.asset_name)

    if args.dry_run:
        log(
            f"[dry-run] Would download asset {asset['name']!r}, back up {OVERLAY_PATHS} to "
            f"{backup_dir}, overlay the new release, reinstall deps, migrate, and touch "
            f"tmp/restart.txt."
        )
        return 0

    with tempfile.TemporaryDirectory(prefix="breidablik-update-") as tmp:
        tmp_path = Path(tmp)
        archive_path = tmp_path / args.asset_name
        log(f"Downloading {asset['name']} ({asset.get('size', '?')} bytes) ...")
        download_asset(args.repo, asset["id"], archive_path, args.github_token)

        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        extract(archive_path, extract_dir)
        extracted_root = extract_dir / "breidablik"

        log(f"Backing up the current release to {backup_dir} ...")
        backup(app_dir, backup_dir)

        try:
            log("Overlaying the new release's files ...")
            overlay_new_files(extracted_root, app_dir)

            if not args.skip_pip_install:
                run_step(
                    "Installing Python dependencies",
                    [args.python, "-m", "pip", "install", "-e", "."],
                    app_dir,
                )

            if not args.skip_migrate:
                run_step(
                    "Running database migrations",
                    [args.python, "-m", "alembic", "upgrade", "head"],
                    app_dir,
                )
        except Exception as exc:
            log(f"Update failed: {exc}")
            restore(app_dir, backup_dir)
            return 1

        restart_file = app_dir / "tmp" / "restart.txt"
        restart_file.parent.mkdir(parents=True, exist_ok=True)
        restart_file.touch()
        log("Touched tmp/restart.txt — Passenger will reload the app on its next request.")

    notify_admins(args.base_url, args.cron_secret, remote_version)
    log(f"Update complete: now on v{remote_version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
