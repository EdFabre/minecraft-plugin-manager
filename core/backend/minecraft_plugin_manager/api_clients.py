"""
API Clients for Plugin Sources

Handles communication with Modrinth and Geyser APIs.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, Optional

import requests

from .config import MODRINTH_API, GEYSER_API, DOWNLOADS_DIR

logger = logging.getLogger(__name__)


class ModrinthAPIClient:
    """Client for Modrinth API"""

    def __init__(self, force_snapshots: bool = False):
        """
        Args:
            force_snapshots: Include SNAPSHOT/dev versions (default: False, releases only)
        """
        self.force_snapshots = force_snapshots

    def check_updates(self, project_id: str) -> Optional[Dict]:
        """
        Check for updates from Modrinth API

        Args:
            project_id: Modrinth project identifier

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

            # Get latest RELEASE version (skip snapshots unless forced)
            latest = None
            for version in versions:
                if version["version_type"] == "release" or self.force_snapshots:
                    latest = version
                    break

            if not latest:
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
