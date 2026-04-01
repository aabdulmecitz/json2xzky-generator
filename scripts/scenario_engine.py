"""
Scenario Engine for Text2Beluga.

Replaces the old .txt parser with a structured JSON-based scenario system.
Each scenario entry defines a user, message, action type, timing, and sound.
"""

import json
import random
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScenarioEntry:
    """Represents a single event in a Beluga-style chat scenario."""
    user: str
    message: str
    action: str  # "typing", "message", "join", "leave"
    delay_before: float
    has_ping: bool = False
    sound: Optional[str] = None
    reply_to: Optional[dict] = None  # {"user": "Name", "message": "text"}

    def __post_init__(self):
        valid_actions = ("typing", "message", "join", "leave")
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action '{self.action}' for user '{self.user}'. "
                f"Must be one of: {valid_actions}"
            )
        if self.action in ("typing", "message") and not self.message:
            raise ValueError(
                f"Action '{self.action}' for user '{self.user}' requires a non-empty message."
            )
        if self.delay_before < 0:
            raise ValueError(
                f"delay_before must be non-negative, got {self.delay_before} "
                f"for user '{self.user}'."
            )


def calculate_typing_duration(message: str) -> float:
    """
    Calculate a humanized typing duration based on the message length.

    Formula:
        base = len(message) * 0.05   (50ms per character)
        variance = random.uniform(-0.3, 0.5)
        result clamped to [0.5, 5.0] seconds

    Returns:
        float: Duration in seconds for the typing indicator frame.
    """
    if not message:
        return 0.5
    base = len(message) * 0.05
    variance = random.uniform(-0.3, 0.5)
    duration = base + variance
    return max(0.5, min(5.0, round(duration, 2)))


def load_scenario(filepath: str) -> list:
    """
    Load a scenario from a JSON file and return a list of ScenarioEntry objects.

    The JSON file should contain an array of objects, each with:
        - user (str): Character name
        - message (str): Message content
        - action (str): "typing", "message", "join", or "leave"
        - delay_before (float): Seconds to wait before this entry
        - has_ping (bool): Whether this message pings someone
        - sound (str|null): Optional sound effect name

    Args:
        filepath: Path to the scenario JSON file.

    Returns:
        list[ScenarioEntry]: Ordered list of scenario entries.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the JSON is malformed.
        ValueError: If any entry fails validation.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Scenario file not found: {filepath}")

    with open(filepath, encoding="utf8") as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        raise ValueError("Scenario JSON must be an array of entry objects.")

    entries = []
    for idx, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {idx}: Expected an object, got {type(item).__name__}.")

        required_fields = ["user", "message", "action", "delay_before"]
        for field_name in required_fields:
            if field_name not in item:
                raise ValueError(f"Entry {idx}: Missing required field '{field_name}'.")

        reply_to = item.get("reply_to")
        if reply_to and not isinstance(reply_to, dict):
            raise ValueError(f"Entry {idx}: reply_to must be an object with 'user' and 'message' keys.")

        entry = ScenarioEntry(
            user=str(item["user"]),
            message=str(item.get("message", "")),
            action=str(item["action"]),
            delay_before=float(item["delay_before"]),
            has_ping=bool(item.get("has_ping", False)),
            sound=item.get("sound") if item.get("sound") else None,
            reply_to=reply_to,
        )
        entries.append(entry)

    return entries


def validate_scenario_characters(entries: list, characters_json_path: str) -> list:
    """
    Cross-validate scenario entries against the characters.json file.

    Returns:
        list[str]: List of warning/error messages (empty if valid).
    """
    errors = []
    if not os.path.isfile(characters_json_path):
        errors.append(f"Characters file not found: {characters_json_path}")
        return errors

    with open(characters_json_path, encoding="utf8") as f:
        characters = json.load(f)

    for idx, entry in enumerate(entries):
        if entry.user not in characters:
            errors.append(
                f"Entry {idx}: User '{entry.user}' not found in characters.json. "
                f"Available: {list(characters.keys())}"
            )

    return errors


def validate_scenario_sounds(entries: list, sounds_dir: str) -> list:
    """
    Cross-validate scenario entries against available sound files.

    Returns:
        list[str]: List of warning/error messages (empty if valid).
    """
    errors = []
    for idx, entry in enumerate(entries):
        if entry.sound:
            sound_path = os.path.join(sounds_dir, f"{entry.sound}.mp3")
            if not os.path.isfile(sound_path):
                errors.append(
                    f"Entry {idx}: Sound '{entry.sound}' not found at {sound_path}"
                )
    return errors


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scenario_engine.py <scenario.json>")
        sys.exit(1)

    filepath = sys.argv[1]
    try:
        entries = load_scenario(filepath)
        print(f"✓ Loaded {len(entries)} scenario entries successfully.")
        for i, e in enumerate(entries):
            typing_dur = calculate_typing_duration(e.message) if e.action == "typing" else 0
            print(
                f"  [{i:03d}] {e.action:8s} | {e.user:12s} | "
                f"delay={e.delay_before:.1f}s | typing={typing_dur:.2f}s | "
                f"sound={e.sound or '-':12s} | {e.message[:40]}"
            )
    except Exception as ex:
        print(f"✗ Error: {ex}")
        sys.exit(1)
