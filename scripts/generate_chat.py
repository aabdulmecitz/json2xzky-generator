from PIL import Image, ImageFont, ImageDraw
from pilmoji import Pilmoji
import sys
import datetime
import os
import json
import random
import regex
import re

from scenario_engine import ScenarioEntry, calculate_typing_duration

# ── DISCORD 2026 DARK MODE COLORS ─────────────────────────────────────────────

WORLD_WIDTH = 1777
WORLD_COLOR = (49, 51, 56, 255)       # #313338 — Discord dark bg
MESSAGE_FONT_COLOR = (219, 222, 225)   # #dbdee1 — Discord message text
NAME_FONT_COLOR = (255, 255, 255)
TIME_FONT_COLOR = (148, 155, 164)      # #949ba4
JOINED_FONT_COLOR = (148, 155, 164)    # #949ba4
PING_BG_COLOR = (68, 64, 55, 255)     # #444037 — Discord ping highlight
MENTION_BG_COLOR = (59, 60, 99)        # #3b3c63
MENTION_TEXT_COLOR = (201, 205, 251)   # #c9cdfb

# Reply constants
REPLY_HEADER_HEIGHT = 55
REPLY_LINE_COLOR = (78, 80, 88)        # #4e5058
REPLY_TEXT_COLOR = (181, 186, 193)     # #b5bac1
REPLY_AVATAR_SIZE = 40
REPLY_NAME_FONT_SIZE = 35
REPLY_FONT_SIZE = 35
REPLY_LINE_X = 66
REPLY_CURVE_RADIUS = 12

# Typing indicator
TYPING_HEIGHT = 90
TYPING_TEXT_COLOR = (180, 182, 186)
TYPING_FONT_SIZE = 40

# Animation
ANIMATION_FRAME_DURATION = 0.04
ANIMATION_NUM_FRAMES = 3
ANIMATION_SLIDE_PX = 12

# ── LAYOUT ─────────────────────────────────────────────────────────────────────

WORLD_Y_INIT_MESSAGE = 231
WORLD_DY = 70
WORLD_HEIGHTS_MESSAGE = [WORLD_Y_INIT_MESSAGE + i * WORLD_DY for i in range(5)]

WORLD_HEIGHT_JOINED = 100
JOINED_FONT_SIZE = 45
JOINED_TEXTS = [
    "CHARACTER joined the party.",
    "CHARACTER is here.",
    "Welcome, CHARACTER. We hope you brought pizza.",
    "A wild CHARACTER appeared.",
    "CHARACTER just landed.",
    "CHARACTER just slid into the server.",
    "CHARACTER just showed up.",
    "Welcome CHARACTER. Say hi!",
    "CHARACTER hopped into the server.",
    "Everyone welcome CHARACTER!",
    "Glad you're here, CHARACTER!",
    "Good to see you, CHARACTER!",
    "Yay you made it, CHARACTER!",
]
LEFT_TEXTS = [
    "CHARACTER left the party.",
    "CHARACTER has left the server.",
    "CHARACTER disconnected.",
]

PROFPIC_WIDTH = 120
PROFPIC_POSITION = (36, 45)
NAME_FONT_SIZE = 50
TIME_FONT_SIZE = 40
MESSAGE_FONT_SIZE = 50
NAME_POSITION = (190, 53)
TIME_POSITION_Y = 67
NAME_TIME_SPACING = 25
MESSAGE_X = 190
MESSAGE_Y_INIT = 115
MESSAGE_DY = 70
MESSAGE_POSITIONS = [(MESSAGE_X, MESSAGE_Y_INIT + i * MESSAGE_DY) for i in range(5)]

# ── FONTS (gg sans → Whitney fallback) ─────────────────────────────────────────

font_name = "whitney"
for candidate in ["ggsans", "whitney"]:
    if os.path.isdir(os.path.join('..', 'assets', 'fonts', candidate)):
        font_name = candidate
        break

