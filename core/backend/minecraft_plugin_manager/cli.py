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

    parser.add_argument("--check", action="store_true", help="Check for available updates")
    parser.add_argument("--download", action="store_true", help="Download available updates")
    parser.add_argument("--deploy", action="store_true", help="Deploy downloaded updates to servers")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous plugin versions using .BAK files")
    parser.add_argument("--audit", action="store_true", help="Check version consistency across similar servers")
    parser.add_argument("--force", action="store_true", help="Force update even if versions match (includes SNAPSHOT versions)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (preview changes without executing)")
    parser.add_argument("--status", action="store_true", help="Show current plugin versions")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    # Default to check mode if no action specified
    if not any([args.check, args.download, args.deploy, args.rollback, args.audit, args.status]):
        args.check = True
        args.dry_run = True

    try:
        # Handle --rollback mode
        if args.rollback:
            deployer = DeploymentManager(dry_run=args.dry_run)
            if deployer.rollback_deployment():
                logger.info("\n✓ Rollback completed successfully")
                return 0
            else:
                logger.error("\n✗ Rollback failed")
                return 1

        # Create updater instance
        updater = MinecraftPluginUpdater(dry_run=args.dry_run, force=args.force)

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
