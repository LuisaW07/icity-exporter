"""
Example: Post a diary entry, comment, and like (requires login).

Usage:
    python write_diary.py <email> <password>
"""

import sys
from icity import ICityClient

if len(sys.argv) < 3:
    print("Usage: python write_diary.py <email> <password>")
    sys.exit(1)

email, password = sys.argv[1], sys.argv[2]

client = ICityClient(email=email, password=password)
print(f"Logged in as @{client.username}\n")

# Post a new diary entry (returns the entry's short ID)
entry_id = client.post_entry("Hello from Python! 🐍")
print(f"✅ Posted diary entry: https://icity.ly/a/{entry_id}")

# Post with a title and privacy setting
entry_id2 = client.post_entry(
    content="This is a private thought.",
    title="Secret",
    privacy=3,  # 1=public, 2=friends, 3=private
)
print(f"✅ Posted private entry: {entry_id2}")

# Like an entry
client.like_entry(entry_id)
print(f"✅ Liked entry {entry_id}")

# Unlike it
client.unlike_entry(entry_id)
print(f"✅ Unliked entry {entry_id}")

# Comment on an entry (returns the comment's short ID)
comment_id = client.post_comment(entry_id, "Nice post! 🎉")
print(f"✅ Commented on {entry_id}: {comment_id}")