_fp = lambda f: os.path.join(f'../assets/fonts/{font_name}', f)
name_font = ImageFont.truetype(_fp('semibold.ttf'), NAME_FONT_SIZE)
time_font = ImageFont.truetype(_fp('medium.ttf'), TIME_FONT_SIZE)
message_font = ImageFont.truetype(_fp('medium.ttf'), MESSAGE_FONT_SIZE)
message_italic_font = ImageFont.truetype(_fp('medium_italic.ttf'), MESSAGE_FONT_SIZE)
message_bold_font = ImageFont.truetype(_fp('bold.ttf'), MESSAGE_FONT_SIZE)
message_italic_bold_font = ImageFont.truetype(_fp('bold_italic.ttf'), MESSAGE_FONT_SIZE)
message_mention_font = ImageFont.truetype(_fp('semibold.ttf'), MESSAGE_FONT_SIZE)
message_mention_italic_font = ImageFont.truetype(_fp('semibold_italic.ttf'), MESSAGE_FONT_SIZE)
typing_font = ImageFont.truetype(_fp('medium.ttf'), TYPING_FONT_SIZE)
reply_name_font = ImageFont.truetype(_fp('semibold.ttf'), REPLY_NAME_FONT_SIZE)
reply_text_font = ImageFont.truetype(_fp('medium.ttf'), REPLY_FONT_SIZE)

# ── CHARACTER DATA ─────────────────────────────────────────────────────────────

with open('../assets/profile_pictures/characters.json', encoding="utf8") as file:
    characters_dict = json.load(file)

# ── HELPERS ────────────────────────────────────────────────────────────────────


def is_emoji_message(message):
    return bool(message) and all(regex.match(r'^\p{Emoji}+$', char) for char in message.strip())


def _draw_reply_header(template, draw, reply_info, reply_offset):
    """Draw Discord-style reply header with curved connector line."""
    reply_user = reply_info.get("user", "Unknown")
    reply_msg = reply_info.get("message", "")
    if len(reply_msg) > 50:
        reply_msg = reply_msg[:50] + "…"

    reply_color = NAME_FONT_COLOR
    if reply_user in characters_dict:
        reply_color = characters_dict[reply_user]["role_color"]

    top_y = 12
    line_x = REPLY_LINE_X
    r = REPLY_CURVE_RADIUS

    # Vertical stem
    draw.line([(line_x, top_y + r), (line_x, reply_offset - 2)],
              fill=REPLY_LINE_COLOR, width=2)
    # Horizontal bar
    draw.line([(line_x + r, top_y), (line_x + 42, top_y)],
              fill=REPLY_LINE_COLOR, width=2)
    # Curved corner (╭)
    draw.arc([(line_x, top_y), (line_x + 2 * r, top_y + 2 * r)],
             start=180, end=270, fill=REPLY_LINE_COLOR, width=2)

    # Small reply avatar
    avatar_x = line_x + 48
    avatar_y = top_y - 8
    if reply_user in characters_dict:
        pic_path = os.path.join('../assets/profile_pictures',
                                characters_dict[reply_user]["profile_pic"])
        if os.path.isfile(pic_path):
            rpic = Image.open(pic_path)
            rpic.thumbnail((REPLY_AVATAR_SIZE, REPLY_AVATAR_SIZE), Image.ANTIALIAS)
            rmask = Image.new("L", rpic.size, 0)
            ImageDraw.Draw(rmask).ellipse(
                [(0, 0), (REPLY_AVATAR_SIZE, REPLY_AVATAR_SIZE)], fill=255)
            template.paste(rpic, (avatar_x, avatar_y), rmask)

    # Reply username + message text
    name_x = avatar_x + REPLY_AVATAR_SIZE + 10
    with Pilmoji(template) as pilmoji:
        pilmoji.text((name_x, avatar_y + 4), reply_user, reply_color,
                     font=reply_name_font)
        nw = reply_name_font.getbbox(reply_user)[2]
        text_x = name_x + nw + 12
        pilmoji.text((text_x, avatar_y + 4), reply_msg, REPLY_TEXT_COLOR,
                     font=reply_text_font)


# ── CORE RENDERING ────────────────────────────────────────────────────────────


