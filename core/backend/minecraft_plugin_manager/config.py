"""
Configuration for Minecraft Plugin Manager

Defines all plugins, servers, and infrastructure settings.
"""

from pathlib import Path

# Base directory - resolve to minecraft/ directory (3 levels up from this file)
# projects/minecraft-plugin-manager/core/backend/minecraft_plugin_manager/config.py
# ../../../../../../minecraft/
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "minecraft"
SHARED_PLUGINS_DIR = BASE_DIR / "shared-plugins"
DOWNLOADS_DIR = BASE_DIR / "downloads"
CHECKSUMS_DIR = BASE_DIR / "checksums"
MANIFEST_FILE = SHARED_PLUGINS_DIR / "shared-plugins.json"
DEPLOYMENT_STATE_FILE = CHECKSUMS_DIR / "deployment-state.json"

# SSH Configuration
SSH_KEY = Path.home() / ".ssh" / "id_rsa_root"
NODE_HOST = "192.168.1.71"
NODE_USER = "root"

# API Endpoints
MODRINTH_API = "https://api.modrinth.com/v2"
GEYSER_API = "https://download.geysermc.org/v2/projects"

# Infrastructure compatibility requirements
# Lesson learned from Phase 1: Geyser 2.9.0 requires Velocity b500+ for Adventure library
COMPATIBILITY_MATRIX = {
    "Geyser-Velocity": {
        "requires": {
            "velocity": {
                "min_build": 500,
                "reason": "Geyser 2.9.0+ requires Adventure library API (ComponentFlattener.nestingLimit)"
            }
        }
    },
    "floodgate-velocity": {
        "requires": {
            "velocity": {
                "min_build": 400,
                "reason": "Modern floodgate requires Velocity 3.4.0+"
            }
        }
    }
}

# Managed plugins (Bedrock-critical + Tier 1 infrastructure)
MANAGED_PLUGINS = {
    # Bedrock Cross-Play (Critical)
    "ViaVersion": {
        "source": "modrinth",
        "project_id": "viaversion",
        "platforms": ["velocity", "paper"],
        "tier": "bedrock",
        "critical": True
    },
    "Geyser-Velocity": {
        "source": "geyser",
        "project": "geyser",
        "artifact": "velocity",
        "platforms": ["velocity"],
        "tier": "bedrock",
        "critical": True
    },
    "floodgate-velocity": {
        "source": "geyser",
        "project": "floodgate",
        "artifact": "velocity",
        "platforms": ["velocity"],
        "tier": "bedrock",
        "critical": True
    },
    "floodgate-spigot": {
        "source": "geyser",
        "project": "floodgate",
        "artifact": "spigot",
        "platforms": ["paper"],
        "tier": "bedrock",
        "critical": True
    },

    # Tier 1: Permissions & Infrastructure
    "LuckPerms-Bukkit": {
        "source": "modrinth",
        "project_id": "Vebnzrzj",
        "platforms": ["paper"],
        "tier": "tier1",
        "critical": True
    },
    "LuckPerms-Velocity": {
        "source": "modrinth",
        "project_id": "Vebnzrzj",
        "platforms": ["velocity"],
        "tier": "tier1",
        "critical": True
    },
    "PlaceholderAPI": {
        "source": "modrinth",
        "project_id": "PlaceholderAPI",
        "platforms": ["paper"],
        "tier": "tier1",
        "critical": True
    },
    # Note: ProtocolLib not on Modrinth - would need SpigotMC API or GitHub integration
    # "ProtocolLib": {
    #     "source": "spigot",  # Future: SpigotMC API integration needed
    #     "resource_id": "1997",
    #     "platforms": ["paper"],
    #     "tier": "tier1",
    #     "critical": True
    # }
}

# Legacy alias for backward compatibility
BEDROCK_PLUGINS = MANAGED_PLUGINS

# Server configuration
SERVERS = {
    "minecraft-proxy-0": {
        "uuid": "b57a0213-6e24-429a-9fdd-241f82c397d1",
        "platform": "velocity",
        "plugins": [
            # Bedrock cross-play
            "Geyser-Velocity", "floodgate-velocity", "ViaVersion",
            # Tier 1 infrastructure
            "LuckPerms-Velocity"
        ]
    },
    "minecraft-paper-0": {
        "uuid": "2f3ff273-dc88-4bee-931c-e126d8440605",
        "platform": "paper",
        "plugins": [
            # Bedrock cross-play
            "floodgate-spigot", "ViaVersion",
            # Tier 1 infrastructure
            "LuckPerms-Bukkit", "PlaceholderAPI"
        ]
    },
    "minecraft-lobby-0": {
        "uuid": "4178f798-1bfd-4482-b011-198601dcbe7e",
        "platform": "paper",
        "plugins": [
            # Bedrock cross-play
            "floodgate-spigot", "ViaVersion",
            # Tier 1 infrastructure
            "LuckPerms-Bukkit", "PlaceholderAPI"
        ]
    }
}
