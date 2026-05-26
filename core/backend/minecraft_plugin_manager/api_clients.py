"""
API Clients for Plugin Sources

Handles communication with Modrinth and Geyser APIs.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

from .config import MODRINTH_API, GEYSER_API, DOWNLOADS_DIR

logger = logging.getLogger(__name__)


# Maps a config-side platform name (what users write in config.yaml under
# `platforms:`) to the set of Modrinth `loaders` field values that are
# binary-compatible with it. Modrinth tags one artifact with multiple loaders
# when it works for several (e.g. a Paper plugin is usually tagged
# ["bukkit", "paper", "spigot"]), so an intersection-based filter handles all
# the common shapes without per-platform special cases.
_PLATFORM_TO_LOADERS: Dict[str, Set[str]] = {
    "paper": {"paper", "bukkit", "spigot", "folia"},
    "spigot": {"spigot", "bukkit", "paper"},
    "bukkit": {"bukkit", "paper", "spigot"},
    "folia": {"folia", "paper"},
    "velocity": {"velocity"},
    "bungee": {"bungeecord", "waterfall"},
    "bungeecord": {"bungeecord", "waterfall"},
    "waterfall": {"waterfall", "bungeecord"},
    "fabric": {"fabric"},
    "forge": {"forge"},
    "neoforge": {"neoforge"},
}


def _acceptable_loaders(platforms: Optional[List[str]]) -> Optional[Set[str]]:
    """Resolve config `platforms:` list to the set of Modrinth loaders that
    should be considered compatible. Returns None when no filter should apply
    (caller didn't specify, or specified an unknown platform we'd rather
    leave permissive than guess wrong on).
    """
    if not platforms:
        return None
    accepted: Set[str] = set()
    for p in platforms:
        key = p.lower()
        if key in _PLATFORM_TO_LOADERS:
            accepted.update(_PLATFORM_TO_LOADERS[key])
        else:
            # Unknown platform — fall back to literal match rather than
            # silently dropping it. Logged once at debug so misspellings are
            # discoverable without spamming.
            logger.debug(f"Unknown platform '{p}' — using literal loader match")
            accepted.add(key)
    return accepted


class ModrinthAPIClient:
    """Client for Modrinth API"""

    def __init__(self, force_snapshots: bool = False):
        """
        Args:
            force_snapshots: Include SNAPSHOT/dev versions (default: False, releases only)
        """
        self.force_snapshots = force_snapshots

    def check_updates(self, project_id: str, platforms: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Check for updates from Modrinth API

        Args:
            project_id: Modrinth project identifier
            platforms: Optional list of platform names (as in config.yaml
                `platforms:` — e.g. ["paper"] or ["velocity"]). When given,
                only versions whose Modrinth loaders are compatible with at
                least one of these platforms are considered. Without this,
                multi-loader projects like LuckPerms return whichever artifact
                is newest overall (often -fabric/-neoforge), which is wrong
                for Paper/Velocity deploys.

        Returns:
            Dict with version info, or None if error
        """
        try:
            url = f"{MODRINTH_API}/project/{project_id}/version"
            logger.info(f"Checking Modrinth for updates: {project_id}")

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            versions = response.json()
            if not versions:
                logger.warning(f"No versions found for {project_id}")
                return None

            accepted_loaders = _acceptable_loaders(platforms)

            # Get latest RELEASE version (skip snapshots unless forced) whose
            # loaders intersect the requested platforms. Modrinth returns
            # versions newest-first so a linear scan is sufficient.
            latest = None
            for version in versions:
                if version["version_type"] != "release" and not self.force_snapshots:
                    continue
                if accepted_loaders is not None:
                    version_loaders = set(version.get("loaders", []))
                    if not (version_loaders & accepted_loaders):
                        continue
                latest = version
                break

            if not latest:
                if accepted_loaders is not None:
                    logger.warning(
                        f"No release found for {project_id} matching loaders "
                        f"{sorted(accepted_loaders)} (from platforms={platforms})"
                    )
                else:
                    logger.warning(f"No stable release found for {project_id}")
                return None

            file_info = latest["files"][0]
            hashes = file_info.get("hashes", {})

            # Modrinth may provide sha1 or sha512, not always sha256
            hash_value = hashes.get("sha256") or hashes.get("sha512") or hashes.get("sha1")
            hash_type = "sha256" if "sha256" in hashes else ("sha512" if "sha512" in hashes else "sha1")

            return {
                "version": latest["version_number"],
                "download_url": file_info["url"],
                "filename": file_info["filename"],
                "hash": hash_value,
                "hash_type": hash_type,
                "release_date": latest["date_published"],
                "game_versions": latest["game_versions"]
            }

        except requests.RequestException as e:
            logger.error(f"Failed to check Modrinth for {project_id}: {e}")
            return None


