"""
Configuration Loader

Loads and validates configuration from YAML files.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

import yaml

from .config import MANAGED_PLUGINS, SERVERS

logger = logging.getLogger(__name__)


def get_config_paths() -> list[Path]:
    """
    Get list of config file paths to check in priority order

    Returns:
        List of paths to check (first found wins)
    """
    paths = []

    # 1. User config directory
    user_config = Path.home() / ".config" / "minecraft-plugin-manager" / "config.yaml"
    paths.append(user_config)

    # 2. Current working directory
    cwd_config = Path.cwd() / "config.yaml"
    paths.append(cwd_config)

    # 3. Project root (for development)
    project_root = Path(__file__).parent.parent.parent.parent
    project_config = project_root / "config.yaml"
    paths.append(project_config)

    return paths


def load_config(config_path: Optional[Path] = None) -> Dict:
    """
    Load configuration from YAML file

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Configuration dict with servers, managed_plugins, paths, etc.
    """
    config = {
        'servers': SERVERS.copy(),
        'managed_plugins': MANAGED_PLUGINS.copy(),
        'paths': {},
        'pterodactyl': {},
        'ssh': {},
        'compatibility': {},
        'discovery': {
            'enabled': False,
            'filter_by_tag': None,
            'filter_by_node': None,
            'auto_detect_platform': True
        }
    }

    # Determine which config file to use
    if config_path:
        config_files = [config_path]
    else:
        config_files = get_config_paths()

    loaded_from = None
    for path in config_files:
        if path.exists():
            loaded_from = path
            break

    if not loaded_from:
        logger.info("No config file found, using defaults")
        return config

    logger.info(f"Loading configuration from: {loaded_from}")

    try:
        with open(loaded_from, 'r') as f:
            user_config = yaml.safe_load(f)

        if not user_config:
            logger.warning(f"Config file {loaded_from} is empty")
            return config

        # Process environment variable substitution
        user_config = substitute_env_vars(user_config)

        # Merge user config with defaults
        if 'servers' in user_config:
            config['servers'] = user_config['servers']

        if 'managed_plugins' in user_config:
            config['managed_plugins'] = user_config['managed_plugins']

        if 'paths' in user_config:
            config['paths'] = user_config['paths']

        if 'pterodactyl' in user_config:
            config['pterodactyl'] = user_config['pterodactyl']

        if 'ssh' in user_config:
            config['ssh'] = user_config['ssh']

        if 'compatibility' in user_config:
            config['compatibility'] = user_config['compatibility']

        if 'discovery' in user_config:
            config['discovery'].update(user_config['discovery'])

        logger.info(f"✓ Loaded {len(config['servers'])} server(s) from config")
        logger.info(f"✓ Loaded {len(config['managed_plugins'])} plugin(s) from config")

        return config

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML config: {e}")
        logger.info("Falling back to defaults")
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        logger.info("Falling back to defaults")
        return config


def substitute_env_vars(config: Dict) -> Dict:
    """
    Substitute environment variables in config values

    Handles patterns like:
    - ${ENV_VAR}
    - ${ENV_VAR:-default_value}

    Args:
        config: Configuration dict

    Returns:
        Config with environment variables substituted
    """
    import re

    def substitute_value(value):
        if isinstance(value, str):
            # Pattern: ${VAR} or ${VAR:-default}
            pattern = r'\$\{([A-Z_]+)(?::-([^}]*))?\}'

            def replacer(match):
                var_name = match.group(1)
                default_value = match.group(2) or ""
                return os.environ.get(var_name, default_value)

            return re.sub(pattern, replacer, value)
        elif isinstance(value, dict):
            return {k: substitute_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [substitute_value(item) for item in value]
        else:
            return value

    return substitute_value(config)


def validate_config(config: Dict) -> tuple[bool, list[str]]:
    """
    Validate configuration structure

    Args:
        config: Configuration dict to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check required top-level keys
    if 'servers' not in config or not config['servers']:
        errors.append("Config must define at least one server in 'servers' section")

    if 'managed_plugins' not in config or not config['managed_plugins']:
        errors.append("Config must define at least one plugin in 'managed_plugins' section")

    # Validate servers
    for server_name, server_config in config.get('servers', {}).items():
        if 'uuid' not in server_config:
            errors.append(f"Server '{server_name}' missing required 'uuid' field")

        if 'platform' not in server_config:
            errors.append(f"Server '{server_name}' missing required 'platform' field")

        if 'plugins' not in server_config or not isinstance(server_config['plugins'], list):
            errors.append(f"Server '{server_name}' missing 'plugins' list")

        # Check all plugins exist
        for plugin_name in server_config.get('plugins', []):
            if plugin_name not in config.get('managed_plugins', {}):
                errors.append(
                    f"Server '{server_name}' references undefined plugin '{plugin_name}'"
                )

    # Validate managed plugins
    for plugin_name, plugin_config in config.get('managed_plugins', {}).items():
        if 'source' not in plugin_config:
            errors.append(f"Plugin '{plugin_name}' missing required 'source' field")

        source = plugin_config.get('source')

        if source == 'modrinth' and 'project_id' not in plugin_config:
            errors.append(
                f"Plugin '{plugin_name}' uses modrinth source but missing 'project_id'"
            )

        if source == 'geyser':
            if 'project' not in plugin_config:
                errors.append(
                    f"Plugin '{plugin_name}' uses geyser source but missing 'project'"
                )
            if 'artifact' not in plugin_config:
                errors.append(
                    f"Plugin '{plugin_name}' uses geyser source but missing 'artifact'"
                )

    # Validate Pterodactyl config (if present)
    if config.get('pterodactyl'):
        ptero = config['pterodactyl']

        if 'panel_url' not in ptero:
            errors.append("Pterodactyl config missing 'panel_url'")

        if 'api_key' not in ptero and 'api_key_env' not in ptero:
            errors.append(
                "Pterodactyl config must have either 'api_key' or 'api_key_env'"
            )

    # Validate SSH config (if present)
    if config.get('ssh'):
        ssh = config['ssh']

        if 'host' not in ssh:
            errors.append("SSH config missing 'host'")

        if 'user' not in ssh:
            errors.append("SSH config missing 'user'")

        if 'key_path' not in ssh and 'password' not in ssh:
            errors.append(
                "SSH config must have either 'key_path' or 'password'"
            )

    is_valid = len(errors) == 0
    return is_valid, errors


def save_config(config: Dict, config_path: Optional[Path] = None) -> bool:
    """
    Save configuration to YAML file

    Args:
        config: Configuration dict to save
        config_path: Optional path to save to (defaults to user config)

    Returns:
        True if saved successfully
    """
    if not config_path:
        # Default to user config directory
        config_path = Path.home() / ".config" / "minecraft-plugin-manager" / "config.yaml"

    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"✓ Configuration saved to: {config_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False
