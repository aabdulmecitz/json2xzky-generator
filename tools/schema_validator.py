#!/usr/bin/env python3
"""
schema_validator.py — Scenario JSON Schema Validator
=====================================================
Validates a scenario.json file against the full interaction engine schema.
Reports errors, warnings, and statistics.

Usage:
    python tools/schema_validator.py assets/example/example_scenario.json
"""

import json
import sys
from pathlib import Path

# All valid action types supported by the interaction engine
VALID_ACTIONS = {
    # Navigation
    "open_sidebar", "close_sidebar", "switch_server", "switch_channel",
    # Messaging
    "typing", "type_message", "message", "send_message",
    "reply", "send_attachment", "send_voice_note",
    # Mutations
    "add_reaction", "edit_message", "delete_message", "reveal_spoiler",
    # Overlays & System
    "join", "leave", "system_message",
    "open_profile", "push_notification",
    "incoming_call", "join_call", "toggle_mute",
}

# Actions that REQUIRE specific fields
REQUIRED_FIELDS = {
    "reply":              ["reply_to_id"],
    "add_reaction":       ["target_msg_id", "emoji"],
    "edit_message":       ["target_msg_id", "new_text"],
    "delete_message":     ["target_msg_id"],
    "reveal_spoiler":     ["target_msg_id"],
    "open_profile":       ["target_user"],
    "push_notification":  ["title", "body"],
    "incoming_call":      ["caller"],
    "send_attachment":    ["image_url"],
    "switch_server":      ["target_id"],
    "switch_channel":     ["target_id"],
}

# Base fields every entry should have
BASE_FIELDS = {"id", "action"}

# Optional but recommended fields
RECOMMENDED_FIELDS = {"user_id", "message_content", "pause_after", "sound", "zoom"}


def validate_scenario(filepath: str) -> dict:
    """
    Validate a scenario JSON file.
    Returns a dict with 'errors', 'warnings', 'stats'.
    """
    path = Path(filepath)
    if not path.exists():
        return {"errors": [f"File not found: {filepath}"], "warnings": [], "stats": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"errors": [f"Invalid JSON: {e}"], "warnings": [], "stats": {}}

    if not isinstance(data, list):
        return {"errors": ["Root element must be a JSON array"], "warnings": [], "stats": {}}

    errors = []
    warnings = []
    seen_ids = set()
    action_counts = {}
    zoom_count = 0
    users = set()

    for i, entry in enumerate(data):
        prefix = f"Entry #{i+1}"

        # Check it's a dict
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: Must be a JSON object, got {type(entry).__name__}")
            continue

        # Check base fields
        if "id" not in entry:
            errors.append(f"{prefix}: Missing required field 'id'")
        else:
            eid = entry["id"]
            if eid in seen_ids:
                errors.append(f"{prefix}: Duplicate id={eid}")
            seen_ids.add(eid)

        if "action" not in entry:
            errors.append(f"{prefix}: Missing required field 'action'")
            continue

        action = entry["action"]

        # Check action is valid
        if action not in VALID_ACTIONS:
            errors.append(f"{prefix} (id={entry.get('id')}): Unknown action '{action}'")
            continue

        action_counts[action] = action_counts.get(action, 0) + 1

        # Track users
        uid = entry.get("user_id") or entry.get("user")
        if uid:
            users.add(uid)

        # Check required fields for this action
        if action in REQUIRED_FIELDS:
            for field in REQUIRED_FIELDS[action]:
                if field not in entry or entry[field] is None:
                    errors.append(
                        f"{prefix} (id={entry.get('id')}, action='{action}'): "
                        f"Missing required field '{field}'"
                    )

        # Check reply_to_id references exist
        if action == "reply" and entry.get("reply_to_id"):
            if entry["reply_to_id"] not in seen_ids:
                warnings.append(
                    f"{prefix} (id={entry.get('id')}): reply_to_id={entry['reply_to_id']} "
                    f"references a message that hasn't appeared yet (forward ref or missing)"
                )

        # Check zoom flag
        if entry.get("zoom") or entry.get("focus"):
            zoom_count += 1

        # Warn on messages without user_id
        if action in ("message", "send_message", "typing", "type_message",
                       "reply", "send_attachment", "send_voice_note"):
            if not uid:
                warnings.append(
                    f"{prefix} (id={entry.get('id')}): Message-type action without user_id"
                )

        # Warn on pause_after
        if action in ("message", "send_message", "reply"):
            if not entry.get("pause_after") and not entry.get("delay"):
                warnings.append(
                    f"{prefix} (id={entry.get('id')}): Message has no pause_after/delay "
                    f"— messages will stack instantly"
                )

    stats = {
        "total_entries": len(data),
        "unique_users": len(users),
        "users": sorted(users),
        "action_breakdown": dict(sorted(action_counts.items())),
        "zoom_cues": zoom_count,
        "errors": len(errors),
        "warnings": len(warnings),
    }

    return {"errors": errors, "warnings": warnings, "stats": stats}


def main():
    if len(sys.argv) < 2:
        print("Usage: python schema_validator.py <scenario.json>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"\n╔════════════════════════════════════════════╗")
    print(f"║  🔍 SCENARIO SCHEMA VALIDATOR              ║")
    print(f"╚════════════════════════════════════════════╝\n")

    result = validate_scenario(filepath)

    # Print stats
    stats = result["stats"]
    if stats:
        print(f"📊 Statistics:")
        print(f"   Total entries:  {stats.get('total_entries', 0)}")
        print(f"   Unique users:   {stats.get('unique_users', 0)} → {stats.get('users', [])}")
        print(f"   Zoom cues:      {stats.get('zoom_cues', 0)}")
        print(f"   Action breakdown:")
        for action, count in stats.get("action_breakdown", {}).items():
            print(f"     {action:25s} {count}")
        print()

    # Print errors
    if result["errors"]:
        print(f"❌ {len(result['errors'])} Error(s):")
        for err in result["errors"]:
            print(f"   • {err}")
        print()

    # Print warnings
    if result["warnings"]:
        print(f"⚠️  {len(result['warnings'])} Warning(s):")
        for warn in result["warnings"]:
            print(f"   • {warn}")
        print()

    if not result["errors"] and not result["warnings"]:
        print("✅ Schema validation passed with no issues!\n")
    elif not result["errors"]:
        print("✅ Schema is valid (warnings are non-blocking).\n")
    else:
        print("❌ Schema validation FAILED — fix errors above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
