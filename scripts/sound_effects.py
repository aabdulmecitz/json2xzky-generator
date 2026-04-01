import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from audio_manager import AudioManager


def add_sounds(sound_events, frame_data=None):
    """
    Overlay all sound effects onto the compiled video.

    Two layers of audio are mixed:
      1. User sounds  — from scenario JSON 'sound' fields (sound_events)
      2. System sounds — typing loops + discord pings (via AudioManager)

    Args:
        sound_events: list of (timestamp, sound_name) tuples from the scenario.
        frame_data:   raw frame_data for AudioManager analysis (optional).
    """
    video = VideoFileClip("output.mp4")
    audio_clips = []

    # ── Layer 1: User-specified sounds from scenario ──────────────────────
    for timestamp, sound_name in sound_events:
        # Skip 'typing' marker — handled by AudioManager's looped typing sound
        if sound_name == "typing":
            continue
        audio_file = f'../assets/sounds/mp3/{sound_name}.mp3'
        if os.path.isfile(audio_file):
            audio_clips.append(AudioFileClip(audio_file).set_start(timestamp))
        else:
            print(f"  ⚠ Sound not found: {audio_file}, skipping.")

    # ── Layer 2: System sounds (typing loop + discord ping) ───────────────
    if frame_data:
        mgr = AudioManager()
        system_clips = mgr.build_system_audio(frame_data)
        audio_clips.extend(system_clips)
        print(f"  ♪ AudioManager added {len(system_clips)} system sound clips")

    # ── Mix and write ─────────────────────────────────────────────────────
    if audio_clips:
        composite_audio = CompositeAudioClip(audio_clips)
        video = video.set_audio(composite_audio)

    video.write_videofile("../final_video.mp4", codec="libx264", audio_codec="aac")
    os.remove("output.mp4")


# ── LEGACY: .txt-based add_sounds (for backward compatibility) ────────────────

def add_sounds_legacy(filename):
    """Legacy .txt-based sound overlay."""
    video = VideoFileClip("output.mp4")
    duration = 0
    audio_clips = []

    with open(filename, encoding="utf8") as f:
        name_up_next = True
        for line in f.read().splitlines():
            if line == '':
                name_up_next = True
                continue
            elif line.startswith('#'):
                continue
            elif line.startswith("WELCOME"):
                if "#!" in line:
                    parts = line.split('$^')
                    duration_part, sound_part = parts[1].split("#!")
                    audio_file = f'../assets/sounds/mp3/{sound_part.strip()}.mp3'
                    audio_clips.append(AudioFileClip(audio_file).set_start(duration))
                    duration += float(duration_part)
                else:
                    duration += float(line.split('$^')[1])
            elif name_up_next:
                name_up_next = False
                continue
            else:
                if "#!" in line:
                    parts = line.split('$^')
                    duration_part, sound_part = parts[1].split("#!")
                    audio_file = f'../assets/sounds/mp3/{sound_part.strip()}.mp3'
                    audio_clips.append(AudioFileClip(audio_file).set_start(duration))
                    duration += float(duration_part)
                else:
                    duration += float(line.split('$^')[1])

    if audio_clips:
        composite_audio = CompositeAudioClip(audio_clips)
        video = video.set_audio(composite_audio)

    video.write_videofile("../final_video.mp4", codec="libx264", audio_codec="aac")
    os.remove("output.mp4")