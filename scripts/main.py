import curses
import datetime
import sys
import textwrap
import os
from playsound import playsound

# Import from refactored modules
from generate_chat import get_filename, save_images_from_scenario
from compile_images import gen_vid
from scenario_engine import load_scenario, calculate_typing_duration
from script_validator import validate_scenario, validate_script_lines

# Try to import pyfiglet for cool ASCII art. Fallback gracefully if not available.
try:
    from pyfiglet import figlet_format
except ImportError:
    def figlet_format(text):
        return text.upper()


# ── SCREEN DRAWING ─────────────────────────────────────────────────────────────

def draw_screen(stdscr, header, description, menu_items=None, current_row=None, left_margin=4):
    stdscr.clear()
    height, width = stdscr.getmaxyx()

    header_text = figlet_format(header)
    header_lines = header_text.splitlines()
    y = 1
    for line in header_lines:
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(y, left_margin, line[:width - left_margin - 4])
        stdscr.attroff(curses.color_pair(1))
        y += 1

    desc_width = width - left_margin * 2
    wrapped_desc = textwrap.fill(description, width=desc_width)
    for line in wrapped_desc.splitlines():
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(y, left_margin, line)
        stdscr.attroff(curses.color_pair(3))
        y += 1

    if menu_items is not None:
        y += 1
        for idx, item in enumerate(menu_items):
            if idx == current_row:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(y, left_margin, f"> {item}")
                stdscr.attroff(curses.color_pair(2))
            else:
                stdscr.attron(curses.color_pair(3))
                stdscr.addstr(y, left_margin, f"  {item}")
                stdscr.attroff(curses.color_pair(3))
            y += 1

    stdscr.refresh()


# ── GENERATE VIDEO ─────────────────────────────────────────────────────────────

def run_generate_chat(stdscr):
    draw_screen(stdscr, "Text 2 Beluga", "Select a scenario file (.json) or legacy script (.txt)...\n\n", menu_items=[])
    curses.napms(500)

    # Cleanup previous output
    final_video = '../final_video.mp4'
    if os.path.isfile(final_video):
        os.remove(final_video)
    if os.path.exists('../chat'):
        for file in os.listdir('../chat'):
            os.remove(os.path.join('../chat', file))
        os.rmdir('../chat')

    filename = get_filename()
    if not filename:
        draw_screen(stdscr, "No Selection", "Press Enter to return to the main menu...\n\n", menu_items=[])
        stdscr.getch()
        return

    if filename.endswith('.json'):
        # ── NEW: JSON Scenario Pipeline ────────────────────────────────
        try:
            draw_screen(stdscr, "Loading Scenario...", f"Loading: {os.path.basename(filename)}\n\n", menu_items=[])
            stdscr.refresh()

            scenario = load_scenario(filename)
            draw_screen(
                stdscr, "Reading Chats...",
                f"Loaded {len(scenario)} entries. Generating chat images with typing indicators...\n\n",
                menu_items=[]
            )
            stdscr.refresh()

            current_time = datetime.datetime.now()
            frame_data = save_images_from_scenario(scenario, init_time=current_time)

            draw_screen(stdscr, "Compiling Video...", "Compiling images into cinematic video with sound effects...\n\n", menu_items=[])
            stdscr.refresh()

            gen_vid(frame_data)

            draw_screen(
                stdscr, "Completed!",
                f"Your Beluga-like video has been generated! ({len(frame_data)} frames)\nEnjoy :)\nPress Enter to return to the main menu...\n\n",
                menu_items=[]
            )
            stdscr.getch()

        except Exception as e:
            draw_screen(stdscr, "Error", f"{e}\nPress Enter to return to the main menu...\n\n", menu_items=[])
            stdscr.getch()
            return

    else:
        # ── LEGACY: .txt Pipeline ──────────────────────────────────────
        try:
            with open(filename, encoding="utf8") as f:
                lines = f.read().splitlines()
        except Exception as e:
            draw_screen(stdscr, "Error", f"{e}\nPress Enter to return to the main menu...\n\n", menu_items=[])
            stdscr.getch()
            return

        from generate_chat import save_images
        from compile_images import gen_vid_legacy

        current_time = datetime.datetime.now()
        draw_screen(stdscr, "Reading Chats...", "Please wait while chat images are being generated...\n\n", menu_items=[])
        stdscr.refresh()
        save_images(lines, init_time=current_time)

        draw_screen(stdscr, "Compiling Video...", "Compiling images into video. Please wait...\n\n", menu_items=[])
        stdscr.refresh()
        gen_vid_legacy(filename)

        draw_screen(stdscr, "Completed!", "Your Beluga-like video has been generated. Enjoy :)\nPress Enter to return to the main menu...\n\n", menu_items=[])
        stdscr.getch()


