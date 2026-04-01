"""
Audio Manager for Text2Beluga.

Manages two system-level sounds automatically:
  - typing_sound: loops continuously during 'User is typing...' status frames
  - discord_ping: triggers at the exact millisecond a message bubble appears

These are applied IN ADDITION TO user-specified sounds from the scenario JSON.
If discord_ping.mp3 or typing_sound.mp3 are not found, falls back to
message.mp3 and typing.mp3 respectively.
"""

import os
from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips

SOUNDS_DIR = os.path.join('..', 'assets', 'sounds', 'mp3')

# Primary → Fallback mapping
TYPING_SOUND_FILE = 'typing_sound.mp3'
TYPING_SOUND_FALLBACK = 'typing.mp3'
DISCORD_PING_FILE = 'discord_ping.mp3'
DISCORD_PING_FALLBACK = 'message.mp3'


class AudioManager:
    """
    Centralized audio controller for the video pipeline.

    Automatically inserts:
      1. Looped typing_sound during every typing indicator frame
      2. discord_ping at the exact timestamp each message bubble appears
    """

    def __init__(self, sounds_dir=SOUNDS_DIR):
        self.sounds_dir = sounds_dir
        self._typing_path = self._resolve(TYPING_SOUND_FILE, TYPING_SOUND_FALLBACK)
        self._ping_path = self._resolve(DISCORD_PING_FILE, DISCORD_PING_FALLBACK)

        if self._typing_path:
            print(f"  ♪ Typing sound : {os.path.basename(self._typing_path)}")
        if self._ping_path:
            print(f"  ♪ Discord ping : {os.path.basename(self._ping_path)}")

    def _resolve(self, primary, fallback):
        """Resolve a sound file path with fallback."""
        p = os.path.join(self.sounds_dir, primary)
        if os.path.isfile(p):
            return p
        fb = os.path.join(self.sounds_dir, fallback)
        if os.path.isfile(fb):
            return fb
        print(f"  ⚠ Neither {primary} nor {fallback} found in {self.sounds_dir}")
        return None

    def create_typing_loop(self, duration, start_time):
        """
        Create an AudioClip that loops typing_sound for the given duration.

        Args:
            duration:   How long the typing indicator is visible (seconds).
            start_time: Video timeline offset where the loop starts.

        Returns:
            AudioClip positioned at start_time, or None if no file.
        """
        if not self._typing_path or duration <= 0:
            return None

        clip = AudioFileClip(self._typing_path)

        if clip.duration >= duration:
            looped = clip.subclip(0, duration)
        else:
            n_loops = int(duration / clip.duration) + 1
            looped = concatenate_audioclips([clip] * n_loops).subclip(0, duration)

        return looped.set_start(start_time)

    def create_ping(self, start_time):
        """
        Create a single discord_ping AudioClip at the exact timestamp.

        Args:
            start_time: Video timeline offset (seconds) when the message appears.

        Returns:
            AudioClip positioned at start_time, or None if no file.
        """
        if not self._ping_path:
            return None
        return AudioFileClip(self._ping_path).set_start(start_time)

    def build_system_audio(self, frame_data):
        """
        Analyze frame_data and generate all system audio clips.

        Logic:
          - Any frame whose sound_name == "typing" → loop typing_sound for its duration
          - The first non-animation frame AFTER a typing sequence → play discord_ping

        Args:
            frame_data: list of (image_path, duration, sound_name) tuples.

        Returns:
            list[AudioClip]: System-generated audio clips to mix into the video.
        """
        clips = []
        cumulative_time = 0.0
        prev_was_typing = False

        for _, duration, sound_name in frame_data:
            is_typing_frame = (sound_name == "typing")

            if is_typing_frame:
                # Loop typing sound for the full duration of this indicator
                typing_clip = self.create_typing_loop(duration, cumulative_time)
                if typing_clip:
                    clips.append(typing_clip)
                prev_was_typing = True

            elif prev_was_typing and sound_name is not None:
                # Message just appeared — play ping at this exact millisecond
                ping_clip = self.create_ping(cumulative_time)
                if ping_clip:
                    clips.append(ping_clip)
                prev_was_typing = False

            else:
                prev_was_typing = False

            cumulative_time += duration

        return clips


if __name__ == "__main__":
    print("AudioManager — system sound controller for Text2Beluga")
    mgr = AudioManager()
    print(f"  Typing path: {mgr._typing_path}")
    print(f"  Ping path  : {mgr._ping_path}")
