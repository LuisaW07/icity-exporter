"""
Example: Read a user's public diary entries (no login needed).

Note: icity.ly only shows ~3 most recent entries without login.
For full access, see read_all.py.
"""

from icity import ICityClient

client = ICityClient()

# Get profile info
profile = client.get_profile("mylifeisalwaysperfect")
print(f"User: {profile.nickname} (@{profile.username})")
print(f"Diary entries: {profile.diary_count}")
print(f"Bio: {profile.bio}")
print()

# Read recent public entries (limited to ~3 without login)
entries = client.get_entries("mylifeisalwaysperfect")
print(f"Got {len(entries)} public entries:\n")

for entry in entries:
    print(f"[{entry.date} {entry.time}] {entry.content[:80]}...")
    if entry.images:
        print(f"  📷 {len(entry.images)} image(s)")
    print()