# ── RUN WEB SIMULATOR ──────────────────────────────────────────────────────────

def run_web_simulator(stdscr):
    draw_screen(stdscr, "Web Simulator", "Starting local HTTP server and launching browser...\nKeep the browser open to record. Press CTRL+C in the terminal to stop the server.\n\n", menu_items=[])
    stdscr.refresh()
    
    # End curses mode temporarily so terminal stdout works visually
    curses.endwin()
    try:
        from play_web import run_server
        run_server()
    except Exception as e:
        print(f"Server stopped: {e}")
    finally:
        # Re-initialize curses when user stops the server
        stdscr.clear()
        stdscr.refresh()


# ── VALIDATE SCRIPT ────────────────────────────────────────────────────────────

def run_validate_script(stdscr):
    draw_screen(stdscr, "Text 2 Beluga", "Select a scenario (.json) or script (.txt) file to validate...\n\n", menu_items=[])
    curses.napms(500)

    filename = get_filename()
    if not filename:
        draw_screen(stdscr, "No Selection", "Press Enter to return to the main menu...\n\n", menu_items=[])
        stdscr.getch()
        return

    draw_screen(stdscr, "Validating...", "Please wait while the file is being validated...\n\n", menu_items=[])
    stdscr.refresh()
    curses.napms(500)

    if filename.endswith('.json'):
        errors = validate_scenario(filename)
    else:
        try:
            with open(filename, encoding="utf8") as f:
                lines = f.read().splitlines()
            errors = validate_script_lines(lines)
        except Exception as e:
            draw_screen(stdscr, "Error", f"{e}\nPress Enter to return to the main menu...\n\n", menu_items=[])
            stdscr.getch()
            return

    if errors:
        header = "Errors"
        description = "Validation found issues:\n" + "\n".join(errors)
    else:
        header = "Seems Good!"
        description = "Validation successful: no problems found."

    draw_screen(stdscr, header, description + "\n\nPress Enter to return to the main menu...\n\n", menu_items=[])
    stdscr.getch()


# ── INSTRUCTIONS ───────────────────────────────────────────────────────────────

def print_instructions(stdscr, header, description, current_row, left_margin):
    menu_items = ["Scenario JSON Format", "Legacy Script Format", "Available Sound Effects", "< Back"]
    while True:
        draw_screen(stdscr, header, description, menu_items, current_row, left_margin)
        key = stdscr.getch()

        if key in [curses.KEY_UP, ord('k')]:
            current_row = (current_row - 1) % len(menu_items)
        elif key in [curses.KEY_DOWN, ord('j')]:
            current_row = (current_row + 1) % len(menu_items)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if current_row == 0:
                scenario_format(stdscr, 0, left_margin)
            elif current_row == 1:
                formatting(stdscr, 0, left_margin)
            elif current_row == 2:
                sounds(stdscr, 0, left_margin)
            elif current_row == 3:
                break


def scenario_format(stdscr, current_row, left_margin):
    menu_items = [
        "--SCENARIO__JSON__FORMAT--",
        "",
        "- The scenario file is a JSON array of entry objects.",
        "- Each entry has the following fields:",
        "  - user (string): Character name (must exist in characters.json)",
        "  - message (string): Message text (supports **bold**, __italic__, @mentions, emojis)",
        "  - action (string): One of: typing, message, join, leave",
        "  - delay_before (number): Seconds to display this frame",
        "  - has_ping (boolean): If true, highlights the message background",
        "  - sound (string|null): Sound effect name from assets/sounds/mp3/",
        "",
        "--ACTION__TYPES--",
        "",
        "- typing: Shows a 'User is typing...' indicator first, then the message",
        "  Duration of typing is auto-calculated from message length (50ms/char + variance)",
        "- message: Shows the message directly (stacks with previous messages from same user)",
        "- join: Shows a 'User joined the party' notification",
        "- leave: Shows a 'User left the party' notification",
        "",
        "- See assets/example/example_scenario.json for a working example.",
        "",
        "< Back"
    ]
    header = "Scenario Format"
    description = "> The new JSON-based scenario format gives you full cinematic control:"

    while True:
        draw_screen(stdscr, header, description, menu_items, current_row, left_margin)
        key = stdscr.getch()

        if key in [curses.KEY_UP, ord('k')]:
            current_row = (current_row - 1) % len(menu_items)
        elif key in [curses.KEY_DOWN, ord('j')]:
            current_row = (current_row + 1) % len(menu_items)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if current_row == (len(menu_items) - 1):
                break


