"""
Minecraft Plugin Manager

Automated plugin update management for Minecraft servers (Velocity + Paper).
Manages Bedrock cross-play plugins and Tier 1 infrastructure plugins.

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Claude Code"
__description__ = "Automated Minecraft plugin update manager"

from .updater import MinecraftPluginUpdater
from .config import MANAGED_PLUGINS, SERVERS

__all__ = [
    "MinecraftPluginUpdater",
    "MANAGED_PLUGINS",
    "SERVERS",
]
