"""
Deployment Operations

Handles SSH-based deployment to Pterodactyl servers, including
preflight checks, rollback, and infrastructure compatibility validation.
"""

import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import (
    SERVERS,
    SSH_KEY,
    NODE_HOST,
    NODE_USER,
    DOWNLOADS_DIR,
    DEPLOYMENT_STATE_FILE,
    COMPATIBILITY_MATRIX,
)

logger = logging.getLogger(__name__)


class DeploymentManager:
    """Manages plugin deployment operations"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def run_preflight_checks(self) -> Tuple[bool, List[str]]:
        """
        Run pre-flight safety checks before deployment

        Returns:
            Tuple of (success, issues_list)
        """
        logger.info("\n" + "=" * 70)
        logger.info("Running pre-flight safety checks...")
        logger.info("=" * 70 + "\n")

        issues = []

        # Check 1: SSH connectivity
        try:
            test_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'echo ok'"
            result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=5)
            if "ok" in result.stdout:
                logger.info("✓ SSH connectivity verified")
            else:
                issue = "✗ SSH connection failed - cannot connect to node"
                issues.append(issue)
                logger.error(issue)
        except Exception as e:
            issue = f"✗ SSH connectivity check failed: {e}"
            issues.append(issue)
            logger.error(issue)

        # Check 2: Disk space on node
        try:
            df_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'df -h /var/lib/pterodactyl/volumes | tail -1'"
            result = subprocess.run(df_cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.stdout:
                parts = result.stdout.split()
                if len(parts) >= 5:
                    usage_pct = parts[4].rstrip('%')
                    if int(usage_pct) < 90:
                        logger.info(f"✓ Disk space OK ({usage_pct}% used)")
                    else:
                        issue = f"⚠ Disk space warning: {usage_pct}% used (>90%)"
                        issues.append(issue)
                        logger.warning(issue)
        except Exception as e:
            logger.warning(f"⚠ Could not check disk space: {e}")

        # Check 3: Download directory exists and is writable
        try:
            DOWNLOADS_DIR.mkdir(exist_ok=True)
            test_file = DOWNLOADS_DIR / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            logger.info("✓ Downloads directory writable")
        except Exception as e:
            issue = f"✗ Downloads directory not writable: {e}"
            issues.append(issue)
            logger.error(issue)

        # Check 4: Deployment state file exists
        if DEPLOYMENT_STATE_FILE.exists():
            logger.info("✓ Deployment state file found")
        else:
            issue = "⚠ Deployment state file not found - rollback may not be possible"
            logger.warning(issue)

        if issues:
            logger.error(f"\n✗ Pre-flight checks failed: {len(issues)} issue(s)")
            return False, issues
        else:
            logger.info("\n✓ All pre-flight checks passed")
            return True, []

    def deploy_to_server(self, server_name: str, plugin_name: str, jar_path: Path) -> bool:
        """
        Deploy a plugin JAR to a specific server via SSH

        Args:
            server_name: Target server name
            plugin_name: Plugin name
            jar_path: Local path to JAR file

        Returns:
            True if successful
        """
        server_config = SERVERS[server_name]
        server_uuid = server_config["uuid"]

        # Construct remote paths
        remote_plugins_dir = f"/var/lib/pterodactyl/volumes/{server_uuid}/plugins"
        remote_jar_name = jar_path.name
        remote_jar_path = f"{remote_plugins_dir}/{remote_jar_name}"

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_name = f"{remote_jar_name}.{timestamp}.BAK"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would deploy {plugin_name} to {server_name}")
            logger.info(f"[DRY RUN]   Source: {jar_path}")
            logger.info(f"[DRY RUN]   Dest: {remote_jar_path}")
            return True

        try:
            # Check if plugin already exists and create backup
            check_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'test -f {remote_jar_path} && echo exists || echo new'"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=10)

            if "exists" in result.stdout:
                # Create backup of existing plugin
                backup_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'cp {remote_jar_path} {remote_plugins_dir}/{backup_name}'"
                subprocess.run(backup_cmd, shell=True, check=True, timeout=10)
                logger.info(f"  Backed up existing plugin: {backup_name}")

            # Upload new JAR
            scp_cmd = f"scp -i {SSH_KEY} {jar_path} {NODE_USER}@{NODE_HOST}:{remote_jar_path}"
            subprocess.run(scp_cmd, shell=True, check=True, timeout=30)

            # Set correct permissions
            perms_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'chown 988:988 {remote_jar_path} && chmod 644 {remote_jar_path}'"
            subprocess.run(perms_cmd, shell=True, check=True, timeout=10)

            logger.info(f"  ✓ Deployed to {server_name}: {plugin_name}")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"  ✗ Deployment timeout for {server_name}: {plugin_name}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"  ✗ Deployment failed for {server_name}: {plugin_name} - {e}")
            return False

    def restart_server(self, server_name: str) -> bool:
        """
        Restart a server container via Docker

        Args:
            server_name: Server to restart

        Returns:
            True if successful
        """
        server_uuid = SERVERS[server_name]["uuid"]

        if self.dry_run:
            logger.info(f"[DRY RUN] Would restart {server_name}")
            return True

        try:
            restart_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'docker restart $(docker ps --filter name={server_uuid} -q)'"
            subprocess.run(restart_cmd, shell=True, check=True, timeout=30, capture_output=True)
            logger.info(f"  ✓ Restarted {server_name}")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"  ✗ Restart timeout for {server_name}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"  ✗ Restart failed for {server_name}: {e}")
            return False

    def verify_plugin_loaded(self, server_name: str, plugin_name: str, expected_version: str) -> bool:
        """
        Verify a plugin loaded successfully after deployment

        Args:
            server_name: Server to check
            plugin_name: Plugin to verify
            expected_version: Expected version

        Returns:
            True if verified
        """
        server_uuid = SERVERS[server_name]["uuid"]
        log_path = f"/var/lib/pterodactyl/volumes/{server_uuid}/logs/latest.log"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would verify {plugin_name} loaded on {server_name}")
            return True

        try:
            # Wait a moment for plugin to load
            time.sleep(3)

            # Check latest log for plugin loading
            check_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} \"grep -i 'loaded plugin.*{plugin_name.lower()}' {log_path} | tail -1\""
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=10)

            if result.stdout and plugin_name.lower() in result.stdout.lower():
                logger.info(f"  ✓ Verified {plugin_name} loaded on {server_name}")
                return True
            else:
                logger.warning(f"  ⚠ Could not verify {plugin_name} on {server_name}")
                return False

        except Exception as e:
            logger.warning(f"  ⚠ Verification failed for {plugin_name} on {server_name}: {e}")
            return False

    def rollback_deployment(self) -> bool:
        """
        Rollback to previous plugin versions using .BAK files

        Returns:
            True if successful
        """
        logger.info("\n" + "=" * 70)
        logger.info("Rolling back to previous deployment...")
        logger.info("=" * 70 + "\n")

        if self.dry_run:
            logger.info("[DRY RUN] Would execute rollback")
            return True

        rollback_success = {}

        for server_name, server_config in SERVERS.items():
            server_uuid = server_config["uuid"]
            plugins_dir = f"/var/lib/pterodactyl/volumes/{server_uuid}/plugins"

            logger.info(f"\n{server_name}:")

            try:
                # Find all .BAK files
                find_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'find {plugins_dir} -name \"*.BAK\" -type f | sort -r'"
                result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True, timeout=10)

                if not result.stdout:
                    logger.warning(f"  No .BAK files found - nothing to rollback")
                    continue

                backup_files = result.stdout.strip().split('\n')

                for backup_file in backup_files[:10]:  # Limit to 10 most recent
                    # Extract original filename (remove timestamp and .BAK)
                    original = backup_file.rsplit('.', 2)[0] + '.jar'

                    # Restore backup
                    restore_cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} 'cp {backup_file} {original}'"
                    subprocess.run(restore_cmd, shell=True, check=True, timeout=10)

                    logger.info(f"  ✓ Restored: {os.path.basename(original)}")

                    if server_name not in rollback_success:
                        rollback_success[server_name] = []
                    rollback_success[server_name].append(os.path.basename(original))

            except Exception as e:
                logger.error(f"  ✗ Rollback failed for {server_name}: {e}")
                return False

        # Restart all affected servers
        if rollback_success:
            logger.info("\nRestarting servers after rollback...")
            for server_name in rollback_success.keys():
                self.restart_server(server_name)

            logger.info("\n✓ Rollback completed successfully")
            logger.info("Affected servers:")
            for server_name, plugins in rollback_success.items():
                logger.info(f"  {server_name}: {len(plugins)} plugin(s) rolled back")

            return True
        else:
            logger.warning("\nNo plugins were rolled back")
            return False

    def get_velocity_build_number(self) -> Optional[int]:
        """
        Get current Velocity build number from proxy server

        Returns:
            Build number or None if not found
        """
        proxy_server = None
        for server_name, config in SERVERS.items():
            if config["platform"] == "velocity":
                proxy_server = server_name
                break

        if not proxy_server:
            logger.warning("No Velocity server found in configuration")
            return None

        server_uuid = SERVERS[proxy_server]["uuid"]
        log_path = f"/var/lib/pterodactyl/volumes/{server_uuid}/logs/latest.log"

        try:
            # Extract Velocity version from logs
            cmd = f"ssh -i {SSH_KEY} {NODE_USER}@{NODE_HOST} \"grep 'Booting up Velocity' {log_path} | tail -1\""
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

            if result.stdout:
                # Parse build number from output like: "git-a046f700-b557"
                match = re.search(r'-b(\d+)', result.stdout)
                if match:
                    build_number = int(match.group(1))
                    logger.info(f"Detected Velocity build: {build_number}")
                    return build_number
                else:
                    logger.warning(f"Could not parse Velocity build number from: {result.stdout}")

        except Exception as e:
            logger.warning(f"Failed to check Velocity version: {e}")

        return None

    def check_infrastructure_compatibility(self, plugins_to_deploy: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if current infrastructure supports the plugins being deployed

        Args:
            plugins_to_deploy: List of plugin names to deploy

        Returns:
            Tuple of (compatible, issues_list)
        """
        logger.info("\n" + "=" * 70)
        logger.info("Checking infrastructure compatibility...")
        logger.info("=" * 70 + "\n")

        compatibility_issues = []

        # Check Velocity-dependent plugins
        velocity_build = None
        velocity_plugins = []

        for plugin_name in plugins_to_deploy:
            if plugin_name in COMPATIBILITY_MATRIX:
                requirements = COMPATIBILITY_MATRIX[plugin_name].get("requires", {})

                if "velocity" in requirements:
                    velocity_plugins.append(plugin_name)

                    # Get Velocity build number if we haven't already
                    if velocity_build is None:
                        velocity_build = self.get_velocity_build_number()

                    if velocity_build is None:
                        issue = f"⚠ {plugin_name}: Cannot verify Velocity version (could not read logs)"
                        compatibility_issues.append(issue)
                        logger.warning(issue)
                        continue

                    # Check if Velocity meets minimum build requirement
                    min_build = requirements["velocity"]["min_build"]
                    reason = requirements["velocity"]["reason"]

                    if velocity_build < min_build:
                        issue = (
                            f"✗ {plugin_name}: Requires Velocity build {min_build}+, "
                            f"but detected build {velocity_build}\n"
                            f"  Reason: {reason}\n"
                            f"  Solution: Update Velocity proxy first using ./update-velocity.sh"
                        )
                        compatibility_issues.append(issue)
                        logger.error(issue)
                    else:
                        logger.info(f"✓ {plugin_name}: Compatible with Velocity build {velocity_build} (requires {min_build}+)")

        if compatibility_issues:
            logger.error(f"\n✗ Found {len(compatibility_issues)} compatibility issue(s)")
            logger.error("Cannot proceed with deployment until infrastructure is updated")
            return False, compatibility_issues
        else:
            logger.info("\n✓ All infrastructure compatibility checks passed")
            return True, []
