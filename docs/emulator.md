# Preview M Drive

The emulator runs the app with the repository's native runtime. The browser draws its command
stream with the same renderer code compiled to WebAssembly.

```sh
node kit/tools/emu.js m_drive --preview-only
```

Open <http://localhost:8077>. The `--preview-only` flag stages the app without BMW's SDK.
It does not create an installable package.

| Input | Action |
|---|---|
| Mouse click on the screen | Touch |
| Mouse wheel, `[` or `]` | Turn the iDrive controller |
| Enter | Press the controller |
| Arrow keys | Tilt the controller |
| Backspace | Back |
| H | Home |
| O | Open M Drive again |

The panel changes the app's settings, feeds demo or manual signals, and shows logs.
The **Screenshot** button saves the native screen at 1920 × 720 pixels.

Saving a file under `apps/m_drive` or `kit/runtime` rebuilds and restarts the app.
The controls are local to the emulator. It has no vehicle diagnostic connection.

Use `--port 8080` for another port, `--no-touch` to inspect the HMI button-bar fallback,
or `--bg /path/to/screen.png` for a 1920 × 720 screenshot of your own HMI frame.

The server listens only on `127.0.0.1`. Stop it with Ctrl+C.
