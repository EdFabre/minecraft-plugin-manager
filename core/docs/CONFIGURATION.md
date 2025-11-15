# Configuration Guide

The Minecraft Plugin Manager supports flexible configuration through YAML files and Pterodactyl API integration for automatic server discovery.

## Quick Start

### 1. Run Setup Wizard

The easiest way to get started is using the interactive setup wizard:

```bash
minecraft-plugin-manager --init
```

This will:
- Prompt for Pterodactyl panel URL and API key
- Test the connection
- Offer to auto-discover servers
- Configure SSH settings (optional)
- Save configuration to `~/.config/minecraft-plugin-manager/config.yaml`

### 2. Auto-Discover Servers

If you already have Pterodactyl configured, you can discover servers anytime:

```bash
minecraft-plugin-manager --discover
```

This will:
- Connect to your Pterodactyl panel
- Find all Minecraft servers
- Auto-detect server platforms (velocity, paper, spigot)
- Extract Minecraft versions from server configs
- Offer to save discovered servers to config

## Configuration File Locations

The tool searches for configuration in this order:

1. Path specified with `--config <path>` argument
2. `~/.config/minecraft-plugin-manager/config.yaml` (recommended)
3. `./config.yaml` (current directory)
4. Hardcoded defaults (fallback)

## Configuration File Format

See `config_example.yaml` for a complete example. The configuration file has these sections:

### Pterodactyl Panel Connection

```yaml
pterodactyl:
  panel_url: "https://panel.example.com"
  api_key: "ptlc_your_api_key_here"
  # OR use environment variable:
  # api_key: "${PTERODACTYL_API_KEY}"
```

