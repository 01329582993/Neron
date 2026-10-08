# 🔌 Neron Plugin Development Guide

Neron is engineered as an extensible platform. Third-party developers can extend its capabilities—adding support for applications like Spotify, VS Code, trading platforms, or custom automation workflows—without modifying Neron's core codebase.

---

## 📁 Plugin Directory Structure

All plugins reside in either the global `plugins/` directory or the user's local config folder (`~/.neron/plugins/`):

```text
plugins/
└── neron-spotify/
    ├── plugin.yaml          # Plugin metadata & permission manifest
    ├── __init__.py          # Package initializer
    ├── plugin.py            # Main plugin lifecycle entrypoint
    ├── tools.py             # Custom tool implementations
    ├── requirements.txt     # Python dependencies (if any)
    └── README.md            # Plugin documentation
```

---

## 📜 The Plugin Manifest (`plugin.yaml`)

Every plugin **must** include a `plugin.yaml` manifest that explicitly declares its identity, required capabilities, and exposed components:

```yaml
id: "neron-spotify"
name: "Spotify Controller"
version: "1.0.0"
author: "Neron Community"
description: "Control playback, playlists, and track search on Spotify."
min_neron_version: "0.1.0"

# Explicit capability requirements requested from Neron's security engine
permissions:
  - "network.access"
  - "application.control"

# Tools exposed to the Neron Agent
tools:
  - name: "spotify.play"
    description: "Start or resume playback"
  - name: "spotify.pause"
    description: "Pause playback"
  - name: "spotify.search_track"
    description: "Search for a song or artist"

# Configuration options customizable by the user
config:
  client_id: ""
  client_secret: ""
  redirect_uri: "http://localhost:8888/callback"
```

---

## 🐍 Plugin Lifecycle & Entry Point (`plugin.py`)

A plugin inherits from `neron.plugins.base.PluginBase`:

```python
from typing import Dict, Any
from neron.plugins.base import PluginBase
from neron.tools.registry import ToolRegistry
from .tools import SpotifyPlayTool, SpotifyPauseTool, SpotifySearchTool

class SpotifyPlugin(PluginBase):
    def on_load(self) -> bool:
        """Called when the plugin is initially discovered and loaded into memory."""
        self.logger.info("Initializing Spotify Plugin...")
        return True

    def on_enable(self, registry: ToolRegistry) -> None:
        """Called when the user or system activates the plugin. Register tools here."""
        registry.register(SpotifyPlayTool(self.config))
        registry.register(SpotifyPauseTool(self.config))
        registry.register(SpotifySearchTool(self.config))
        self.logger.info("Spotify tools registered successfully.")

    def on_disable(self, registry: ToolRegistry) -> None:
        """Called when the plugin is deactivated. Unregister tools and release resources."""
        registry.unregister("spotify.play")
        registry.unregister("spotify.pause")
        registry.unregister("spotify.search_track")
        self.logger.info("Spotify tools unregistered.")

    def on_unload(self) -> None:
        """Final cleanup before unloading from runtime."""
        self.logger.info("Spotify Plugin unloaded.")
```

---

## 🛡️ Sandbox & Permission Enforcement

1. **Declared Permissions**: When a user installs or enables a plugin, Neron displays the exact list of permissions requested in the manifest (`network.access`, `application.control`, etc.).
2. **Permission Rejection**: If the user declines to grant a permission, the plugin is either loaded in restricted mode or disabled.
3. **Audit Trail**: All tool calls originating from a plugin are tagged with `plugin_id: <id>` in the central audit database.

---

## 🧪 Testing Your Plugin

We provide a mock testing harness for plugin developers:

```python
import pytest
from neron.tools.registry import ToolRegistry
from plugins.neron_spotify.plugin import SpotifyPlugin

def test_spotify_plugin_lifecycle():
    registry = ToolRegistry()
    plugin = SpotifyPlugin()
    
    assert plugin.on_load() is True
    plugin.on_enable(registry)
    
    # Assert tools were registered
    assert registry.has("spotify.play")
    assert registry.has("spotify.pause")
    
    plugin.on_disable(registry)
    assert not registry.has("spotify.play")
```

---

## 🚀 Publishing & Distribution

1. Package your plugin into a `.zip` or Git repository.
2. In Neron, users can install plugins via CLI or Console:
   ```bash
   neron plugin install https://github.com/user/neron-spotify.git
   ```
3. Neron's `DeveloperAgent` verifies the manifest, checks dependencies, prompts the user for permission grant, and activates the extension.