def generate_chat(messages, name_time, profpic_file, color,
                  has_ping=False, reply_info=None):
    """Generate a Discord-style chat message image."""
    name_text = name_time[0]
    time_text = f'Today at {name_time[1]} PM'
    reply_offset = REPLY_HEADER_HEIGHT if reply_info else 0

    name_ascent, _ = name_font.getmetrics()
    time_ascent, _ = time_font.getmetrics()
    baseline_y = NAME_POSITION[1] + reply_offset + name_ascent
    time_position = (
        NAME_POSITION[0] + name_font.getbbox(name_text)[2] + NAME_TIME_SPACING,
        baseline_y - time_ascent
    )

    prof_pic = Image.open(profpic_file)
    prof_pic.thumbnail((sys.maxsize, PROFPIC_WIDTH), Image.ANTIALIAS)
    mask = Image.new("L", prof_pic.size, 0)
    ImageDraw.Draw(mask).ellipse([(0, 0), (PROFPIC_WIDTH, PROFPIC_WIDTH)], fill=255)

    y_increment = 0
    for msg in messages:
        if is_emoji_message(msg):
            bbox = message_font.getbbox("\U0001f480")
            y_increment += (bbox[3] - bbox[1]) + 8

    total_height = WORLD_HEIGHTS_MESSAGE[len(messages) - 1] + y_increment + reply_offset
    bg_color = PING_BG_COLOR if has_ping else WORLD_COLOR
    template = Image.new(mode='RGBA', size=(WORLD_WIDTH, total_height), color=bg_color)
    draw_template = ImageDraw.Draw(template)

    # Reply header
    if reply_info:
        _draw_reply_header(template, draw_template, reply_info, reply_offset)

    pp = (PROFPIC_POSITION[0], PROFPIC_POSITION[1] + reply_offset)
    template.paste(prof_pic, pp, mask)

    np = (NAME_POSITION[0], NAME_POSITION[1] + reply_offset)
    draw_template.text(np, name_text, color, font=name_font)
    draw_template.text(time_position, time_text, TIME_FONT_COLOR, font=time_font)

    y_offset = 0
    for i, message in enumerate(messages):
        message = message.strip()
        if not message:
            continue
        x, base_y = MESSAGE_POSITIONS[i]
        y_pos = base_y + y_offset + reply_offset
        current_x = x

        if is_emoji_message(message):
            with Pilmoji(template) as pilmoji:
                pilmoji.text((current_x, y_pos), message, MESSAGE_FONT_COLOR,
                             font=message_font, emoji_position_offset=(0, 8),
                             emoji_scale_factor=2)
            y_offset += message_font.getbbox(message)[3]
            continue

        tokens = re.split(r'(\*\*|__)', message)
        bold = italic = False
        with Pilmoji(template) as pilmoji:
            for token in tokens:
                if token == '**':
                    bold = not bold
                elif token == '__':
                    italic = not italic
                else:
                    if not token:
                        continue
                    parts = re.split(r'(@\w+)', token)
                    for part in parts:
                        if not part:
                            continue
                        if part.startswith('@'):
                            if bold and italic:
                                fu = message_mention_italic_font
                            elif bold:
                                fu = message_mention_font
                            elif italic:
                                fu = message_mention_italic_font
                            else:
                                fu = message_mention_font
                            bbox = fu.getbbox(part)
                            tw = bbox[2] - bbox[0]
                            tt, tb = bbox[1], bbox[3]
                            pad = 8
                            draw_template.rounded_rectangle(
                                [current_x, y_pos + tt - pad,
                                 current_x + tw + 2 * pad, y_pos + tb + pad],
                                fill=MENTION_BG_COLOR, radius=10)
                            pilmoji.text((current_x + pad, y_pos), part,
                                         MENTION_TEXT_COLOR, font=fu)
                            current_x += tw + 2 * pad
                        else:
                            if bold and italic:
                                fu = message_italic_bold_font
                            elif bold:
                                fu = message_bold_font
                            elif italic:
                                fu = message_italic_font
                            else:
                                fu = message_font
                            pilmoji.text((current_x, y_pos), part,
                                         MESSAGE_FONT_COLOR, font=fu,
                                         emoji_position_offset=(0, 8),
                                         emoji_scale_factor=1.2)
                            current_x += fu.getbbox(part)[2] - fu.getbbox(part)[0]
    return template


