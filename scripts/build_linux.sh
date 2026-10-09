#!/usr/bin/env bash
# Shell script to package Neron for Linux (AppImage & Debian)
set -e

OUTPUT_DIR="${1:-build/linux}"

echo "========================================================"
echo "  Neron Linux Packaging Engine                          "
echo "========================================================"

python3 -c "
from neron.packaging import PackageBuilder, PackagingConfig
builder = PackageBuilder()
cfg = PackagingConfig(target_os='linux')
res = builder.build_linux_artifacts(cfg, '${OUTPUT_DIR}')
print(f'[OK] Generated AppDir at: {res[\"appimage_dir\"]}')
print(f'[OK] Generated Debian tree at: {res[\"debian_dir\"]}')
"

echo "[SUCCESS] Linux packaging artifacts generated in ${OUTPUT_DIR}"
