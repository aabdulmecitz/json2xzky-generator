"""
Migration Helper: Convert legacy .txt scripts to the new scenario.json format.

Usage:
    python migrate_txt_to_json.py <input.txt> [output.json]

If output.json is not specified, it defaults to the input filename with .json extension.
"""

import json
import sys
import os
import re


def migrate_txt_to_json(txt_filepath, json_filepath=None):
    """
    Convert a legacy .txt script to the new scenario.json format.

    Args:
        txt_filepath: Path to the input .txt script file.
        json_filepath: Path to the output .json file. If None, uses input name + .json.

    Returns:
        str: Path to the generated JSON file.
    """
    if json_filepath is None:
        base, _ = os.path.splitext(txt_filepath)
        json_filepath = base + ".json"

    with open(txt_filepath, encoding="utf8") as f:
        lines = f.read().splitlines()

    entries = []
    name_up_next = True
    current_name = None

    for line in lines:
        # Empty line resets block
        if line.strip() == '':
            name_up_next = True
            continue

        # Skip comments
        if line.strip().startswith('#'):
            continue

        # WELCOME line → join action
        if line.startswith("WELCOME "):
            parts = line.split("$^")
            name_part = parts[0].replace("WELCOME ", "").strip()

            delay = 1.5
            sound = None
            if len(parts) > 1:
                duration_sound = parts[1]
                if "#!" in duration_sound:
                    dur_str, snd_str = duration_sound.split("#!", 1)
                    delay = float(dur_str.strip())
                    sound = snd_str.strip()
                else:
                    delay = float(duration_sound.strip())

            entries.append({
                "user": name_part,
                "message": "",
                "action": "join",
                "delay_before": delay,
                "has_ping": False,
                "sound": sound
            })
            name_up_next = True
            continue

        # Name line (contains colon, first non-empty in block)
        if name_up_next:
            current_name = line.split(':')[0].strip()
            name_up_next = False
            continue

        # Message line
        parts = line.split("$^")
        message_text = parts[0].strip()

        delay = 2.0
        sound = None
        if len(parts) > 1:
            duration_sound = parts[1]
            if "#!" in duration_sound:
                dur_str, snd_str = duration_sound.split("#!", 1)
                delay = float(dur_str.strip())
                sound = snd_str.strip()
            else:
                delay = float(duration_sound.strip())

        # Detect if message has mentions → has_ping
        has_ping = bool(re.search(r'@\w+', message_text))

        # Default to "typing" action for cinematic effect
        entries.append({
            "user": current_name,
            "message": message_text,
            "action": "typing",
            "delay_before": delay,
            "has_ping": has_ping,
            "sound": sound
        })

    # Write the JSON output
    with open(json_filepath, 'w', encoding="utf8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    return json_filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_txt_to_json.py <input.txt> [output.json]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(input_file):
        print(f"✗ Input file not found: {input_file}")
        sys.exit(1)

    result = migrate_txt_to_json(input_file, output_file)
    print(f"✓ Migration complete!")
    print(f"  Input:  {input_file}")
    print(f"  Output: {result}")

    # Quick summary
    with open(result, encoding="utf8") as f:
        data = json.load(f)
    
    actions = {}
    for entry in data:
        a = entry["action"]
        actions[a] = actions.get(a, 0) + 1
    
    print(f"  Entries: {len(data)}")
    for action, count in sorted(actions.items()):
        print(f"    - {action}: {count}")


if __name__ == "__main__":
    main()