def generate_typing_indicator(name, profpic_file, color):
    """Generate Discord-style 'X is typing...' indicator."""
    template = Image.new(mode='RGBA', size=(WORLD_WIDTH, TYPING_HEIGHT), color=WORLD_COLOR)
    draw = ImageDraw.Draw(template)

    dot_x = 50
    dot_y = TYPING_HEIGHT // 2
    dot_r = 6
    dot_gap = 18
    for i, alpha in enumerate([220, 180, 140]):
        cx = dot_x + i * dot_gap
        cy = dot_y - (4 if i == 1 else 0)
        draw.ellipse([(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)],
                     fill=(alpha, alpha, alpha))

    text = f"{name} is typing..."
    tx = dot_x + 3 * dot_gap + 15
    tb = typing_font.getbbox(text)
    ty = (TYPING_HEIGHT - (tb[3] - tb[1])) // 2 - tb[1]
    with Pilmoji(template) as pilmoji:
        pilmoji.text((tx, ty), text, TYPING_TEXT_COLOR, font=typing_font)
    return template


def generate_slide_fade_frames(final_image, num_frames=ANIMATION_NUM_FRAMES,
                                slide_px=ANIMATION_SLIDE_PX):
    """Generate fade-in + slide-up animation frames."""
    w, h = final_image.size
    bg = Image.new('RGBA', (w, h), WORLD_COLOR)
    frames = []
    for i in range(1, num_frames + 1):
        progress = i / (num_frames + 1)
        y_shift = int(slide_px * (1 - progress))
        shifted = Image.new('RGBA', (w, h), WORLD_COLOR)
        if 0 < y_shift < h:
            region = final_image.crop((0, 0, w, h - y_shift))
            shifted.paste(region, (0, y_shift))
        else:
            shifted = final_image.copy()
        blended = Image.blend(bg, shifted, progress)
        frames.append(blended)
    return frames


def generate_joined_message(name, time, template_str, arrow_x, color=NAME_FONT_COLOR):
    before_text, after_text = template_str.split("CHARACTER", 1) if "CHARACTER" in template_str else ("", "")
    time_text = f'Today at {time} PM'
    template_img = Image.new(mode='RGBA', size=(WORLD_WIDTH, WORLD_HEIGHT_JOINED), color=WORLD_COLOR)
    draw_template = ImageDraw.Draw(template_img)
    arrow = Image.open("../assets/green_arrow.png")
    arrow.thumbnail((40, 40))
    text_x = arrow_x + arrow.width + 60
    text_bbox = message_font.getbbox("Sample")
    text_height = text_bbox[3] - text_bbox[1]
    text_y = (WORLD_HEIGHT_JOINED - text_height) // 2
    ma, md = message_font.getmetrics()
    tth = ma + md
    arrow_y = text_y + (tth - arrow.height) // 2
    template_img.paste(arrow, (arrow_x, arrow_y), arrow)
    bw = message_font.getbbox(before_text)[2] if before_text else 0
    nw = name_font.getbbox(name)[2]
    with Pilmoji(template_img) as pilmoji:
        if before_text:
            pilmoji.text((text_x, text_y), before_text, JOINED_FONT_COLOR, font=message_font)
        pilmoji.text((text_x + bw, text_y), name, color, font=name_font)
        if after_text:
            pilmoji.text((text_x + bw + nw, text_y), after_text, JOINED_FONT_COLOR, font=message_font)
        tw = bw + nw + message_font.getbbox(after_text)[2]
        tx = text_x + tw + 30
        ty2 = text_y + ma - time_font.getmetrics()[0]
        pilmoji.text((tx, ty2), time_text, TIME_FONT_COLOR, font=time_font)
    return template_img


