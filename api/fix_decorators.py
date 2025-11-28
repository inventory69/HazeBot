#!/usr/bin/env python3
"""
Script to remove @token_required and @require_permission decorators from Blueprint modules
These decorators must be applied AFTER initialization, not at import time
"""

import re
from pathlib import Path

# Blueprint modules that need fixing
BLUEPRINT_MODULES = [
    "auth_routes.py",
    "config_routes.py",
    "user_routes.py",
    "meme_routes.py",
    "rocket_league_routes.py",
    "ticket_routes.py",
    "hazehub_cogs_routes.py",
    "notification_routes.py",
]


def remove_decorators(file_path):
    """Remove @token_required and @require_permission decorators from routes"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content

    # Pattern to match the decorators (handles multi-line)
    # Match @token_required or @require_permission("...") on their own line
    content = re.sub(r"^@token_required\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"^@require_permission\([^)]+\)\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"^@log_config_action\([^)]+\)\n", "", content, flags=re.MULTILINE)

    if content != original_content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Fixed: {file_path.name}")
        return True
    else:
        print(f"⏭️  Skipped: {file_path.name} (no changes needed)")
        return False


def main():
    api_dir = Path(__file__).parent
    fixed_count = 0

    print("🔧 Removing decorators from Blueprint modules...")
    print("=" * 60)

    for module_name in BLUEPRINT_MODULES:
        file_path = api_dir / module_name
        if file_path.exists():
            if remove_decorators(file_path):
                fixed_count += 1
        else:
            print(f"⚠️  Not found: {module_name}")

    print("=" * 60)
    print(f"✅ Fixed {fixed_count} modules")
    print("\n⚠️  NOTE: You must now manually add decorator application in each init_*_routes() function")
    print("   See admin_routes.py for the pattern to follow")


if __name__ == "__main__":
    main()
