"""
Config Version Manager

Tracks plugin configuration files across servers using git.
Snapshots are pulled from each server via SSH and committed
to the local minecraft/ repository for full change history.
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import (
    BASE_DIR,
    SERVERS,
    NODES,
    SSH_KEY,
    NODE_HOST,
    NODE_USER,
)

logger = logging.getLogger(__name__)

# Where snapshots live inside the minecraft/ git repo
SNAPSHOTS_DIR = BASE_DIR / "config-snapshots"

# Directories/files to exclude when pulling configs (same as backup script)
RSYNC_EXCLUDES = [
    # Binaries and backups
    "*.jar",
    "*.jar.BAK",
    "*.jar.*.BAK",
    "*.manualbak",
    "*.jar.*.manualbak",
    # Libraries and caches
    "*/libs/*",
    "*/lib/*",
    "*/cache/*",
    "*/caches/*",
    # Dynmap (web assets + tiles are huge, colorschemes are static)
    "dynmap/",
    # Paper internal (remapped classes, not config)
    ".paper-remapped/",
    ".paper-nms.jar",
    # Logs
    "*.log",
    "*/logs/*",
    # Git
    "*/.git/*",
    # Database files (binary, not useful in git)
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Large generated files
    "*/skins/*",
    "*/playerdata/*",
    "*/usercache.json",
    "*/whitelist.json",
    "*/banned-*.json",
    "*/ops.json",
]

# Friendly names for display
SERVER_ALIASES = {
    "minecraft-paper-0": "paper-0",
    "minecraft-lobby-0": "lobby-0",
    "minecraft-proxy-0": "proxy-0",
}


class ConfigVersionManager:
    """Manages git-versioned snapshots of plugin configs per server."""

    def __init__(
        self,
        dry_run: bool = False,
        servers: Optional[Dict] = None,
        nodes: Optional[Dict] = None,
    ):
        self.dry_run = dry_run
        self.servers = servers or SERVERS
        self.nodes = nodes or NODES

    def _get_ssh_config(self, server_config: Dict) -> Tuple[str, str, Path]:
        """Get SSH (host, user, key) for a server's node."""
        node_name = server_config.get("node")
        if node_name and node_name in self.nodes:
            nc = self.nodes[node_name]
            return (nc["host"], nc.get("ssh_user", NODE_USER), Path(nc.get("ssh_key", SSH_KEY)).expanduser())
        return (NODE_HOST, NODE_USER, SSH_KEY)

    def _server_alias(self, server_name: str) -> str:
        return SERVER_ALIASES.get(server_name, server_name)

    def _active_servers(self, server_filter: Optional[List[str]] = None) -> Dict[str, Dict]:
        """Return active servers, optionally filtered."""
        result = {}
        for name, cfg in self.servers.items():
            if not cfg.get("active", True):
                continue
            if server_filter:
                alias = self._server_alias(name)
                if name not in server_filter and alias not in server_filter:
                    continue
            result[name] = cfg
        return result

    # ------------------------------------------------------------------
    # snapshot: pull configs from server(s) and commit
    # ------------------------------------------------------------------

    def snapshot(
        self,
        server_filter: Optional[List[str]] = None,
        message: str = "",
        tag: bool = True,
    ) -> bool:
        """
        Pull plugin configs from server(s) and commit to git.

        Args:
            server_filter: Limit to specific server names/aliases
            message: Optional commit message suffix
            tag: Create a dated git tag

        Returns:
            True if successful
        """
        servers = self._active_servers(server_filter)
        if not servers:
            logger.error("No active servers matched the filter")
            return False

        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 70)
        logger.info("Config Snapshot")
        logger.info("=" * 70)

        success_count = 0
        for server_name, server_config in servers.items():
            alias = self._server_alias(server_name)
            if self._pull_configs(server_name, server_config):
                success_count += 1
                logger.info(f"  ✓ {alias}: configs pulled")
            else:
                logger.error(f"  ✗ {alias}: failed to pull configs")

        if success_count == 0:
            logger.error("\n✗ No configs were pulled")
            return False

        # Commit to git
        aliases = [self._server_alias(n) for n in servers]
        servers_str = ", ".join(aliases)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        default_msg = f"Config snapshot: {servers_str} ({timestamp})"
        commit_msg = f"{default_msg}\n\n{message}" if message else default_msg

        if self.dry_run:
            logger.info(f"\n[DRY RUN] Would commit: {default_msg}")
            return True

        committed = self._git_commit(commit_msg)

        if committed and tag:
            tag_name = f"config-{datetime.now().strftime('%Y%m%d-%H%M')}"
            self._git_tag(tag_name)

        logger.info(f"\n✓ Snapshot complete ({success_count} server(s))")
        return True

    def _pull_configs(self, server_name: str, server_config: Dict) -> bool:
        """Pull plugin configs from a single server via rsync."""
        alias = self._server_alias(server_name)
        uuid = server_config["uuid"]
        host, user, key = self._get_ssh_config(server_config)

        remote_plugins = f"/var/lib/pterodactyl/volumes/{uuid}/plugins/"
        local_dir = SNAPSHOTS_DIR / alias
        local_dir.mkdir(parents=True, exist_ok=True)

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would rsync {user}@{host}:{remote_plugins} → {local_dir}/")
            return True

        # Build rsync command
        exclude_args = []
        for pattern in RSYNC_EXCLUDES:
            exclude_args.extend(["--exclude", pattern])

        cmd = [
            "rsync", "-az", "--delete",
            "-e", f"ssh -i {key} -o StrictHostKeyChecking=no -o ConnectTimeout=10",
            *exclude_args,
            f"{user}@{host}:{remote_plugins}",
            f"{local_dir}/",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error(f"  rsync failed for {alias}: {result.stderr.strip()}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"  rsync timeout for {alias}")
            return False
        except Exception as e:
            logger.error(f"  rsync error for {alias}: {e}")
            return False

    # ------------------------------------------------------------------
    # diff: show what changed since last snapshot
    # ------------------------------------------------------------------

    def diff(
        self,
        server_filter: Optional[List[str]] = None,
        since: Optional[str] = None,
        stat_only: bool = False,
    ) -> bool:
        """
        Show config changes since last snapshot or a specific tag/ref.

        Args:
            server_filter: Limit to specific server(s)
            since: Git ref or tag to diff from (default: last commit)
            stat_only: Only show file stats, not full diff

        Returns:
            True if diff was shown
        """
        original_dir = os.getcwd()
        try:
            os.chdir(BASE_DIR)

            # Default: diff working tree against HEAD
            ref = since or "HEAD"

            # Build path filter for specific servers
            paths = []
            if server_filter:
                for name in server_filter:
                    # Try as alias or full name
                    alias = name
                    if name in SERVER_ALIASES:
                        alias = SERVER_ALIASES[name]
                    paths.append(f"config-snapshots/{alias}")
            else:
                paths.append("config-snapshots/")

            logger.info("=" * 70)
            logger.info(f"Config Diff (since {ref})")
            logger.info("=" * 70 + "\n")

            # Check for uncommitted changes in working tree
            stat_cmd = ["git", "diff", "--stat", "--", *paths]
            result = subprocess.run(stat_cmd, capture_output=True, text=True, timeout=10)

            if result.stdout.strip():
                # There are uncommitted changes — show them
                logger.info("Uncommitted changes:\n")
                print(result.stdout)

                if not stat_only:
                    diff_cmd = ["git", "diff", "--", *paths]
                    diff_result = subprocess.run(diff_cmd, capture_output=True, text=True, timeout=30)
                    if diff_result.stdout.strip():
                        print(diff_result.stdout)
            else:
                # No uncommitted changes — show last commit's changes
                stat_cmd = ["git", "log", "-1", "--stat", "--format=Last snapshot: %s (%cr)", "--", *paths]
                result = subprocess.run(stat_cmd, capture_output=True, text=True, timeout=10)

                if result.stdout.strip():
                    print(result.stdout)
                else:
                    logger.info("No config changes detected")

            return True

        except Exception as e:
            logger.error(f"Diff failed: {e}")
            return False
        finally:
            os.chdir(original_dir)

    # ------------------------------------------------------------------
    # restore: restore a config file from a previous snapshot
    # ------------------------------------------------------------------

    def restore(
        self,
        server_name: str,
        config_path: str,
        ref: Optional[str] = None,
    ) -> bool:
        """
        Restore a config file from a previous git snapshot.

        Args:
            server_name: Server alias (e.g., paper-0)
            config_path: Relative path within plugins/ (e.g., ExecutableItems/items/Misc/warp_stone.yml)
            ref: Git ref to restore from (default: HEAD~1)

        Returns:
            True if successful
        """
        alias = server_name
        # Find the full server name
        full_name = None
        for name, cfg in self.servers.items():
            if self._server_alias(name) == alias or name == alias:
                full_name = name
                break

        if not full_name:
            logger.error(f"Server not found: {server_name}")
            return False

        server_config = self.servers[full_name]
        ref = ref or "HEAD~1"

        # Git path within repo
        git_path = f"config-snapshots/{alias}/{config_path}"
        local_path = SNAPSHOTS_DIR / alias / config_path

        original_dir = os.getcwd()
        try:
            os.chdir(BASE_DIR)

            if self.dry_run:
                logger.info(f"[DRY RUN] Would restore {git_path} from {ref}")
                return True

            # Extract file from git history
            show_cmd = ["git", "show", f"{ref}:{git_path}"]
            result = subprocess.run(show_cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logger.error(f"File not found in {ref}: {git_path}")
                logger.error(f"  {result.stderr.strip()}")
                return False

            content = result.stdout

            # Write locally
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(content, encoding="utf-8")
            logger.info(f"✓ Restored locally: {git_path}")

            # Push to server
            uuid = server_config["uuid"]
            host, user, key = self._get_ssh_config(server_config)
            remote_path = f"/var/lib/pterodactyl/volumes/{uuid}/plugins/{config_path}"

            scp_cmd = f"scp -i {key} {local_path} {user}@{host}:{remote_path}"
            subprocess.run(scp_cmd, shell=True, check=True, timeout=30)

            # Fix permissions
            perms_cmd = f"ssh -i {key} {user}@{host} 'chown 988:988 {remote_path}'"
            subprocess.run(perms_cmd, shell=True, check=True, timeout=10)

            logger.info(f"✓ Deployed to server: {remote_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Restore failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return False
        finally:
            os.chdir(original_dir)

    # ------------------------------------------------------------------
    # list_snapshots: show available snapshot tags
    # ------------------------------------------------------------------

    def list_snapshots(self, limit: int = 20) -> List[Dict]:
        """List available config snapshot tags."""
        original_dir = os.getcwd()
        try:
            os.chdir(BASE_DIR)

            cmd = ["git", "tag", "-l", "config-*", "--sort=-creatordate"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if not result.stdout.strip():
                logger.info("No config snapshots found")
                return []

            tags = result.stdout.strip().split("\n")[:limit]
            snapshots = []

            for tag in tags:
                # Get tag date
                date_cmd = ["git", "log", "-1", "--format=%ci", tag]
                date_result = subprocess.run(date_cmd, capture_output=True, text=True, timeout=5)
                date_str = date_result.stdout.strip() if date_result.returncode == 0 else "unknown"

                # Get short commit message
                msg_cmd = ["git", "log", "-1", "--format=%s", tag]
                msg_result = subprocess.run(msg_cmd, capture_output=True, text=True, timeout=5)
                msg = msg_result.stdout.strip() if msg_result.returncode == 0 else ""

                snapshots.append({
                    "tag": tag,
                    "date": date_str,
                    "message": msg,
                })

            return snapshots

        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
            return []
        finally:
            os.chdir(original_dir)

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _git_commit(self, message: str) -> bool:
        """Stage config-snapshots/ and commit."""
        original_dir = os.getcwd()
        try:
            os.chdir(BASE_DIR)

            # Stage all config snapshot changes
            subprocess.run(["git", "add", "config-snapshots/"], check=True, timeout=120)

            # Check if there's anything to commit
            status = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True, timeout=10,
            )
            if status.returncode == 0:
                logger.info("No config changes to commit")
                return False

            subprocess.run(
                ["git", "commit", "-m", message],
                check=True, timeout=120,
            )
            logger.info("✓ Committed config snapshot to git")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"Git commit failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Git error: {e}")
            return False
        finally:
            os.chdir(original_dir)

    def _git_tag(self, tag_name: str) -> bool:
        """Create a lightweight git tag."""
        original_dir = os.getcwd()
        try:
            os.chdir(BASE_DIR)
            subprocess.run(["git", "tag", tag_name], check=True, timeout=5)
            logger.info(f"✓ Tagged: {tag_name}")
            return True
        except subprocess.CalledProcessError:
            logger.warning(f"Tag already exists or failed: {tag_name}")
            return False
        finally:
            os.chdir(original_dir)
