"""
Inspect the audit log directly from the command line.

Usage:
    python inspect_log.py        # last 5 entries
    python inspect_log.py 10     # last N entries
"""

import sys
from audit.log import get_recent

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    entries = get_recent(limit)

    if not entries:
        print("Audit log is empty.")
        return

    print(f"{len(entries)} most recent submission(s):\n")
    for entry in entries:
        print(f"  content_id  : {entry['content_id']}")
        print(f"  creator_id  : {entry['creator_id']}")
        print(f"  timestamp   : {entry['timestamp']}")
        print(f"  attribution : {entry['attribution']}")
        print(f"  confidence  : {entry['confidence']}")
        print(f"  llm_score   : {entry['llm_score']}")
        print(f"  status      : {entry['status']}")
        print()

if __name__ == "__main__":
    main()