def formatting(stdscr, current_row, left_margin):
    menu_items = [
        "--IMPORTANT__POINTS--",
        "- Any custom characters should be configured in [assets/profile_pictures/characters.json] and their profile pictures should be present.",
        "- All the dependencies listed in [requirements.txt] should be installed.",
        "",
        "--FORMATTING__GUIDELINES--(legacy .txt format)",
        "- Lines beginning with a hashtag (#) are treated as comments and are ignored.",
        "- To display a \"character joined\" message, the line should begin with WELCOME followed by the character name ~ [WELCOME CharacterName]",
        "- To make a character say something, Write the character's name immediately followed by a colon and it's messages in the subsequent lines.",
        "- Each message should be (MANDATORILY) immediately followed by \"$^\" and a number that indicated for how many seconds that message should be shown.",
        "- Each duration can be (OPTIONALLY) immediately followed by \"#!\" and a sound effect name to play that sound in the video when that message is shown.",
        "- There should be an empty line between a character's message and the next character's name.",
        "- Message text enclosed within ** and ** will be shown in bold.",
        "- Message text enclosed within __ and __ will be shown in italics.",
        "- Emojis are supported in messages.",
        "- Different characters can be mentioned in a message by writing \"@\" followed by a character's name.",
        "",
        "- An example script has been provided to give an idea and get you started.",
        "",
        "< Back"
    ]
    header = "Formatting"
    description = "> Your chat script should be written in a [.txt] file with the following formatting guidelines:"

    while True:
        draw_screen(stdscr, header, description, menu_items, current_row, left_margin)
        key = stdscr.getch()

        if key in [curses.KEY_UP, ord('k')]:
            current_row = (current_row - 1) % len(menu_items)
        elif key in [curses.KEY_DOWN, ord('j')]:
            current_row = (current_row + 1) % len(menu_items)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if current_row == (len(menu_items) - 1):
                break


def sounds(stdscr, current_row, left_margin):
    header = "Sounds"
    description = "> Use the arrow keys to navigate through the available sound effects. Press [ENTER] to listen to the selected sound effect."

    menu_items = []
    for file in os.listdir(os.path.join("..", "assets", "sounds", "mp3")):
        if file.endswith(".mp3"):
            menu_items.append(file.replace(".mp3", ""))
    menu_items.append("                     ")
    menu_items.append("< Back")

    while True:
        draw_screen(stdscr, header, description, menu_items, current_row, left_margin)
        key = stdscr.getch()

        if key in [curses.KEY_UP, ord('k')]:
            current_row = (current_row - 1) % len(menu_items)
        elif key in [curses.KEY_DOWN, ord('j')]:
            current_row = (current_row + 1) % len(menu_items)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if current_row == (len(menu_items) - 1):
                break
            elif current_row == (len(menu_items) - 2):
                continue
            else:
                playsound(f'{os.path.join("..", "assets", "sounds", "mp3", menu_items[current_row] + ".mp3")}')


# ── MAIN MENU ─────────────────────────────────────────────────────────────────

def curses_menu(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)

    menu_items = [
        "Launch Real-Time Web Simulator (For Screen Recording)",
        "Generate Video (Legacy MP4 Render)", 
        "Validate Script", 
        "Instructions", 
        "", 
        "Exit"
    ]
    current_row = 0
    left_margin = 4

    while True:
        header = "Text 2 Beluga"
        description = (
            "> Welcome to Text2Beluga! Generate Beluga-like videos from JSON scenarios "
            "or legacy text scripts. Features: typing indicators, cinematic sequencing, "
            "and sound effects. It's absolutely free!"
        )
        draw_screen(stdscr, header, description, menu_items, current_row, left_margin)
        key = stdscr.getch()

        if key in [curses.KEY_UP, ord('k')]:
            current_row = (current_row - 1) % len(menu_items)
        elif key in [curses.KEY_DOWN, ord('j')]:
            current_row = (current_row + 1) % len(menu_items)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if current_row == 0:
                run_web_simulator(stdscr)
            elif current_row == 1:
                run_generate_chat(stdscr)
            elif current_row == 2:
                run_validate_script(stdscr)
            elif current_row == 3:
                print_instructions(stdscr, header, description, current_row, left_margin)
            elif current_row == 5:
                break


def main():
    curses.wrapper(curses_menu)


if __name__ == '__main__':
    main()
