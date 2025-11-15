"""
Main Update Orchestrator

Coordinates plugin update workflow across API clients and deployment.
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import (
    MANAGED_PLUGINS,
    BEDROCK_PLUGINS,  # Legacy alias
    SERVERS,
    MANIFEST_FILE,
    DEPLOYMENT_STATE_FILE,
    DOWNLOADS_DIR,
    BASE_DIR,
)
from .api_clients import (
    ModrinthAPIClient,
    GeyserAPIClient,
    PluginDownloader,
)
from .deployment import DeploymentManager

logger = logging.getLogger(__name__)


class MinecraftPluginUpdater:
    """Main plugin updater orchestrator"""

    def __init__(self, dry_run: bool = False, force: bool = False):
        """
        Args:
            dry_run: Preview mode - no actual changes
            force: Include SNAPSHOT/dev versions
        """
        self.dry_run = dry_run
        self.force = force
        self.manifest = self.load_manifest()
        self.deployment_state = self.load_deployment_state()
        self.updates_available = {}

        # Initialize components
        self.modrinth_client = ModrinthAPIClient(force_snapshots=force)
        self.geyser_client = GeyserAPIClient()
        self.downloader = PluginDownloader(dry_run=dry_run)
        self.deployer = DeploymentManager(dry_run=dry_run)

    def load_manifest(self) -> dict:
        """Load shared-plugins.json manifest"""
        if not MANIFEST_FILE.exists():
            logger.error(f"Manifest file not found: {MANIFEST_FILE}")
            return {}

        with open(MANIFEST_FILE) as f:
            return json.load(f)

    def load_deployment_state(self) -> dict:
        """Load deployment-state.json"""
        if not DEPLOYMENT_STATE_FILE.exists():
            logger.warning(f"Deployment state file not found: {DEPLOYMENT_STATE_FILE}")
            return {}

        with open(DEPLOYMENT_STATE_FILE) as f:
            return json.load(f)

    def save_manifest(self):
        """Save updated manifest"""
        if self.dry_run:
            logger.info("[DRY RUN] Would save manifest to: %s", MANIFEST_FILE)
            return

        with open(MANIFEST_FILE, 'w') as f:
            json.dump(self.manifest, f, indent=2)
        logger.info("Manifest saved: %s", MANIFEST_FILE)

    def save_deployment_state(self):
        """Save updated deployment state"""
        if self.dry_run:
            logger.info("[DRY RUN] Would save deployment state to: %s", DEPLOYMENT_STATE_FILE)
            return

        with open(DEPLOYMENT_STATE_FILE, 'w') as f:
            json.dump(self.deployment_state, f, indent=2)
        logger.info("Deployment state saved: %s", DEPLOYMENT_STATE_FILE)

    def check_for_updates(self) -> Dict[str, Dict]:
        """
        Check all managed plugins for updates

        Returns:
            Dict of {plugin_name: {current, latest, info}}
        """
        logger.info("=" * 70)
        logger.info("Checking for plugin updates...")
        logger.info("=" * 70)

        updates = {}

        for plugin_name, config in MANAGED_PLUGINS.items():
            logger.info(f"\nChecking: {plugin_name}")

            # Get current version from manifest
            current_version = None
            if plugin_name in self.manifest.get("plugins", {}):
                current_version = self.manifest["plugins"][plugin_name].get("version")

            if not current_version:
                logger.warning(f"  No current version found in manifest")
                continue

            logger.info(f"  Current version: {current_version}")

            # Check for latest version based on source
            latest_info = None
            if config["source"] == "modrinth":
                latest_info = self.modrinth_client.check_updates(config["project_id"])
            elif config["source"] == "geyser":
                latest_info = self.geyser_client.check_updates(config["project"], config["artifact"])
            else:
                logger.warning(f"  Unknown source: {config['source']}")
                continue

            if not latest_info:
                logger.warning(f"  Could not fetch latest version")
                continue

            latest_version = latest_info["version"]
            logger.info(f"  Latest version: {latest_version}")

            # Normalize versions for comparison
            current_normalized = self.downloader.normalize_version(current_version)
            latest_normalized = self.downloader.normalize_version(latest_version)

            # Compare versions
            if current_normalized != latest_normalized or self.force:
                logger.info(f"  → Update available: {current_version} → {latest_version}")
                updates[plugin_name] = {
                    "current": current_version,
                    "latest": latest_version,
                    "info": latest_info
                }
            else:
                logger.info(f"  ✓ Already up to date")

        self.updates_available = updates
        return updates

    def download_all_updates(self, updates: Dict[str, Dict]) -> Dict[str, Path]:
        """
        Download all available updates

        Args:
            updates: Dict from check_for_updates()

        Returns:
            Dict of {plugin_name: download_path}
        """
        logger.info("\n" + "=" * 70)
        logger.info("Downloading updates...")
        logger.info("=" * 70 + "\n")

        downloads = {}

        for plugin_name, update_info in updates.items():
            logger.info(f"Downloading: {plugin_name}")

            info = update_info["info"]
            download_url = info["download_url"]
            filename = info["filename"]
            expected_hash = info.get("hash")
            hash_type = info.get("hash_type", "sha256")

            download_path = self.downloader.download(
                download_url=download_url,
                filename=filename,
                expected_hash=expected_hash,
                hash_type=hash_type
            )

            if download_path:
                downloads[plugin_name] = download_path
                logger.info(f"✓ {plugin_name} downloaded successfully\n")
            else:
                logger.error(f"✗ Failed to download {plugin_name}\n")

        return downloads

    def deploy_all_updates(self, downloads: Dict[str, Path]) -> bool:
        """
        Deploy all downloaded updates to appropriate servers

        Args:
            downloads: Dict of {plugin_name: jar_path}

        Returns:
            True if successful
        """
        # Pre-flight safety checks
        preflight_ok, preflight_issues = self.deployer.run_preflight_checks()
        if not preflight_ok:
            logger.error("\n✗ Deployment aborted due to pre-flight check failures")
            for issue in preflight_issues:
                logger.error(f"  {issue}")
            return False

        # Infrastructure compatibility check
        plugins_to_deploy = list(downloads.keys())
        compatible, compat_issues = self.deployer.check_infrastructure_compatibility(plugins_to_deploy)

        if not compatible:
            logger.error("\n✗ Deployment aborted due to infrastructure compatibility issues")
            for issue in compat_issues:
                logger.error(f"  {issue}")
            return False

        logger.info("\n" + "=" * 70)
        logger.info("Deploying updates to servers...")
        logger.info("=" * 70 + "\n")

        deployment_success = {}
        timestamp = datetime.now(timezone.utc).isoformat()

        # Deploy each plugin to its target servers
        for plugin_name, jar_path in downloads.items():
            plugin_config = MANAGED_PLUGINS[plugin_name]
            platforms = plugin_config["platforms"]

            logger.info(f"Deploying: {plugin_name}")

            # Find servers that need this plugin
            target_servers = []
            for server_name, server_config in SERVERS.items():
                if server_config["platform"] in platforms:
                    target_servers.append(server_name)

            # Deploy to each target server
            success_count = 0
            for server_name in target_servers:
                if self.deployer.deploy_to_server(server_name, plugin_name, jar_path):
                    success_count += 1

                    # Track deployment in state
                    if server_name not in deployment_success:
                        deployment_success[server_name] = []
                    deployment_success[server_name].append(plugin_name)

            if success_count == len(target_servers):
                logger.info(f"  ✓ {plugin_name} deployed to all {success_count} servers\n")
            else:
                logger.error(f"  ✗ {plugin_name} only deployed to {success_count}/{len(target_servers)} servers\n")
                return False

        # Restart all affected servers
        logger.info("\nRestarting servers...")
        for server_name in deployment_success.keys():
            if not self.deployer.restart_server(server_name):
                logger.error(f"Failed to restart {server_name}")
                return False

        # Wait for servers to start and verify plugin loading
        if not self.dry_run:
            logger.info("\nWaiting 30 seconds for servers to start...")
            import time
            time.sleep(30)

            logger.info("\nVerifying plugin loading...")
            for server_name, plugins in deployment_success.items():
                logger.info(f"\n{server_name}:")
                for plugin_name in plugins:
                    latest_version = self.updates_available[plugin_name]["latest"]
                    self.deployer.verify_plugin_loaded(server_name, plugin_name, latest_version)

        # Update deployment state
        if not self.dry_run:
            self.update_deployment_state(deployment_success, timestamp)

            # Commit to git for audit trail
            logger.info("\nCommitting changes to git...")
            self.commit_to_git(deployment_success)

        return True

    def update_deployment_state(self, deployments: Dict[str, List[str]], timestamp: str):
        """
        Update deployment-state.json with new deployment info

        Args:
            deployments: Dict of {server_name: [plugin_names]}
            timestamp: ISO timestamp
        """
        logger.info("\nUpdating deployment state...")

        for server_name, plugins in deployments.items():
            if server_name not in self.deployment_state.get("servers", {}):
                continue

            server_state = self.deployment_state["servers"][server_name]

            for plugin_name in plugins:
                if plugin_name not in self.updates_available:
                    continue

                update_info = self.updates_available[plugin_name]
                latest_version = update_info["latest"]
                current_version = update_info["current"]

                # Update deployed plugin info
                if "deployed_plugins" not in server_state:
                    server_state["deployed_plugins"] = {}

                # Calculate SHA256 of deployed JAR
                jar_path = DOWNLOADS_DIR / update_info["info"]["filename"]
                sha256 = self.downloader.calculate_hash(jar_path, "sha256") if jar_path.exists() else "unknown"

                server_state["deployed_plugins"][plugin_name] = {
                    "version": latest_version,
                    "deployed_at": timestamp,
                    "deployed_by": "minecraft-plugin-manager",
                    "sha256": sha256,
                    "previous_version": current_version,
                    "note": "Automated deployment"
                }

        # Update last_updated timestamp
        self.deployment_state["last_updated"] = timestamp

        # Save updated state
        self.save_deployment_state()
        logger.info("✓ Deployment state updated")

    def commit_to_git(self, deployment_info: Dict) -> bool:
        """
        Commit deployment changes to git for audit trail

        Args:
            deployment_info: Dict of {server_name: [plugin_names]}

        Returns:
            True if successful
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would commit changes to git")
            return True

        try:
            # Change to base directory for git operations
            import os
            original_dir = os.getcwd()
            os.chdir(BASE_DIR)

            # Check if we're in a git repository
            check_git = subprocess.run("git rev-parse --git-dir", shell=True, capture_output=True, timeout=5)
            if check_git.returncode != 0:
                logger.warning("Not in a git repository - skipping git commit")
                os.chdir(original_dir)
                return False

            # Check if there are changes to commit
            status = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True, timeout=5)
            if not status.stdout:
                logger.info("No git changes to commit")
                os.chdir(original_dir)
                return True

            # Stage deployment-state.json
            subprocess.run("git add checksums/deployment-state.json", shell=True, check=True, timeout=5)

            # Create commit message
            plugins_updated = []
            for server_name, plugins in deployment_info.items():
                for plugin_name in plugins:
                    if plugin_name in self.updates_available:
                        update = self.updates_available[plugin_name]
                        plugins_updated.append(f"{plugin_name}: {update['current']} → {update['latest']}")

            commit_msg = f"""Automated deployment: {len(plugins_updated)} plugin(s) updated

{chr(10).join([f"- {p}" for p in plugins_updated])}

Deployed by: minecraft-plugin-manager
Timestamp: {datetime.now(timezone.utc).isoformat()}

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"""

            # Create commit
            commit_cmd = f"git commit -m '{commit_msg}'"
            subprocess.run(commit_cmd, shell=True, check=True, timeout=10)

            logger.info("✓ Changes committed to git")
            os.chdir(original_dir)
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠ Git commit failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"⚠ Git integration error: {e}")
            return False
        finally:
            try:
                os.chdir(original_dir)
            except:
                pass

    def show_status(self):
        """Display current plugin versions from deployment state"""
        logger.info("=" * 70)
        logger.info("Current Plugin Deployment Status")
        logger.info("=" * 70 + "\n")

        if not self.deployment_state.get("servers"):
            logger.warning("No deployment state found")
            return

        last_updated = self.deployment_state.get("last_updated", "unknown")
        logger.info(f"Last Updated: {last_updated}\n")

        for server_name, server_info in self.deployment_state["servers"].items():
            logger.info(f"{server_name}:")
            logger.info(f"  Platform: {server_info.get('platform', 'unknown')}")
            logger.info(f"  UUID: {server_info.get('uuid', 'unknown')}")

            if "infrastructure" in server_info:
                logger.info("  Infrastructure:")
                for infra_name, infra_info in server_info["infrastructure"].items():
                    version = infra_info.get("version", "unknown")
                    deployed_at = infra_info.get("deployed_at", "unknown")
                    logger.info(f"    {infra_name}: {version} (deployed: {deployed_at})")

            if "deployed_plugins" in server_info:
                logger.info("  Plugins:")
                for plugin_name, plugin_info in sorted(server_info["deployed_plugins"].items()):
                    version = plugin_info.get("version", "unknown")

                    # Check if this plugin is managed by the tool
                    is_managed = plugin_name in MANAGED_PLUGINS
                    managed_marker = "🔧" if is_managed else "  "

                    logger.info(f"    {managed_marker} {plugin_name}: {version}")

            logger.info("")

        # Summary of managed plugins
        managed_count = len([p for p in MANAGED_PLUGINS.keys()])
        logger.info(f"Managed Plugins: {managed_count}")
        logger.info("  🔧 = Managed by this tool\n")

    def check_version_consistency(self) -> Dict[str, List[Dict]]:
        """
        Check for version drift between similar servers

        Returns:
            Dict of {plugin_name: [inconsistency_info]}
        """
        logger.info("=" * 70)
        logger.info("Checking version consistency across servers...")
        logger.info("=" * 70)

        inconsistencies = {}

        # Group servers by platform type
        platforms = {}
        for server_name, server_config in SERVERS.items():
            platform = server_config["platform"]
            if platform not in platforms:
                platforms[platform] = []
            platforms[platform].append(server_name)

        # Check each platform group
        for platform, server_list in platforms.items():
            if len(server_list) < 2:
                logger.info(f"\nPlatform '{platform}': Only 1 server, skipping consistency check")
                continue

            logger.info(f"\nPlatform '{platform}': Checking {len(server_list)} servers")

            # Get deployed plugins for each server in this platform
            server_plugins = {}
            for server_name in server_list:
                if server_name in self.deployment_state.get("servers", {}):
                    deployed = self.deployment_state["servers"][server_name].get("deployed_plugins", {})
                    server_plugins[server_name] = deployed
                else:
                    logger.warning(f"  {server_name}: No deployment state found")
                    server_plugins[server_name] = {}

            # Find all unique plugins across servers in this platform
            all_plugins = set()
            for plugins in server_plugins.values():
                all_plugins.update(plugins.keys())

            # Check each plugin for version consistency
            for plugin_name in sorted(all_plugins):
                versions = {}
                for server_name in server_list:
                    if plugin_name in server_plugins[server_name]:
                        version = server_plugins[server_name][plugin_name].get("version", "unknown")
                        versions[server_name] = version
                    else:
                        versions[server_name] = None

                # Check if all versions match
                unique_versions = set(v for v in versions.values() if v is not None)

                if len(unique_versions) > 1:
                    # Version mismatch found
                    logger.warning(f"  ⚠ DRIFT DETECTED: {plugin_name}")
                    for server_name, version in versions.items():
                        status = "NOT INSTALLED" if version is None else version
                        logger.warning(f"    {server_name}: {status}")

                    if plugin_name not in inconsistencies:
                        inconsistencies[plugin_name] = []

                    inconsistencies[plugin_name].append({
                        "platform": platform,
                        "servers": versions,
                        "unique_versions": list(unique_versions)
                    })

                elif None in versions.values():
                    # Plugin missing on some servers
                    missing_servers = [s for s, v in versions.items() if v is None]
                    installed_version = list(unique_versions)[0] if unique_versions else "unknown"

                    logger.warning(f"  ⚠ MISSING: {plugin_name} (installed: {installed_version})")
                    for server_name in missing_servers:
                        logger.warning(f"    {server_name}: NOT INSTALLED")

                    if plugin_name not in inconsistencies:
                        inconsistencies[plugin_name] = []

                    inconsistencies[plugin_name].append({
                        "platform": platform,
                        "servers": versions,
                        "unique_versions": list(unique_versions),
                        "missing": missing_servers
                    })

        return inconsistencies
