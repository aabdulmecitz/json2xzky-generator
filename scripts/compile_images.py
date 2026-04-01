import os
from sound_effects import add_sounds


def gen_vid(frame_data):
    """
    Compile chat images into a video using ffmpeg.

    Args:
        frame_data: list of (image_path, duration, sound_name) tuples.
                    - image_path: path to the PNG frame
                    - duration: how long this frame should be shown (seconds)
                    - sound_name: sound effect name or None (passed to add_sounds)
    """
    if not frame_data:
        print("⚠ No frames to compile.")
        return

    # Create the ffmpeg concat file
    with open('image_paths.txt', 'w') as f:
        for image_path, duration, _ in frame_data:
            f.write(f"file '{image_path}'\noutpoint {duration}\n")
        # Add a tiny final frame to avoid ffmpeg truncation
        last_path = frame_data[-1][0]
        f.write(f"file '{last_path}'\noutpoint 0.04\n")

    video_width, video_height = 1280, 720
    ffmpeg_cmd = (
        f"ffmpeg -f concat -safe 0 -i image_paths.txt -vcodec libx264 -r 25 -crf 25 "
        f"-vf \"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,"
        f"pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2\" -pix_fmt yuv420p output.mp4"
    )
    os.system(ffmpeg_cmd)
    os.remove('image_paths.txt')

    # Build sound events from frame_data
    sound_events = _build_sound_events(frame_data)
    add_sounds(sound_events)


def _build_sound_events(frame_data):
    """
    Convert frame_data into a list of (timestamp, sound_name) tuples
    for the sound_effects module.

    Each frame's sound plays at the start of that frame's display time.
    """
    sound_events = []
    cumulative_time = 0.0

    for _, duration, sound_name in frame_data:
        if sound_name:
            sound_events.append((cumulative_time, sound_name))
        cumulative_time += duration

    return sound_events


# ── LEGACY: .txt-based gen_vid (for backward compatibility) ───────────────────

def gen_vid_legacy(filename):
    """Legacy .txt-based video compilation."""
    input_folder = '../chat/'
    image_files = sorted([f for f in os.listdir(input_folder) if f.endswith('.png')])

    durations = []
    with open(filename, encoding="utf8") as f:
        name_up_next = True
        lines = f.read().splitlines()
        for line in lines:
            if line == '':
                name_up_next = True
                continue
            elif line[0] == '#':
                continue
            elif line.startswith("WELCOME"):
                if "#!" in line:
                    durations.append(line.split('$^')[1].split("#!")[0])
                else:
                    durations.append(line.split('$^')[1])
                continue
            elif name_up_next == True:
                name_up_next = False
                continue
            else:
                if "#!" in line:
                    durations.append(line.split('$^')[1].split("#!")[0])
                else:
                    durations.append(line.split('$^')[1])

    with open('image_paths.txt', 'w') as file:
        count = 0
        for image_file in image_files:
            file.write(f"file '{input_folder}{image_file}'\noutpoint {durations[count]}\n")
            count += 1
        file.write(f"file '{input_folder}{image_files[-1]}'\noutpoint 0.04\n")

    video_width, video_height = 1280, 720
    ffmpeg_cmd = (
        f"ffmpeg -f concat -safe 0 -i image_paths.txt -vcodec libx264 -r 25 -crf 25 "
        f"-vf \"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,"
        f"pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2\" -pix_fmt yuv420p output.mp4"
    )
    os.system(ffmpeg_cmd)
    os.remove('image_paths.txt')

    from sound_effects import add_sounds_legacy
    add_sounds_legacy(filename)