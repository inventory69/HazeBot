#!/usr/bin/env python3
"""
Quick test script to verify all routes are properly registered
"""

import sys
sys.path.insert(0, '.')

from api.app import app

print("🔍 Checking registered routes...\n")

# Get all routes
routes = []
for rule in app.url_map.iter_rules():
    if rule.endpoint != 'static':
        routes.append({
            'endpoint': rule.endpoint,
            'methods': ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})),
            'path': rule.rule
        })

# Sort by path
routes.sort(key=lambda x: x['path'])

print(f"✅ Found {len(routes)} API routes:")
print("-" * 80)

for route in routes:
    print(f"{route['methods']:10} {route['path']:50} -> {route['endpoint']}")

print("-" * 80)
print(f"\n📊 Total routes: {len(routes)}")

# Check for specific missing routes from user's error log
missing_checks = [
    '/api/auth/me',
    '/api/ping',
    '/api/proxy/image',
    '/api/guild/channels',
    '/api/guild/roles',
    '/api/memes/<message_id>/reactions'
]

print("\n🔍 Checking specific routes:")
for check in missing_checks:
    # Convert Flask route pattern to check
    check_pattern = check.replace('<message_id>', '<int:message_id>')
    found = any(check in r['path'] or check_pattern in r['path'] for r in routes)
    status = "✅" if found else "❌"
    print(f"{status} {check}")
