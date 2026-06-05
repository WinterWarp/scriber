# Scriber

Handwrite with a stylus (or mouse/touch) to input text into apps on GNOME.

You write on a canvas, Scriber recognizes the handwriting, and the text goes to
your target app — by default via the **clipboard** (you paste with `Ctrl+V`),
or optionally **auto-typed** into the focused window.

Built for **NixOS + GNOME (Wayland)**. GTK4 front end, pluggable recognition and
text-delivery backends.

```
┌─ Scriber ───────────────────────────────[Recognize][≡]┐
│ [Clear] [Undo stroke] [Auto] [Append]                  │
│ ┌────────────────────────────────────────────────────┐│
│ │              ✍  write here  (ruled guides)          ││
│ └────────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────────┐│
│ │ recognized text (editable)                          ││
│ └────────────────────────────────────────────────────┘│
│ Recognized & copied — paste with Ctrl+V [Clear][Type][Copy]│
└────────────────────────────────────────────────────────┘
```

## Run it

From this directory:

```sh
nix develop -c python -m scriber      # quick run (dev shell)
# or
nix run                               # build + run the packaged app
```

To get a stable `scriber` command (useful for the auto-type shortcut below):

```sh
nix profile install .#default
scriber                               # launches the window
```

## Workflow

1. Write a word or line on the canvas.
2. **Recognize** (`Ctrl+Enter`). The text appears in the editable box and — with
   the default clipboard method — is copied automatically.
3. Switch to your target app and **paste** (`Ctrl+V`). Fix any mistakes in the
   text box before copying if needed.

Toolbar:

| Control | What it does |
|---|---|
| **Recognize** (`Ctrl+Enter`) | Recognize the current strokes |
| **Clear** (`Ctrl+L`) | Wipe the canvas |
| **Undo stroke** (`Ctrl+Z`) | Remove the last stroke |
| **Auto** | Recognize automatically a moment after you stop writing |
| **Append** | Add each recognition to the existing text (write sentences word-by-word) |
| **Copy** (`Ctrl+Shift+C`) / **Auto-type** | Send the text to the clipboard / type it |
| **Compact mode** (`Ctrl+M`, or the ⤢ header button) | Shrink to a small, always-on-top palette for writing beside your app |

## Recognition engines

Switch in the **≡ menu → Engine** (or set `engine` in the config file).

- **Tesseract** (default, offline) — private, free, no network. Best on neat,
  separated block letters; weaker on cursive.
- **Claude (cloud)** — much higher accuracy including cursive. Needs an API key:

  ```sh
  export ANTHROPIC_API_KEY=sk-ant-...
  nix develop -c python -m scriber
  ```

  Sends the rendered handwriting image to the Anthropic API (small per-call cost).
  Model defaults to `claude-haiku-4-5-20251001`; change `claude_model` in config
  (e.g. `claude-sonnet-4-6` for tougher handwriting).

- **OpenRouter / OpenAI-compatible** — route through OpenRouter (or OpenAI, Groq,
  Together, or a local llama.cpp / LM Studio server). Uses the OpenAI Chat
  Completions vision API, so you can pick *any* vision model. To use Claude via
  OpenRouter:

  ```sh
  export OPENROUTER_API_KEY=sk-or-...
  nix develop -c python -m scriber          # pick engine + model in the ≡ menu
  ```

  The **model is editable in the ≡ menu** (the field appears when a cloud engine is
  selected). Defaults: `openai_base_url = "https://openrouter.ai/api/v1"`,
  `openai_model = "anthropic/claude-sonnet-4.5"` (other vision slugs:
  `anthropic/claude-opus-4.8`, `openai/gpt-4o`, … see openrouter.ai/models).
  The key is read from the env var named by `openai_api_key_env` (default
  `OPENROUTER_API_KEY`) so it never lands in the config file. For a **local**
  server set `openai_base_url` to e.g. `http://localhost:11434/v1`; no key needed.

The recognizer interface is `scriber/recognizers/base.py` — adding another backend
(local TrOCR, a stroke-based engine, …) is a small, self-contained file.

## Auto-typing into the focused app (optional, needs setup)