def generate_leave_message(name, time, color=NAME_FONT_COLOR):
    template_str = random.choice(LEFT_TEXTS)
    before_text, after_text = template_str.split("CHARACTER", 1) if "CHARACTER" in template_str else ("", "")
    time_text = f'Today at {time} PM'
    template_img = Image.new(mode='RGBA', size=(WORLD_WIDTH, WORLD_HEIGHT_JOINED), color=WORLD_COLOR)
    draw_template = ImageDraw.Draw(template_img)
    arrow_x = random.randint(50, 80)
    arrow = Image.open("../assets/green_arrow.png")
    arrow.thumbnail((40, 40))
    arrow = arrow.transpose(Image.FLIP_LEFT_RIGHT)
    text_x = arrow_x + arrow.width + 60
    text_bbox = message_font.getbbox("Sample")
    text_height = text_bbox[3] - text_bbox[1]
    text_y = (WORLD_HEIGHT_JOINED - text_height) // 2
    ma, md = message_font.getmetrics()
    tth = ma + md
    arrow_y = text_y + (tth - arrow.height) // 2
    template_img.paste(arrow, (arrow_x, arrow_y), arrow)
    bw = message_font.getbbox(before_text)[2] if before_text else 0
    nw = name_font.getbbox(name)[2]
    with Pilmoji(template_img) as pilmoji:
        if before_text:
            pilmoji.text((text_x, text_y), before_text, JOINED_FONT_COLOR, font=message_font)
        pilmoji.text((text_x + bw, text_y), name, color, font=name_font)
        if after_text:
            pilmoji.text((text_x + bw + nw, text_y), after_text, JOINED_FONT_COLOR, font=message_font)
        tw = bw + nw + message_font.getbbox(after_text)[2]
        tx = text_x + tw + 30
        ty2 = text_y + ma - time_font.getmetrics()[0]
        pilmoji.text((tx, ty2), time_text, TIME_FONT_COLOR, font=time_font)
    return template_img


def generate_joined_message_stack(joined_messages, hour):
    total_height = WORLD_HEIGHT_JOINED * len(joined_messages)
    template_img = Image.new(mode='RGBA', size=(WORLD_WIDTH, total_height), color=WORLD_COLOR)
    for idx, key in enumerate(joined_messages):
        name = key.split(' ')[1].split('$^')[0]
        color = characters_dict[name]["role_color"]
        time_str = f'{hour}:{joined_messages[key][2].minute:02d}'
        joined_img = generate_joined_message(name, time_str, joined_messages[key][0],
                                             joined_messages[key][1], color)
        template_img.paste(joined_img, (0, idx * WORLD_HEIGHT_JOINED))
    return template_img


# ── FILE DIALOG ────────────────────────────────────────────────────────────────

def get_filename():
    from PyQt5.QtWidgets import QApplication, QFileDialog
    app = QApplication(sys.argv)
    options = QFileDialog.Options()
    filename, _ = QFileDialog.getOpenFileName(
        None, "Select File", "",
        "Scenario Files (*.json);;Text Files (*.txt);;All Files (*)",
        options=options)
    app.exit()
    return filename


# ── LEGACY .txt PIPELINE ──────────────────────────────────────────────────────

def save_images(lines, init_time, dt=30):
    os.makedirs('../chat', exist_ok=True)
    name_up_next = True
    current_time = init_time
    current_name = None
    current_lines = []
    msg_number = 1
    joined_messages = {}
    name_time = []
    for line in lines:
        if line == '':
            name_up_next = True
            current_lines = []
            name_time = []
            joined_messages = {}
            continue
        if line.startswith('#'):
            joined_messages = {}
            continue
        if line.startswith("WELCOME "):
            joined_messages[line] = [random.choice(JOINED_TEXTS), random.randint(50, 80), current_time]
            hour = current_time.hour % 12 or 12
            image = generate_joined_message_stack(joined_messages, hour)
            image.save(f'../chat/{msg_number:03d}.png')
            current_time += datetime.timedelta(seconds=dt)
            msg_number += 1
            continue
        else:
            joined_messages = {}
        if name_up_next:
            current_name = line.split(':')[0]
            hour = current_time.hour % 12 or 12
            name_time = [current_name, f'{hour}:{current_time.minute:02d}']
            name_up_next = False
            continue
        current_lines.append(line.split('$^')[0])
        image = generate_chat(
            messages=current_lines, name_time=name_time,
            profpic_file=os.path.join('../assets/profile_pictures', characters_dict[current_name]["profile_pic"]),
            color=characters_dict[current_name]["role_color"])
        image.save(f'../chat/{msg_number:03d}.png')
        current_time += datetime.timedelta(seconds=dt)
        msg_number += 1


# ── SCENARIO-BASED PIPELINE ──────────────────────────────────────────────────