class GeyserAPIClient:
    """Client for Geyser Download API"""

    @staticmethod
    def check_updates(project: str, artifact: str) -> Optional[Dict]:
        """
        Check for updates from Geyser API

        Args:
            project: Project name (geyser, floodgate)
            artifact: Artifact type (velocity, spigot)

        Returns:
            Dict with version info, or None if error
        """
        try:
            # Get latest version
            url = f"{GEYSER_API}/{project}/versions/latest/builds/latest"
            logger.info(f"Checking Geyser API for updates: {project}/{artifact}")

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            version = data["version"]
            build = data["build"]

            # Construct download URL
            download_url = f"{GEYSER_API}/{project}/versions/{version}/builds/{build}/downloads/{artifact}"

            return {
                "version": f"{version}-b{build}",
                "download_url": download_url,
                "filename": f"{project.capitalize()}-{artifact.capitalize()}_{version}-build{build}.jar",
                "build": build,
                "release_date": data.get("time", "")
            }

        except requests.RequestException as e:
            logger.error(f"Failed to check Geyser API for {project}/{artifact}: {e}")
            return None


class PluginDownloader:
    """Handles plugin download and verification"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def download(self, download_url: str, filename: str, expected_hash: Optional[str] = None,
                 hash_type: str = "sha256") -> Optional[Path]:
        """
        Download plugin JAR file with hash verification

        Args:
            download_url: URL to download from
            filename: Filename to save as
            expected_hash: Expected hash value for verification
            hash_type: Hash algorithm (sha256, sha512, sha1)

        Returns:
            Path to downloaded file, or None if failed
        """
        # Ensure downloads directory exists
        DOWNLOADS_DIR.mkdir(exist_ok=True)

        download_path = DOWNLOADS_DIR / filename

        if self.dry_run:
            logger.info(f"[DRY RUN] Would download: {download_url} → {download_path}")
            return download_path

        logger.info(f"Downloading: {filename}")
        logger.info(f"  URL: {download_url}")

        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Verify download
            file_size = download_path.stat().st_size
            logger.info(f"  Downloaded: {file_size:,} bytes")

            # Calculate and verify hash if available
            if expected_hash:
                calculated_hash = self.calculate_hash(download_path, hash_type)

                if calculated_hash == expected_hash:
                    logger.info(f"  ✓ {hash_type.upper()} verified: {calculated_hash[:16]}...")
                else:
                    logger.error(f"  ✗ {hash_type.upper()} mismatch!")
                    logger.error(f"    Expected: {expected_hash}")
                    logger.error(f"    Got:      {calculated_hash}")
                    download_path.unlink()  # Delete corrupted file
                    return None

            return download_path

        except requests.RequestException as e:
            logger.error(f"Download failed for {filename}: {e}")
            if download_path.exists():
                download_path.unlink()
            return None

    @staticmethod
    def calculate_hash(filepath: Path, hash_type: str = "sha256") -> str:
        """
        Calculate hash of a file

        Args:
            filepath: Path to file
            hash_type: Hash algorithm (sha256, sha512, sha1)

        Returns:
            Hexadecimal hash string
        """
        if hash_type == "sha1":
            hash_obj = hashlib.sha1()
        elif hash_type == "sha512":
            hash_obj = hashlib.sha512()
        else:
            hash_obj = hashlib.sha256()

        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                hash_obj.update(byte_block)
        return hash_obj.hexdigest()

    @staticmethod
    def normalize_version(version: str) -> str:
        """
        Normalize version strings for comparison (e.g., 'build981' → 'b981')

        Args:
            version: Version string

        Returns:
            Normalized version string
        """
        # Replace 'build' with 'b' for consistency
        normalized = re.sub(r'-build(\d+)', r'-b\1', version)
        return normalized