**API Key Types:**
- `ptlc_*` - Client API key (can access user's servers)
- `ptla_*` - Application API key (admin access, can see all servers)

### SSH Connection (Optional)

For direct volume access instead of using Pterodactyl API:

```yaml
ssh:
  host: "192.168.1.71"
  user: "root"
  key_path: "~/.ssh/id_rsa_root"
  # password: "your_password"  # Not recommended
```

### Server Definitions

Define your Minecraft servers and which plugins they should have:

```yaml
servers:
  minecraft-proxy-0:
    uuid: "b57a0213-6e24-429a-9fdd-241f82c397d1"  # Pterodactyl server UUID
    platform: "velocity"                          # velocity, paper, spigot
    minecraft_version: "velocity-3.4.0"           # Optional
    node: "games-node-1"                          # Optional: for logging
    plugins:                                      # Plugins for this server
      - ViaVersion
      - Geyser-Velocity
      - floodgate-velocity
      - LuckPerms-Velocity

  minecraft-lobby-0:
    uuid: "4178f798-1bfd-4482-b011-198601dcbe7e"
    platform: "paper"
    minecraft_version: "1.20.1"
    node: "games-node-1"
    plugins:
      - ViaVersion
      - floodgate-spigot
      - LuckPerms-Bukkit
      - PlaceholderAPI
```

**Typical 4-Server Setup:**
- **proxy** - Velocity server for Bedrock cross-play
- **lobby** - Paper server for player hub
- **game** - Paper server for gameplay
- **respack** - Paper server for resource pack distribution

### Managed Plugins

Define which plugins the tool should manage:

```yaml
managed_plugins:
  ViaVersion:
    source: "modrinth"
    project_id: "viaversion"
    platforms: ["velocity", "paper", "spigot"]
    tier: "bedrock"
    critical: true

  Geyser-Velocity:
    source: "geyser"
    project: "geyser"
    artifact: "velocity"
    platforms: ["velocity"]
    tier: "bedrock"
    critical: true
```

**Plugin Sources:**
- `modrinth` - Modrinth API (requires `project_id`)
- `geyser` - Geyser Download API (requires `project` and `artifact`)

**Tiers:**
- `bedrock` - Bedrock cross-play plugins (highest priority)
- `tier1` - Infrastructure plugins (permissions, placeholders)
- `tier2` - Gameplay plugins
- `tier3` - Quality of life plugins

### File Path Overrides

Override default file locations:

```yaml
paths:
  downloads: "/path/to/downloads"
  shared_plugins: "/path/to/shared-plugins"
  manifest: "/path/to/shared-plugins.json"
  deployment_state: "/path/to/deployment-state.json"
```

### Infrastructure Compatibility

Define infrastructure requirements for plugins:

```yaml
compatibility:
  Geyser-Velocity:
    requires:
      velocity:
        min_build: 500
        reason: "Geyser 2.9.0+ requires Adventure library API (ComponentFlattener.nestingLimit)"
```

### Discovery Settings

Configure Pterodactyl auto-discovery behavior:

```yaml
discovery:
  enabled: true
  filter_by_tag: "minecraft"           # Only discover servers with this tag
  filter_by_node: null                 # Only discover servers on specific node
  auto_detect_platform: true           # Auto-detect velocity/paper/spigot
```

## Environment Variable Substitution

You can use environment variables in config values:

```yaml
pterodactyl:
  panel_url: "https://panel.example.com"
  api_key: "${PTERODACTYL_API_KEY}"  # Reads from environment

ssh:
  password: "${SSH_PASSWORD:-default_password}"  # With default fallback
```

**Format:**
- `${VAR_NAME}` - Replace with environment variable
- `${VAR_NAME:-default}` - Replace with env var or use default if not set

## Pterodactyl Auto-Discovery

The tool can automatically discover your Minecraft servers from Pterodactyl:

### What Gets Auto-Detected?

1. **Server Identification:**
   - Server name (converted to kebab-case)
   - Server UUID
   - Node name

2. **Platform Detection:**
   - Checks server name for keywords: `velocity`, `proxy`, `paper`, `spigot`
   - Checks startup command for platform indicators
   - Defaults to `paper` if uncertain

3. **Version Detection:**
   - Extracts version from server description
   - Checks `MINECRAFT_VERSION` environment variable
   - Checks `SERVER_VERSION` environment variable

4. **Filtering:**
   - Skips non-Minecraft servers
   - Applies tag filters (if configured)
   - Applies node filters (if configured)

### Example Discovery Output

```
======================================================================
Auto-discovering Minecraft servers from Pterodactyl...
======================================================================
✓ Discovered: minecraft-proxy-0
  UUID: b57a0213-6e24-429a-9fdd-241f82c397d1
  Platform: velocity
  Node: games-node-1
  Version: velocity-3.4.0

✓ Discovered: minecraft-lobby-0
  UUID: 4178f798-1bfd-4482-b011-198601dcbe7e
  Platform: paper
  Node: games-node-1
  Version: 1.20.1

✓ Discovered 2 Minecraft server(s)
```

## Configuration Validation

The tool validates your configuration on startup:

```bash
minecraft-plugin-manager --check
```

**Validation checks:**
- At least one server defined
- At least one managed plugin defined
- All servers have required fields (uuid, platform, plugins)
- All referenced plugins are defined in managed_plugins
- Pterodactyl config is complete (if present)
- SSH config is complete (if present)

**If validation fails:**
```
✗ Configuration validation failed:
  - Server 'minecraft-lobby-0' references undefined plugin 'UnknownPlugin'
  - Plugin 'Geyser-Velocity' uses geyser source but missing 'artifact'

Run 'minecraft-plugin-manager --init' to create a valid configuration
```

## Example: 4-Server Setup

Here's a complete configuration for a typical 4-server Bedrock-compatible setup:

```yaml
pterodactyl:
  panel_url: "https://panel.example.com"
  api_key: "${PTERODACTYL_API_KEY}"

servers:
  minecraft-proxy-0:
    uuid: "b57a0213-6e24-429a-9fdd-241f82c397d1"
    platform: "velocity"
    plugins: [ViaVersion, Geyser-Velocity, floodgate-velocity, LuckPerms-Velocity]

  minecraft-lobby-0:
    uuid: "4178f798-1bfd-4482-b011-198601dcbe7e"
    platform: "paper"
    plugins: [ViaVersion, floodgate-spigot, LuckPerms-Bukkit, PlaceholderAPI]

  minecraft-game-0:
    uuid: "your-game-server-uuid"
    platform: "paper"
    plugins: [ViaVersion, floodgate-spigot, LuckPerms-Bukkit, PlaceholderAPI]

  minecraft-respack-0:
    uuid: "your-respack-server-uuid"
    platform: "paper"
    plugins: [ViaVersion, floodgate-spigot, LuckPerms-Bukkit]

managed_plugins:
  ViaVersion:
    source: "modrinth"
    project_id: "viaversion"
    platforms: ["velocity", "paper"]
    tier: "bedrock"
    critical: true

  Geyser-Velocity:
    source: "geyser"
    project: "geyser"
    artifact: "velocity"
    platforms: ["velocity"]
    tier: "bedrock"
    critical: true

  floodgate-velocity:
    source: "geyser"
    project: "floodgate"
    artifact: "velocity"
    platforms: ["velocity"]
    tier: "bedrock"
    critical: true

  floodgate-spigot:
    source: "geyser"
    project: "floodgate"
    artifact: "spigot"
    platforms: ["paper"]
    tier: "bedrock"
    critical: true

  LuckPerms-Bukkit:
    source: "modrinth"
    project_id: "Vebnzrzj"
    platforms: ["paper"]
    tier: "tier1"
    critical: true

  LuckPerms-Velocity:
    source: "modrinth"
    project_id: "Vebnzrzj"
    platforms: ["velocity"]
    tier: "tier1"
    critical: true

  PlaceholderAPI:
    source: "modrinth"
    project_id: "PlaceholderAPI"
    platforms: ["paper"]
    tier: "tier1"
    critical: true
```

## Troubleshooting

### "No config file found, using defaults"

This is normal if you haven't created a config file yet. The tool will use hardcoded defaults. Run `--init` to create a config.

### "Configuration validation failed"

Check the error messages and fix the issues in your config file. Common problems:
- Missing required fields (uuid, platform, plugins)
- Referencing undefined plugins
- Invalid Pterodactyl or SSH configuration

### "Discovery failed: Connection refused"

Check:
- Panel URL is correct and accessible
- API key is valid (starts with `ptlc_` or `ptla_`)
- Network connectivity to the panel
- Firewall rules allow access

### "No Minecraft servers discovered"

Check:
- Your servers have "minecraft" in the name OR are tagged appropriately
- API key has access to your servers (client keys only see user's servers)
- Discovery filters aren't too restrictive

## Security Best Practices

1. **Use environment variables for secrets:**
   ```yaml
   pterodactyl:
     api_key: "${PTERODACTYL_API_KEY}"
   ```

2. **Use SSH keys instead of passwords:**
   ```yaml
   ssh:
     key_path: "~/.ssh/id_rsa"
   ```

3. **Don't commit config.yaml to git:**
   - The `.gitignore` already excludes `config.yaml`
   - Only `config_example.yaml` should be committed

4. **Use client API keys when possible:**
   - Client keys (`ptlc_*`) have limited access
   - Application keys (`ptla_*`) are admin-level - only use if needed

5. **Restrict file permissions:**
   ```bash
   chmod 600 ~/.config/minecraft-plugin-manager/config.yaml
   ```

## Related Documentation

- [Quick Start Guide](./QUICK_START.md) - Getting started with the tool
- [Automation Usage](./AUTOMATION_USAGE.md) - Using the automation features
- Example configuration: `config_example.yaml` in project root
