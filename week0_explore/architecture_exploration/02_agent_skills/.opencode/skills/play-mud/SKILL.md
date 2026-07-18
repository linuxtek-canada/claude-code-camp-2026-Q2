---
name: play-mud
description: Use when playing or interacting with a text-based MUD game running locally, especially tBAMUD or CircleMUD servers on localhost:4000, when given specific in-game commands to execute
---

# Play MUD

Play text-based MUD games (tBAMUD/CircleMUD) using `nc` (netcat) as a TCP transport with persistent memory files.

## Overview

This skill manages a MUD session through `mud_client.py`. **Interactive mode with tmux is the only way to play the MUD** — it maintains a single persistent connection with real-time output streaming via `select()`.

Memory is persisted to `data/player.md` and `data/world.md` (relative to working directory) so you can track player state and world changes across sessions for longer-term goal tracking.

## When to Use

- User asks you to play a MUD game or execute commands in a MUD
- tBAMUD or CircleMUD server running on localhost:4000
- Given specific in-game commands to run (look, move, use item, fight, etc.)
- User wants to track character progress or world state over time

## Setup

The MUD client script is at `mud_client.py` in this directory. Auto-detects nc variant (OpenBSD, ncat, traditional). Default: `localhost:4000`, user: `dummy`, password: `helloworld`.

## Usage — Interactive Mode (ALWAYS USE)

**Interactive mode with tmux is the default and required mode for all gameplay.** Every agent session that plays a MUD MUST start an interactive tmux session.

### Start a session

Run the client with no arguments. When run without a TTY (from an agent), it **automatically spawns a tmux session** named `play-mud` and exits with instructions.

```bash
# Start interactive session (auto-tmux when no TTY)
python3 mud_client.py
# With custom server:
python3 mud_client.py --host localhost --port 4000 --user dummy --pass helloworld
```

### Monitor the session (auto-tmux mode)

After starting, use these tmux commands to interact with the session:

```bash
# Capture the current pane content (this is how you read MUD output)
tmux capture-pane -t play-mud -p

# Reattach to the tmux session directly
tmux attach -t play-mud

# Send input to the tmux session (type a MUD command into it)
tmux send-keys -t play-mud "look" Enter
tmux send-keys -t play-mud "!scan" Enter

# Kill the session when done
tmux kill-session -t play-mud
```

### Interactive shortcuts (prefix with `!`)

Once the interactive session is running, use these shortcuts to manage state without leaving the game loop:

| Shortcut | Action |
|----------|--------|
| `!scan` / `!save_player` | Run `scan`, save player state to `data/player.md` |
| `!look` / `!save_world` | Run `look`, save world state to `data/world.md` |
| `!status` | Show connection and memory status |
| `!mem` | Read both memory files |
| `!mem player` | Read player memory only |
| `!mem world` | Read world memory only |
| `!q` / `!quit` | Disconnect from MUD only (keeps tmux running) |
| `!cleanup` | Disconnect from MUD **and** kill tmux session |
| `!help` | Show shortcut help |

Anything else (no `!` prefix) is sent directly to the MUD as a game command.

### Sending commands from an agent session

Since the agent runs without a TTY and the MUD session lives in tmux, send commands into the tmux pane using `tmux send-keys`:

```bash
# Type "look" and press Enter into the MUD session
tmux send-keys -t play-mud "look" Enter

# Type "!scan" and press Enter into the MUD session
tmux send-keys -t play-mud "!scan" Enter

# Read the MUD output
tmux capture-pane -t play-mud -p
```

## Quick Reference

| Action | Command |
|--------|---------|
| **Start interactive session (default)** | `python3 mud_client.py` |
| **Interactive mode explicit** | `python3 mud_client.py interactive` |
| **Interactive in tmux** | `python3 mud_client.py` (auto-tmux when no TTY) |
| **Send command into MUD** | `tmux send-keys -t play-mud "<cmd>" Enter` |
| **Read MUD output** | `tmux capture-pane -t play-mud -p` |
| **Save player state** | `tmux send-keys -t play-mud "!scan" Enter` |
| **Save world state** | `tmux send-keys -t play-mud "!look" Enter` |
| **Read memory** | `tmux send-keys -t play-mud "!mem" Enter` |
| **Kill session** | `tmux kill-session -t play-mud` |