def save_images_from_scenario(scenario, init_time):
    """Generate chat images with typing indicators, animations, and replies."""
    os.makedirs('../chat', exist_ok=True)
    frame_data = []
    msg_number = 1
    current_time = init_time
    current_block_user = None
    current_block_messages = []
    current_block_name_time = []

    for entry in scenario:
        user = entry.user
        char_data = characters_dict.get(user)
        if not char_data:
            print(f"\u26a0 Warning: User '{user}' not in characters.json, skipping.")
            continue

        color = char_data["role_color"]
        profpic_path = os.path.join('../assets/profile_pictures', char_data["profile_pic"])
        hour = current_time.hour % 12 or 12
        time_str = f'{hour}:{current_time.minute:02d}'
        reply_info = entry.reply_to if hasattr(entry, 'reply_to') else None

        if entry.action == "join":
            current_block_user = None
            current_block_messages = []
            template_str = random.choice(JOINED_TEXTS)
            arrow_x = random.randint(50, 80)
            image = generate_joined_message(user, time_str, template_str, arrow_x, color)
            # Fade-in animation
            for af in generate_slide_fade_frames(image):
                p = f'../chat/{msg_number:03d}.png'
                af.save(p)
                frame_data.append((p, ANIMATION_FRAME_DURATION, None))
                msg_number += 1
            path = f'../chat/{msg_number:03d}.png'
            image.save(path)
            frame_data.append((path, entry.delay_before, entry.sound))
            msg_number += 1
            current_time += datetime.timedelta(seconds=int(entry.delay_before))

        elif entry.action == "leave":
            current_block_user = None
            current_block_messages = []
            image = generate_leave_message(user, time_str, color)
            for af in generate_slide_fade_frames(image):
                p = f'../chat/{msg_number:03d}.png'
                af.save(p)
                frame_data.append((p, ANIMATION_FRAME_DURATION, None))
                msg_number += 1
            path = f'../chat/{msg_number:03d}.png'
            image.save(path)
            frame_data.append((path, entry.delay_before, entry.sound))
            msg_number += 1
            current_time += datetime.timedelta(seconds=int(entry.delay_before))

        elif entry.action == "typing":
            current_block_user = user
            current_block_messages = []
            current_block_name_time = [user, time_str]

            # Typing indicator
            typing_img = generate_typing_indicator(user, profpic_path, color)
            tp = f'../chat/{msg_number:03d}.png'
            typing_img.save(tp)
            typing_dur = calculate_typing_duration(entry.message)
            frame_data.append((tp, typing_dur, "typing"))
            msg_number += 1

            # Message with fade-in animation
            current_block_messages.append(entry.message)
            msg_img = generate_chat(
                messages=current_block_messages, name_time=current_block_name_time,
                profpic_file=profpic_path, color=color,
                has_ping=entry.has_ping, reply_info=reply_info)
            for af in generate_slide_fade_frames(msg_img):
                p = f'../chat/{msg_number:03d}.png'
                af.save(p)
                frame_data.append((p, ANIMATION_FRAME_DURATION, None))
                msg_number += 1
            mp = f'../chat/{msg_number:03d}.png'
            msg_img.save(mp)
            frame_data.append((mp, entry.delay_before, entry.sound))
            msg_number += 1
            current_time += datetime.timedelta(seconds=int(entry.delay_before))

        elif entry.action == "message":
            if current_block_user != user:
                current_block_user = user
                current_block_messages = []
                current_block_name_time = [user, time_str]
            current_block_messages.append(entry.message)
            if len(current_block_messages) > 5:
                current_block_messages = current_block_messages[-5:]
            msg_img = generate_chat(
                messages=current_block_messages, name_time=current_block_name_time,
                profpic_file=profpic_path, color=color,
                has_ping=entry.has_ping, reply_info=reply_info)
            for af in generate_slide_fade_frames(msg_img):
                p = f'../chat/{msg_number:03d}.png'
                af.save(p)
                frame_data.append((p, ANIMATION_FRAME_DURATION, None))
                msg_number += 1
            mp = f'../chat/{msg_number:03d}.png'
            msg_img.save(mp)
            frame_data.append((mp, entry.delay_before, entry.sound))
            msg_number += 1
            current_time += datetime.timedelta(seconds=int(entry.delay_before))

    return frame_data


if __name__ == '__main__':
    print('Please run the main.py script!')