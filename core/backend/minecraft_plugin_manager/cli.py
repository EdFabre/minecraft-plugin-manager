"""
Command-Line Interface

Entry point for minecraft-plugin-manager CLI tool.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .updater import MinecraftPluginUpdater
from .deployment import DeploymentManager
from .config import BASE_DIR
from .config_loader import load_config, validate_config, save_config
from .pterodactyl import PterodactylClient

# Logging setup
def setup_logging():
    """Configure logging for CLI"""
    log_file = BASE_DIR / f"minecraft-plugin-manager-{datetime.now().strftime('%Y%m%d%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def run_update_workflow(updater: MinecraftPluginUpdater, check_only: bool = False,
                        download_only: bool = False, deploy: bool = False) -> int:
    """
    Main update workflow execution

    Args:
        updater: MinecraftPluginUpdater instance
        check_only: Only check for updates
        download_only: Download but don't deploy
        deploy: Download and deploy

    Returns:
        Exit code (0 = success)
    """
    logger.info("Minecraft Plugin Manager")
    logger.info("=" * 70)
    logger.info(f"Version: {__version__}")
    logger.info(f"Mode: {'DRY RUN' if updater.dry_run else 'LIVE'}")
    logger.info(f"Force: {updater.force}")
    logger.info("")

    # Step 1: Check for updates
    updates = updater.check_for_updates()

    if not updates:
        logger.info("\n✓ All plugins are up to date!")
        return 0

    logger.info(f"\n{len(updates)} update(s) available:")
    for plugin_name, info in updates.items():
        logger.info(f"  • {plugin_name}: {info['current']} → {info['latest']}")

    # If check-only mode, stop here
    if check_only or updater.dry_run:
        if updater.dry_run:
            logger.info("\n[DRY RUN] Stopping here. Remove --dry-run to download.")
        else:
            logger.info("\nRun with --download to download updates")
        return 0

    # Step 2: Download updates
    downloads = updater.download_all_updates(updates)

    if len(downloads) != len(updates):
        logger.error("\n✗ Not all downloads succeeded. Aborting.")
        return 1

    logger.info("\n✓ All downloads completed successfully!")

    # If download-only mode, stop here
    if download_only:
        logger.info("\nNext steps:")
        logger.info("  1. Review downloaded JARs in downloads/")
        logger.info("  2. Run with --deploy to deploy to servers")
        return 0

    # Step 3: Deploy updates (if deploy mode)
    if deploy:
        if not updater.deploy_all_updates(downloads):
            logger.error("\n✗ Deployment failed!")
            return 1

        logger.info("\n✓ Deployment completed successfully!")
        logger.info("\nRecommended next steps:")
        logger.info("  1. Verify consistency: minecraft-plugin-manager --audit")
        logger.info("  2. Test Bedrock connectivity: mc.haymoed.com:19132")
        return 0

    return 0


def run_init_wizard() -> int:
    """
    Interactive setup wizard to create config.yaml

    Returns:
        Exit code (0 = success)
    """
    logger.info("=" * 70)
    logger.info("Minecraft Plugin Manager - Setup Wizard")
    logger.info("=" * 70)
    logger.info("\nThis wizard will help you create a configuration file.\n")

    config = {}

    # Ask for Pterodactyl credentials
    logger.info("Step 1: Pterodactyl Panel Connection")
    logger.info("-" * 40)
    panel_url = input("Panel URL (e.g., https://panel.example.com): ").strip()

    if panel_url:
        api_key = input("API Key (ptlc_ or ptla_ prefix): ").strip()

        if not api_key:
            logger.warning("No API key provided - skipping Pterodactyl configuration")
        else:
            config['pterodactyl'] = {
                'panel_url': panel_url,
                'api_key': api_key
            }

            # Test connection
            logger.info("\nTesting Pterodactyl connection...")
            try:
                client = PterodactylClient(panel_url, api_key)
                servers = client.list_servers()
                logger.info(f"✓ Connection successful! Found {len(servers)} server(s)")

                # Offer to run discovery
                run_discovery = input("\nRun server discovery now? [Y/n]: ").strip().lower()
                if run_discovery != 'n':
                    discovered = client.discover_minecraft_servers()
                    if discovered:
                        config['servers'] = discovered
                        logger.info(f"\n✓ Discovered {len(discovered)} Minecraft server(s)")

            except Exception as e:
                logger.error(f"✗ Connection failed: {e}")
                logger.info("You can configure this later manually")

    # Ask for SSH details
    logger.info("\nStep 2: SSH Connection (for direct volume access)")
    logger.info("-" * 40)
    ssh_host = input("SSH Host (IP or hostname) [skip to use Pterodactyl API]: ").strip()

    if ssh_host:
        ssh_user = input("SSH User [root]: ").strip() or "root"
        ssh_key_path = input("SSH Key Path [~/.ssh/id_rsa]: ").strip() or "~/.ssh/id_rsa"

        config['ssh'] = {
            'host': ssh_host,
            'user': ssh_user,
            'key_path': ssh_key_path
        }

    # If no servers discovered, ask for manual config
    if 'servers' not in config or not config['servers']:
        logger.info("\nStep 3: Manual Server Configuration")
        logger.info("-" * 40)
        logger.info("No servers discovered. You'll need to configure servers manually.")
        logger.info("Edit the config file after creation to add server definitions.")
        config['servers'] = {}

    # Set managed plugins to defaults
    from .config import MANAGED_PLUGINS
    config['managed_plugins'] = MANAGED_PLUGINS

    # Ask where to save config
    logger.info("\nStep 4: Save Configuration")
    logger.info("-" * 40)
    default_path = Path.home() / ".config" / "minecraft-plugin-manager" / "config.yaml"
    save_path_input = input(f"Save to [{default_path}]: ").strip()
    save_path = Path(save_path_input) if save_path_input else default_path

    # Save config
    if save_config(config, save_path):
        logger.info(f"\n✓ Configuration saved to: {save_path}")
        logger.info("\nNext steps:")
        logger.info("  1. Review the config file and customize as needed")
        logger.info("  2. Run 'minecraft-plugin-manager --status' to verify")
        logger.info("  3. Run 'minecraft-plugin-manager --check' to check for updates")
        return 0
    else:
        logger.error("\n✗ Failed to save configuration")
        return 1


def run_discovery(config: dict = None) -> int:
    """
    Run Pterodactyl server discovery

    Args:
        config: Optional config dict (will load from file if not provided)

    Returns:
        Exit code (0 = success)
    """
    logger.info("=" * 70)
    logger.info("Minecraft Plugin Manager - Server Discovery")
    logger.info("=" * 70)

    # Load config if not provided
    if not config:
        config = load_config()

    # Check for Pterodactyl credentials
    if 'pterodactyl' not in config or not config['pterodactyl']:
        logger.error("\n✗ No Pterodactyl configuration found")
        logger.info("\nRun 'minecraft-plugin-manager --init' to configure Pterodactyl connection")
        return 1

    ptero_config = config['pterodactyl']
    if 'panel_url' not in ptero_config or 'api_key' not in ptero_config:
        logger.error("\n✗ Pterodactyl configuration incomplete")
        logger.info("Missing 'panel_url' or 'api_key' in config file")
        return 1

    # Run discovery
    try:
        logger.info("\nConnecting to Pterodactyl panel...")
        client = PterodactylClient(ptero_config['panel_url'], ptero_config['api_key'])

        # Get discovery settings
        discovery_config = config.get('discovery', {})
        filter_tag = discovery_config.get('filter_by_tag')
        filter_node = discovery_config.get('filter_by_node')
        auto_detect = discovery_config.get('auto_detect_platform', True)

        logger.info(f"Filter by tag: {filter_tag or 'None'}")
        logger.info(f"Filter by node: {filter_node or 'None'}")
        logger.info(f"Auto-detect platform: {auto_detect}")
        logger.info("")

        discovered = client.discover_minecraft_servers(
            filter_tag=filter_tag,
            filter_node=filter_node,
            auto_detect_platform=auto_detect
        )

        if not discovered:
            logger.warning("\n⚠ No Minecraft servers discovered")
            logger.info("\nTips:")
            logger.info("  - Check if servers have 'minecraft' in the name")
            logger.info("  - Verify API key has access to your servers")
            logger.info("  - Try adjusting filter_by_tag or filter_by_node in config")
            return 1

        logger.info("\n" + "=" * 70)
        logger.info(f"✓ Discovery complete! Found {len(discovered)} server(s)")
        logger.info("=" * 70)

        # Ask to save to config
        save_config_choice = input("\nSave discovered servers to config? [Y/n]: ").strip().lower()
        if save_config_choice != 'n':
            config['servers'] = discovered

            # Determine config file path
            from .config_loader import get_config_paths
            config_paths = get_config_paths()
            config_file = None
            for path in config_paths:
                if path.exists():
                    config_file = path
                    break

            if not config_file:
                config_file = config_paths[0]  # Default to user config

            if save_config(config, config_file):
                logger.info(f"\n✓ Configuration updated: {config_file}")
                logger.info("\nNext steps:")
                logger.info("  1. Review server configuration")
                logger.info("  2. Assign plugins to each server in config file")
                logger.info("  3. Run 'minecraft-plugin-manager --status' to verify")
                return 0
            else:
                logger.error("\n✗ Failed to save configuration")
                return 1
        else:
            logger.info("\nDiscovered servers not saved")
            logger.info("Copy the server definitions above into your config file manually")
            return 0

    except Exception as e:
        logger.exception(f"\n✗ Discovery failed: {e}")
        return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description=f"Minecraft Plugin Manager v{__version__} - Automated update system for Minecraft plugins",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check for version consistency across servers
  %(prog)s --audit

  # Check for updates
  %(prog)s --check

  # Download updates
  %(prog)s --download

  # Download and deploy updates (with all safety checks)
  %(prog)s --deploy

  # Force check even if versions match
  %(prog)s --check --force

  # Show current versions
  %(prog)s --status

  # Emergency rollback
  %(prog)s --rollback

Managed Plugins:
  - Bedrock Cross-Play: ViaVersion, Geyser, floodgate
  - Tier 1 Infrastructure: LuckPerms, PlaceholderAPI

Documentation:
  https://github.com/anthropics/claude-code/tree/main/projects/minecraft-plugin-manager
        """
    )

    # Configuration commands
    parser.add_argument("--init", action="store_true", help="Run interactive setup wizard to create config.yaml")
    parser.add_argument("--discover", action="store_true", help="Discover Minecraft servers from Pterodactyl panel")

    # Update commands
    parser.add_argument("--check", action="store_true", help="Check for available updates")
    parser.add_argument("--download", action="store_true", help="Download available updates")
    parser.add_argument("--deploy", action="store_true", help="Deploy downloaded updates to servers")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous plugin versions using .BAK files")
    parser.add_argument("--audit", action="store_true", help="Check version consistency across similar servers")
    parser.add_argument("--force", action="store_true", help="Force update even if versions match (includes SNAPSHOT versions)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (preview changes without executing)")
    parser.add_argument("--status", action="store_true", help="Show current plugin versions")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Config file override
    parser.add_argument("--config", type=Path, help="Path to config file (overrides default search paths)")

    args = parser.parse_args()

    # Default to check mode if no action specified
    if not any([args.init, args.discover, args.check, args.download, args.deploy, args.rollback, args.audit, args.status]):
        args.check = True
        args.dry_run = True

    try:
        # Handle --init mode (setup wizard)
        if args.init:
            return run_init_wizard()

        # Handle --discover mode (Pterodactyl discovery)
        if args.discover:
            return run_discovery()

        # Load configuration
        config = load_config(args.config if args.config else None)

        # Validate configuration
        is_valid, errors = validate_config(config)
        if not is_valid:
            logger.error("\n✗ Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.info("\nRun 'minecraft-plugin-manager --init' to create a valid configuration")
            return 1

        # Handle --rollback mode
        if args.rollback:
            deployer = DeploymentManager(dry_run=args.dry_run)
            if deployer.rollback_deployment():
                logger.info("\n✓ Rollback completed successfully")
                return 0
            else:
                logger.error("\n✗ Rollback failed")
                return 1

        # Create updater instance with config
        updater = MinecraftPluginUpdater(dry_run=args.dry_run, force=args.force, config=config)

        # Handle --audit mode
        if args.audit:
            inconsistencies = updater.check_version_consistency()

            if not inconsistencies:
                logger.info("\n✓ All servers have consistent plugin versions!")
                return 0
            else:
                logger.error(f"\n✗ Found {len(inconsistencies)} plugin(s) with version inconsistencies")
                logger.info("\nRecommendation: Use --download and --deploy to sync versions across servers")
                return 1

        # Handle --status mode
        if args.status:
            updater.show_status()
            return 0

        # Handle update workflow (check, download, deploy)
        check_only = args.check and not args.download and not args.deploy
        download_only = args.download and not args.deploy
        deploy = args.deploy

        return run_update_workflow(updater, check_only=check_only, download_only=download_only, deploy=deploy)

    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
