#!/usr/bin/env python3
"""Script to add @require_permission("all") to admin-only endpoints"""

# Endpoints that need admin permission
ADMIN_ENDPOINTS = [
    "/api/config",
    "/api/config/roles",
    "/api/config/welcome",
    "/api/config/rocket_league",
    "/api/config/server_guide",
    "/api/rocket-league",
    "/api/logs",
]

# Endpoints that should remain accessible to meme_generator users (skip these)
SKIP_ENDPOINTS = [
    "/api/health",
    "/api/auth/login",
    "/api/auth/me",
    "/api/discord",
    "/api/meme-generator",
    "/api/imgflip",
    "/api/test/meme",  # Meme testing endpoints
    "/api/proxy/image",
]


def should_protect_endpoint(line):
    """Check if this endpoint should be protected"""
    for skip in SKIP_ENDPOINTS:
        if skip in line:
            return False

    for admin in ADMIN_ENDPOINTS:
        if admin in line:
            return True

    return False


def main():
    with open("api/app.py", "r") as f:
        lines = f.readlines()

    modified_lines = []
    i = 0
    changes = 0

    while i < len(lines):
        line = lines[i]
        modified_lines.append(line)

        # Check if this is a route definition
        if "@app.route(" in line and should_protect_endpoint(line):
            # Check next line for @token_required
            if i + 1 < len(lines) and "@token_required" in lines[i + 1]:
                modified_lines.append(lines[i + 1])  # Add @token_required

                # Check if @require_permission already exists
                if i + 2 < len(lines) and "@require_permission" not in lines[i + 2]:
                    # Add @require_permission("all")
                    modified_lines.append('@require_permission("all")\n')
                    changes += 1
                    print(f"Added permission check to line {i + 1}: {line.strip()}")

                i += 2
                continue

        i += 1

    if changes > 0:
        with open("api/app.py", "w") as f:
            f.writelines(modified_lines)
        print(f"\n✅ Added {changes} permission checks")
    else:
        print("✅ No changes needed")


if __name__ == "__main__":
    main()
