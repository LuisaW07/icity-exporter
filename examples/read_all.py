"""
Example: Read ALL diary entries with login (full pagination).

Usage:
    python read_all.py <email> <password> <username>
"""

import sys
from icity import ICityClient

if len(sys.argv) < 4:
    print("Usage: python read_all.py <email> <password> <username>")
    sys.exit(1)

email, password, username = sys.argv[1], sys.argv[2], sys.argv[3]

# Login
client = ICityClient(email=email, password=password)
print(f"Logged in as @{client.username}\n")

# Fetch all entries
entries = client.get_all_entries(username)
print(f"\nTotal: {len(entries)} entries\n")

# Show first 5
for entry in entries[:5]:
    print(f"[{entry.date} {entry.time}]")
    print(f"  {entry.content[:100]}")
    if entry.images:
        print(f"  📷 {len(entry.images)} image(s)")
    if entry.likes:
        print(f"  ♡ {entry.likes}")
    print()
