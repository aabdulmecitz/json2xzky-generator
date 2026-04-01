# Text 2 Beluga 🎥💬

Easily convert `scenario.json` files into full-fledged Beluga-style Discord conversation videos (using our new Web Simulator) with a plethora of text formatting options, sound effects, and much more customisation within seconds!

## Features ✨

- 🖥️ **Real-Time Web Simulator** - Generate Discord-style messages using a fully automated local HTML/JS interface modeled perfectly after the **2026 Discord UI**.
- 🎬 **OBS Capturing Ready** - Dedicated "Clean Recording Mode" with 1080x1920 viewport container, hidden UX elements, and synced typing delays for perfect TikTok/Shorts capture!
- 🔊 **Sound Effect Integration** - Add impact sounds, join notifications, and Discord core typing/ping sounds synchronized perfectly to message bubbles.
- 🤓 **Advanced Formatting Support**:
    - **Bold** and *italic* text
    - Mentions (`@Character`)
    - Native Thread Reply UI Support.
    - True-to-life typing indicators (`duration = text_length * 0.05s`).
    - Smart batching of consecutive messages.

## Prerequisites 📋

- Any modern web browser (Edge, Chrome, Firefox).
- Built-in Local Host (Optional but recommended for loading audio). *`python -m http.server 8000`*

## Configuration 🛠

Before generating videos, configure your profiles:

1. Add profile pictures in `assets/profile_pictures/`
2. Map your characters in `assets/profile_pictures/characters.json`
```json
{
    "Billy": {
        "profile_pic": "perm/billy.jpeg",
        "role_color": "#ffffff"
    }
}
```

## Scenario Script Format 📜

Create a `.json` scenario file (see `assets/example/example_scenario.json` for a live example) with your sequence of events. 

### JSON Schema

```json
[
  {
    "id": 1,
    "user_id": "Billy",
    "message_content": "this server was peaceful",
    "action": "message",
    "reply_to_id": null,
    "pause_after": 2.0,
    "sound": "softmessage"
  }
]
```

#### Fields Breakdown

1. `id`: Sequential integer needed to target replies.
2. `user_id`: Must match a user existing within `characters.json`.
3. `message_content`: Content of the message. Markdown (like **bold** or __italic__) is supported.
4. `action`: One of (`join`, `leave`, `message`, `typing`).
5. `reply_to_id`: Provide the `id` of an earlier message if you want to create a Thread Reply embed. Use `null` if none.
6. `pause_after`: Time in seconds to wait **after** the action is completed before performing the next step in the JSON file.
7. `sound`: Exact base-name (without `.mp3`) of your audio file within `assets/sounds/mp3/`. Fallback default is standard discord ping.

## Running the Web Simulator 🚀

1. Navigate to the `web_player/` directory.
2. Start up a basic local server if your browser restricts local Fetch API due to CORS.
    ```bash
    cd web_player
    python -m http.server
    ```
3. Open `http://localhost:8000` in your web browser.
4. Click "Choose File" and upload your specific `scenario.json` file.
5. Hit **Start Simulator**.
6. The window will open into fullscreen, hide elements, and lock exactly into a vertical phone aspect-ratio of `1080x1920`. Begin capturing your window on OBS immediately!

## Legacy Python Compiler (Optional)

_Please note: If you are looking for the former static image script generation over `txt` syntax, the `/scripts` directory retains logic covering static MP4 compilation. It expects `example_script.txt` files and compiles heavily with FFmpeg. Moving forward, the Web Simulator JSON flow is the recommended high-fidelity production path._

## Note Regarding Fonts 🗒️

The default font loaded is `Whitney`. If you need exact Discord parity, ensure your font `.ttf` variants are located inside the `assets/fonts/whitney/` folder. The app natively mounts these fonts visually matching Discord's exact typography flow. # json2xzky-generator
