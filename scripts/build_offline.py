#!/usr/bin/env python3
"""Cross-platform script to generate standalone zero-config offline distribution bundle."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neron.packaging import OfflineBundleGenerator, PackagingConfig


def main() -> None:
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "build/offline"
    print("========================================================")
    print("  Neron Standalone Offline Bundle Generator             ")
    print("========================================================")

    cfg = PackagingConfig(
        app_name="Neron",
        version="1.0.0",
        bundle_type="offline",
        include_models=True,
    )

    res = OfflineBundleGenerator.create_offline_bundle(cfg, output_dir=output_dir)
    print(f"[OK] Bundle created at: {res['bundle_dir']}")
    print(f"[OK] Total files indexed with SHA256: {res['files_count']}")
    print(f"[OK] Offline manifest: {res['manifest_file']}")
    print("\n[SUCCESS] Standalone offline installer bundle generated successfully!")


if __name__ == "__main__":
    main()