### End of Session (MANDATORY)

**When you are done playing the MUD (goals achieved, task complete, or user says stop), you MUST clean up.**

Do NOT leave the tmux session running. Orphaned sessions consume resources and confuse future instances.

**Steps — in exact order:**
```
1. Send !cleanup to the tmux session
   tmux send-keys -t play-mud "!cleanup" Enter
2. Verify: tmux list-sessions should NOT show "play-mud"
   tmux list-sessions 2>/dev/null | grep play-mud
3. Report: "Session cleaned up. MUD session closed."
```

**If you used `!q` instead of `!cleanup`**, you only disconnected from the MUD. You MUST still clean up:
```
tmux kill-session -t play-mud
```

## Memory Workflow

### How memory works

The `data/` directory is created automatically where the command is run from.

**data/player.md** — Tracks character state:
- HP/Mana/Vitality from prompt (`25H 100M 84V >`)
- Inventory from `i` or `inv`
- Status effects (hungry, thirsty, poisoned, etc.)
- Stats from `score`, `skills`, `abilities`

**data/world.md** — Tracks the environment:
- Room name and description from `look`
- Exits and their directions
- NPCs, items, and people in the room
- Recent world events (monster arrivals, changes)

### Pattern for longer-term goals (interactive mode)

```
1. Send !look or !scan to the tmux session
2. Read memory with !mem to recall context
3. Compare previous memory with current output to detect changes
4. Track progression: inventory changes, room exploration, NPC interactions
```

## How It Works

1. `mud_client.py` spawns `nc` (netcat) as a subprocess for TCP transport
2. Python manages nc's stdin/stdout via pipes with `select()` for multiplexing
3. Login flow: username → name confirmation → password
4. **Interactive mode**: persistent session — MUD output streams to terminal, readline handles input, `!` shortcuts invoke client operations. When no TTY is available, the client auto-spawns a tmux session named `play-mud`.
5. `!scan`/`!look` shortcuts write output to `data/player.md` or `data/world.md`

## Common Mistakes

- **Connection refused**: If the MUD server isn't running, verify connectivity is possible first.
- **Memory files in wrong place**: `data/` is relative to working directory, not the skill directory. Run commands from the directory where you want memory files stored.
- **Using wrong stat commands**: tBAMUD commands vary. Try `scan`, `i`, `look` as reliable defaults. The prompt line (`25H 100M 84V >`) always contains HP/Mana/Vitality.
- **Shortcut collision**: `!`-prefixed input triggers client shortcuts. If a MUD command starts with `!`, use a different approach.
- **Leaving tmux session after finishing**: Typing `!q` only disconnects from the MUD — the tmux session `play-mud` stays running. **ALWAYS use `!cleanup` instead, or manually run `tmux kill-session -t play-mud`.** This is the most common and most damaging mistake.

## Example Workflow (Interactive with tmux)

```
Partner: "Check my stats and look around"
You:     tmux send-keys -t play-mud "score" Enter
         tmux send-keys -t play-mud "i" Enter
         tmux send-keys -t play-mud "!scan" Enter
         tmux send-keys -t play-mud "look" Enter
         tmux send-keys -t play-mud "!look" Enter
         tmux capture-pane -t play-mud -p

Partner: "Go south"
You:     tmux send-keys -t play-mud "south" Enter
         tmux send-keys -t play-mud "look" Enter
         tmux send-keys -t play-mud "!look" Enter

Partner: "What's different from before?"
You:     tmux send-keys -t play-mud "!mem world" Enter
         tmux capture-pane -t play-mud -p
         Compare saved room state with current output
```

## Environment Flags

Start the session with:
- `--host` - MUD server hostname (default: localhost)
- `--port` - MUD server port (default: 4000)
- `--user` - Username (default: dummy)
- `--pass` - Password (default: helloworld)
