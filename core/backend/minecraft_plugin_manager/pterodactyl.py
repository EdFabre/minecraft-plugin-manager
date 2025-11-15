"""
Pterodactyl API Client

Handles communication with Pterodactyl panel for server discovery and management.
"""

import logging
import re
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class PterodactylClient:
    """Client for Pterodactyl Panel API"""

    def __init__(self, panel_url: str, api_key: str):
        """
        Initialize Pterodactyl API client

        Args:
            panel_url: Base URL of Pterodactyl panel (e.g., https://panel.example.com)
            api_key: API key (client or application key)
        """
        self.panel_url = panel_url.rstrip('/')
        self.api_key = api_key

        # Determine if this is a client or application key
        self.is_client_key = api_key.startswith('ptlc_')
        self.is_application_key = api_key.startswith('ptla_')

        if not (self.is_client_key or self.is_application_key):
            logger.warning("API key doesn't start with ptlc_ or ptla_ - may be invalid format")

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make GET request to API

        Args:
            endpoint: API endpoint (without /api prefix)
            params: Query parameters

        Returns:
            JSON response as dict
        """
        # Use appropriate base path based on key type
        if self.is_client_key:
            base_path = '/api/client'
        else:
            base_path = '/api/application'

        url = f"{self.panel_url}{base_path}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def list_servers(self, filter_tag: Optional[str] = None,
                     filter_node: Optional[str] = None) -> List[Dict]:
        """
        List all servers accessible via API

        Args:
            filter_tag: Optional tag to filter servers
            filter_node: Optional node name to filter servers

        Returns:
            List of server information dicts
        """
        logger.info("Fetching servers from Pterodactyl panel...")

        servers = []
        page = 1

        while True:
            try:
                data = self._get('/servers', params={'page': page})

                for server in data.get('data', []):
                    attributes = server.get('attributes', {})

                    # Apply filters
                    if filter_tag:
                        tags = attributes.get('tags', [])
                        if filter_tag not in tags:
                            continue

                    if filter_node:
                        node = attributes.get('node', '')
                        if node != filter_node:
                            continue

                    servers.append(attributes)

                # Check if there are more pages
                meta = data.get('meta', {})
                pagination = meta.get('pagination', {})

                if pagination.get('current_page') >= pagination.get('total_pages', 0):
                    break

                page += 1

            except Exception as e:
                logger.error(f"Failed to fetch servers page {page}: {e}")
                break

        logger.info(f"Found {len(servers)} server(s)")
        return servers

    def get_server_details(self, server_id: str) -> Dict:
        """
        Get detailed information about a specific server

        Args:
            server_id: Server UUID or identifier

        Returns:
            Server details dict
        """
        logger.info(f"Fetching details for server: {server_id}")

        try:
            data = self._get(f'/servers/{server_id}')
            return data.get('attributes', {})
        except Exception as e:
            logger.error(f"Failed to get server details for {server_id}: {e}")
            raise

    def detect_platform(self, server: Dict) -> Optional[str]:
        """
        Detect server platform (velocity, paper, spigot) from server configuration

        Args:
            server: Server attributes dict from API

        Returns:
            Platform name or None if cannot detect
        """
        # Try to detect from server name
        name = server.get('name', '').lower()

        if 'velocity' in name or 'proxy' in name:
            return 'velocity'
        elif 'paper' in name:
            return 'paper'
        elif 'spigot' in name:
            return 'spigot'
        elif 'lobby' in name or 'game' in name or 'respack' in name:
            # These are typically Paper servers
            return 'paper'

        # Try to detect from startup command if available
        startup = server.get('container', {}).get('startup_command', '')

        if 'velocity' in startup.lower():
            return 'velocity'
        elif 'paper' in startup.lower():
            return 'paper'
        elif 'spigot' in startup.lower():
            return 'spigot'

        # Default to paper for generic Minecraft servers
        logger.warning(f"Could not detect platform for {server.get('name')}, defaulting to 'paper'")
        return 'paper'

    def detect_minecraft_version(self, server: Dict) -> Optional[str]:
        """
        Detect Minecraft version from server configuration

        Args:
            server: Server attributes dict from API

        Returns:
            Minecraft version string or None
        """
        # Try to extract from server description or environment variables
        description = server.get('description', '')

        # Look for version patterns like "1.20.1" or "velocity-3.4.0"
        version_pattern = r'(\d+\.\d+\.\d+)'
        match = re.search(version_pattern, description)

        if match:
            return match.group(1)

        # Try from container environment
        env = server.get('container', {}).get('environment', {})
        minecraft_version = env.get('MINECRAFT_VERSION') or env.get('SERVER_VERSION')

        if minecraft_version:
            return minecraft_version

        return None

    def discover_minecraft_servers(self, filter_tag: Optional[str] = None,
                                   filter_node: Optional[str] = None,
                                   auto_detect_platform: bool = True) -> Dict[str, Dict]:
        """
        Auto-discover Minecraft servers and build configuration

        Args:
            filter_tag: Optional tag to filter servers
            filter_node: Optional node name to filter servers
            auto_detect_platform: Auto-detect server platform

        Returns:
            Dict of {server_name: server_config} suitable for config.yaml
        """
        logger.info("=" * 70)
        logger.info("Auto-discovering Minecraft servers from Pterodactyl...")
        logger.info("=" * 70)

        servers = self.list_servers(filter_tag=filter_tag, filter_node=filter_node)

        discovered = {}

        for server in servers:
            server_id = server.get('identifier') or server.get('uuid')
            server_name = server.get('name', '').lower().replace(' ', '-')

            # Skip if not a Minecraft server
            if not any(keyword in server_name for keyword in ['minecraft', 'mc', 'proxy', 'lobby', 'game', 'velocity', 'paper', 'spigot']):
                logger.debug(f"Skipping non-Minecraft server: {server_name}")
                continue

            platform = self.detect_platform(server) if auto_detect_platform else 'paper'
            minecraft_version = self.detect_minecraft_version(server)
            node_name = server.get('node', 'unknown')

            config = {
                'uuid': server_id,
                'platform': platform,
                'node': node_name,
                'plugins': []  # To be configured by user
            }

            if minecraft_version:
                config['minecraft_version'] = minecraft_version

            discovered[server_name] = config

            logger.info(f"✓ Discovered: {server_name}")
            logger.info(f"  UUID: {server_id}")
            logger.info(f"  Platform: {platform}")
            logger.info(f"  Node: {node_name}")
            if minecraft_version:
                logger.info(f"  Version: {minecraft_version}")
            logger.info("")

        logger.info(f"✓ Discovered {len(discovered)} Minecraft server(s)")

        return discovered