The clipboard path needs no privileges and is the default. If you want Scriber to
**type directly** into the focused window, enable `ydotool` (it injects via the
kernel `uinput` device, which is what works on GNOME Wayland).

1. Add to your NixOS configuration and rebuild:

   ```nix
   programs.ydotool.enable = true;
   ```

   ```sh
   sudo nixos-rebuild switch
   ```

   Then **log out and back in** so the `ydotoold` user service starts and uinput
   access applies. (Verify: `ls "$XDG_RUNTIME_DIR/.ydotool_socket"`.)

2. In Scriber, set **≡ menu → Send text via → Auto-type (ydotool)**.

Two ways to use it:

- **In-app button** — click **Auto-type**; a short countdown lets you click your
  target window, then the text is typed. (The text is also copied as a fallback.)
- **Global shortcut (hands-free)** — bind a key to type the last result into
  whatever is focused, so you never have to juggle window focus:

  GNOME *Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts → +*

  ```
  Name:    Scriber type
  Command: scriber type-last        # after `nix profile install .#default`
  ```

  Workflow: write in Scriber → focus your target app → press the shortcut.

## Compact mode (small, always-on-top)

For quick word-by-word input — especially with **auto-type** — toggle **Compact
mode** with the ⤢ button in the header or `Ctrl+M`. The window shrinks to a small
palette (just the canvas plus Recognize / Auto-type / Copy), hiding the toolbar
and the recognized-text box, so it fits beside your target app. Press `Ctrl+M`
again to return to the full window. Set `compact = true` in the config to have
Scriber open this way every time.

**Staying on top** is best-effort, because GTK4 has no portable "keep above":

- On **X11** sessions, Scriber uses `wmctrl` (if installed) to pin the window
  while compact, and unpins it when you leave compact mode.
- On **Wayland / GNOME**, only the compositor can pin a window. Right-click the
  title bar and choose **Always on Top** (Scriber shows a one-time reminder).
  The window stays small either way, which is the part that matters for
  auto-type.

Turn the keep-above behaviour off with **≡ menu → Keep on top in compact mode**.

## Configuration

`~/.config/scriber/config.toml` (flat keys). The **≡ menu → Save as defaults**
button writes it for you. Defaults:

```toml
engine = "tesseract"          # "tesseract" | "claude" | "openai"
tesseract_lang = "eng"
tesseract_psm = 7             # 7 = single line; 6 = uniform block (multi-line)
claude_model = "claude-haiku-4-5-20251001"
openai_base_url = "https://openrouter.ai/api/v1"   # "openai" engine target
openai_model = "anthropic/claude-sonnet-4.5"       # any vision model on the endpoint
openai_api_key_env = "OPENROUTER_API_KEY"          # env var the key is read from
input_method = "clipboard"    # "clipboard" | "ydotool"
append_space = true           # trailing space when auto-typing
autotype_delay = 1.2          # countdown seconds before auto-typing
guide_lines = true
stroke_width = 3.0
append = false                # accumulate successive recognitions
compact = false               # open as a small palette (toolbar/text box hidden)
always_on_top = true          # keep compact window above others (best-effort; see below)
```

## Limitations & notes

- **Tesseract is OCR for printed text**; it does okay on tidy printing but
  struggles with cursive/fast writing. Use the Claude engine for real accuracy.
- **Wayland focus**: a normal window holds keyboard focus while you write, so
  auto-typing needs either the in-app countdown (click your target) or the global
  `type-last` shortcut (fires while your target is focused). The clipboard path
  sidesteps this entirely.
- Strokes are rendered to a clean, upscaled black-on-white image before
  recognition; the raw stroke data is also used for undo and (for Tesseract) a
  tighter crop.

## Project layout

```
scriber/
  app.py                 GTK4 window + wiring
  canvas.py              stroke capture, smoothing, PNG export
  config.py              TOML config + last-text cache
  cli.py                 entry point (GUI / `type-last`)
  recognizers/           base.py, tesseract.py, claude.py, make_recognizer()
  injectors/             base.py, clipboard.py, ydotool.py, make_injector()
tests/smoke.py           headless end-to-end check
flake.nix                dev shell + packaged app
```

Run the headless checks any time:

```sh
nix develop -c env PYTHONPATH=$PWD python tests/smoke.py
```
