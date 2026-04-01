import os
import sys
import re
import json
import argparse
from PyQt5.QtWidgets import QApplication, QFileDialog


def get_filename():
    """Opens a file dialog and returns the selected filename."""
    app = QApplication(sys.argv)
    options = QFileDialog.Options()
    filename, _ = QFileDialog.getOpenFileName(
        None, "Select File to Validate", "",
        "Scenario Files (*.json);;Text Files (*.txt);;All Files (*)",
        options=options
    )
    app.exit()
    return filename


# ── NEW: JSON Scenario Validation ─────────────────────────────────────────────

def validate_scenario(filepath):
    """
    Validate a scenario JSON file.

    Checks:
        - Valid JSON structure (must be an array of objects)
        - Required fields: user, message, action, delay_before
        - action must be one of: typing, message, join, leave
        - user must exist in characters.json
        - sound (if specified) must exist in assets/sounds/mp3/
        - delay_before must be a non-negative number
        - message must be non-empty for typing and message actions
        - has_ping must be a boolean

    Returns:
        list[str]: List of error messages (empty if valid).
    """
    errors = []

    # Load the JSON file
    if not os.path.isfile(filepath):
        errors.append(f"File not found: {filepath}")
        return errors

    try:
        with open(filepath, encoding="utf8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return errors

    if not isinstance(data, list):
        errors.append("Scenario JSON must be an array (list) of entry objects.")
        return errors

    # Load characters for cross-validation
    characters_path = os.path.join("..", "assets", "profile_pictures", "characters.json")
    characters = {}
    if os.path.isfile(characters_path):
        with open(characters_path, encoding="utf8") as f:
            characters = json.load(f)
    else:
        errors.append(f"⚠ characters.json not found at {characters_path}")

    valid_actions = {"typing", "message", "join", "leave"}
    sounds_dir = os.path.join("..", "assets", "sounds", "mp3")

    for idx, item in enumerate(data):
        prefix = f"Entry {idx}"

        if not isinstance(item, dict):
            errors.append(f"{prefix}: Expected an object, got {type(item).__name__}.")
            continue

        # Check required fields
        for field in ["user", "message", "action", "delay_before"]:
            if field not in item:
                errors.append(f"{prefix}: Missing required field '{field}'.")

        # Validate user
        user = item.get("user", "")
        if user and characters and user not in characters:
            errors.append(
                f"{prefix}: User '{user}' not found in characters.json. "
                f"Available: {list(characters.keys())}"
            )

        # Validate action
        action = item.get("action", "")
        if action and action not in valid_actions:
            errors.append(
                f"{prefix}: Invalid action '{action}'. Must be one of: {sorted(valid_actions)}"
            )

        # Validate delay_before
        delay = item.get("delay_before")
        if delay is not None:
            try:
                delay_val = float(delay)
                if delay_val < 0:
                    errors.append(f"{prefix}: delay_before must be non-negative, got {delay_val}.")
            except (ValueError, TypeError):
                errors.append(f"{prefix}: delay_before must be a number, got '{delay}'.")

        # Validate message non-empty for typing/message actions
        message = item.get("message", "")
        if action in ("typing", "message") and not message:
            errors.append(f"{prefix}: Action '{action}' requires a non-empty message.")

        # Validate sound
        sound = item.get("sound")
        if sound:
            sound_path = os.path.join(sounds_dir, f"{sound}.mp3")
            if not os.path.isfile(sound_path):
                errors.append(f"{prefix}: Sound '{sound}' not found at {sound_path}")

        # Validate has_ping
        has_ping = item.get("has_ping")
        if has_ping is not None and not isinstance(has_ping, bool):
            errors.append(f"{prefix}: has_ping must be a boolean, got '{has_ping}'.")

    return errors


# ── LEGACY: .txt Script Validation ────────────────────────────────────────────

def validate_script_lines(lines):
    """
    Validate the legacy .txt script lines.

    Expected structure:
      - An empty line: resets the block state.
      - Lines starting with '#' are comments and are skipped.
      - Lines starting with "WELCOME " are treated as joined messages.
      - The first non-empty, non-comment, non-WELCOME line in a block should be a name line (must contain a colon).
      - Subsequent lines in that block (chat messages) must contain the delimiter '$^' with a valid float duration,
        optionally followed by a sound marker starting with "#!".
      - If a sound marker is present, the referenced sound file (../assets/sounds/mp3/<sound>.mp3) must exist.
    """
    errors = []
    state = "waiting_for_name"
    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if line == "":
            state = "waiting_for_name"
            continue
        if line.startswith("#"):
            continue
        if line.startswith("WELCOME "):
            continue

        if state == "waiting_for_name":
            if ":" not in line:
                errors.append(f"Line {idx}: Expected a name line containing ':' but got: {line}")
            else:
                name_part = line.split(":", 1)[0].strip()
                if not name_part:
                    errors.append(f"Line {idx}: Name part before ':' is empty.")
            state = "collecting_messages"
        else:
            if "$^" not in line:
                errors.append(f"Line {idx}: Expected '$^' delimiter in message line but got: {line}")
            else:
                parts = line.split("$^", 1)
                duration_part = parts[1].strip()
                if duration_part == "":
                    errors.append(f"Line {idx}: Missing duration information after '$^'.")
                else:
                    if "#!" in duration_part:
                        dur_str, sound_marker = duration_part.split("#!", 1)
                        dur_str = dur_str.strip()
                        sound_name = sound_marker.strip()
                        sound_path = os.path.join("..", "assets", "sounds", "mp3", f"{sound_name}.mp3")
                        if not os.path.isfile(sound_path):
                            errors.append(f"Line {idx}: Sound effect '{sound_name}' does not exist at expected location: {sound_path}")
                    else:
                        dur_str = duration_part
                    try:
                        float(dur_str)
                    except ValueError:
                        errors.append(f"Line {idx}: Unable to convert duration '{dur_str}' to a number.")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate a script file for chat generation.")
    parser.add_argument("script_file", nargs="?", help="Path to the script file (.json or .txt). If not provided, a file dialog will open.")
    args = parser.parse_args()

    if args.script_file:
        filename = args.script_file
    else:
        filename = get_filename()

    if not filename or not os.path.isfile(filename):
        print("No valid file selected. Exiting.")
        sys.exit(1)

    if filename.endswith('.json'):
        errors = validate_scenario(filename)
    else:
        with open(filename, encoding="utf8") as f:
            lines = f.read().splitlines()
        errors = validate_script_lines(lines)

    if errors:
        print("Validation found issues:")
        for error in errors:
            print("  -", error)
    else:
        print("✓ Validation successful: no problems found.")


if __name__ == '__main__':
    # main()
    print('Please run the main.py script!')