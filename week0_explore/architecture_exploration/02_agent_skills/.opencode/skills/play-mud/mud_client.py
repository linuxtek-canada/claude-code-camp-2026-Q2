#!/usr/bin/env python3
"""
MUD Client for tBAMUD/CircleMUD instances.

Manages an nc (netcat) subprocess for TCP transport to a MUD server.
Handles login, command sending, and memory file persistence.

Usage:
    python3 mud_client.py [options]        # Interactive mode (auto-tmux when no TTY)
    python3 mud_client.py interactive [options]  # Interactive mode explicit
"""

import argparse
import os
import re
import select
import subprocess
import sys
import time

try:
    import readline
except ImportError:
    readline = None

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4000
DEFAULT_USER = "dummy"
DEFAULT_PASS = "helloworld"
READ_TIMEOUT = 15
NC_TIMEOUT = 300

# MUD prompt patterns to strip/recognize
MUD_PROMPT_PATTERNS = [
    re.compile(r'^\d+[Hh]\s+\d+[Mm]\s+\d+[Vv]\s+>'),  # 25H 100M 84V >
    re.compile(r'^>'),                                   # simple >
]


def _is_mud_prompt(line):
    """Check if a line looks like a MUD prompt."""
    stripped = line.strip()
    for pat in MUD_PROMPT_PATTERNS:
        if pat.match(stripped):
            return True
    return False


def detect_nc():
    """Detect which netcat implementation is available and return the variant name."""
    for nc_path in ["nc", "ncat", "nmap-ncat"]:
        if subprocess.run(["which", nc_path], capture_output=True).returncode == 0:
            result = subprocess.run([nc_path, "-h"], capture_output=True, text=True, timeout=5)
            output = result.stderr + result.stdout
            if "OpenBSD" in output:
                return "openbsd"
            elif "Ncat" in output or "nmap" in nc_path:
                return "ncat"
            elif "traditional" in output.lower() or "sysutils" in output.lower():
                return "traditional"
            else:
                return "unknown"
    return None


def build_nc_command(nc_variant, host, port):
    """Build the nc command list based on detected variant."""
    if nc_variant == "openbsd":
        return ["nc", "-w", str(NC_TIMEOUT), "-4", host, str(port)]
    elif nc_variant == "ncat":
        return ["ncat", "--connect-timeout", str(NC_TIMEOUT), host, str(port)]
    elif nc_variant == "traditional":
        return ["nc", "-w", str(NC_TIMEOUT), host, str(port)]
    else:
        return ["nc", host, str(port)]


class MUDSession:
    """Manages a nc-based MUD session with memory persistence."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 user=DEFAULT_USER, password=DEFAULT_PASS,
                 nc_path=None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.process = None
        self.nc_variant = None
        self.connected = False
        self.logged_in = False
        self.buffer = ""
        self.memory_dir = os.path.join(os.getcwd(), "data")
        self.player_file = os.path.join(self.memory_dir, "player.md")
        self.world_file = os.path.join(self.memory_dir, "world.md")
        self._read_thread = None

    def start(self):
        """Start the nc subprocess."""
        if self.nc_variant is None:
            self.nc_variant = detect_nc()
            if self.nc_variant is None:
                print("Error: no netcat (nc) implementation found.", file=sys.stderr)
                return False
            print(f"[nc variant: {self.nc_variant}]", file=sys.stderr)

        cmd = build_nc_command(self.nc_variant, self.host, self.port)
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self.connected = True
            time.sleep(0.3)
            return True
        except FileNotFoundError as e:
            print(f"nc not found: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Failed to start nc: {e}", file=sys.stderr)
            return False

    def stop(self):
        """Terminate the nc subprocess."""
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception:
                pass
            self.process = None
        self.connected = False
        self.logged_in = False

    def _read_all(self, timeout=READ_TIMEOUT):
        """Read all available output from nc, with polling for more data."""
        if not self.process or not self.process.stdout:
            return ""
        start = time.time()
        output = []
        idle = 0
        while time.time() - start < timeout:
            ready, _, _ = select.select([self.process.stdout], [], [], 0.3)
            if ready:
                try:
                    chunk = os.read(self.process.stdout.fileno(), 4096)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        output.append(text)
                        self.buffer += text
                        idle = 0
                    else:
                        self.connected = False
                        self.logged_in = False
                        break
                except OSError:
                    self.connected = False
                    self.logged_in = False
                    break
            else:
                idle += 1
                if idle > 3:
                    break
        return "".join(output)

    def strip_mud_sequences(self, data):
        """Remove ANSI escape codes and MUD control sequences from text."""
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\([a-zA-Z]|\x1b\(B')
        data = ansi_pattern.sub('', data)
        clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', data)
        return clean

    def send(self, data):
        """Write data to nc's stdin."""
        if not self.process or not self.process.stdin:
            print("No active nc connection.", file=sys.stderr)
            return False
        if not data.endswith("\n"):
            data += "\n"
        try:
            self.process.stdin.write(data.encode("utf-8"))
            self.process.stdin.flush()
            return True
        except BrokenPipeError:
            self.connected = False
            self.logged_in = False
            return False

    def connect(self):
        """Start nc connection and drain initial banner."""
        print(f"Connecting to {self.host}:{self.port}...", file=sys.stderr)
        if not self.start():
            return False
        time.sleep(1)
        initial = self._read_all(timeout=3)
        banner = self.strip_mud_sequences(initial).strip()
        if banner:
            print(f"[Banner: {banner[:100]}...]", file=sys.stderr)
        return True

    def login(self):
        """Login to tBAMUD/CircleMUD.

        Flow:
        1. Send username
        2. Wait for "By what name do you wish to be known?"
        3. Confirm username
        4. Wait for "Password: "
        5. Send password
        6. Wait for login result
        """
        if not self.connected:
            if not self.connect():
                return False

        # Step 1: Send username
        print(f"[Sending username: {self.user}]", file=sys.stderr)
        self.send(self.user)
        time.sleep(2)
        name_response = self._read_all(timeout=5)
        name_clean = self.strip_mud_sequences(name_response).lower()
        if "name" in name_clean or "known" in name_clean:
            print(f"[Name confirmation prompt received]", file=sys.stderr)
        else:
            print(f"[Server: {self.strip_mud_sequences(name_response).strip()[:150]}]", file=sys.stderr)

        # Step 2: Confirm name
        print(f"[Confirming name: {self.user}]", file=sys.stderr)
        self.send(self.user)
        time.sleep(1)
        pass_response = self._read_all(timeout=3)
        pass_clean = self.strip_mud_sequences(pass_response).lower()
        if "password" in pass_clean:
            print(f"[Password prompt received]", file=sys.stderr)
        else:
            print(f"[Server: {self.strip_mud_sequences(pass_response).strip()[:150]}]", file=sys.stderr)

        # Step 3: Send password
        print(f"[Sending password...]", file=sys.stderr)
        self.send(self.password)
        time.sleep(2)
        result = self._read_all(timeout=5)
        result_clean = self.strip_mud_sequences(result).strip()

        if result_clean:
            print(result_clean)

        # Detect login success
        success_markers = ["room", "you are", "your", "health", "hp:", "hp ",
                           "level", "class", "race", "skills", "stats",
                           "you see", "exit", "north", "south", "east",
                           "west", "up", "down", ">", "!", "command?"]
        fail_markers = ["error", "wrong", "invalid", "bad", "denied", "forbidden"]

        if any(m in result_clean.lower() for m in success_markers):
            self.logged_in = True
            print("[Login successful]", file=sys.stderr)
            return True
        elif any(m in result_clean.lower() for m in fail_markers):
            print("[Login failed]", file=sys.stderr)
            return False
        else:
            print("[Login result unclear]", file=sys.stderr)
            return False

    def send_command(self, command):
        """Send a game command and return output."""
        if not self.connected:
            if not self.connect():
                return None
            if not self.logged_in:
                if not self.login():
                    return None

        print(f"\n>>> {command}", file=sys.stderr)
        self.send(command)
        time.sleep(0.5)
        output = self._read_all(timeout=READ_TIMEOUT)
        output = self.strip_mud_sequences(output).strip()
        if output:
            print(output)
        return output

    def drain_output(self, timeout=1.0):
        """Non-blocking read of any pending MUD output. Prints directly to stdout.
        Returns any text read (which may be empty if nothing pending)."""
        if not self.process or not self.process.stdout:
            return ""
        output = []
        idle = 0
        start = time.time()
        while time.time() - start < timeout:
            ready, _, _ = select.select([self.process.stdout], [], [], 0.3)
            if ready:
                try:
                    chunk = os.read(self.process.stdout.fileno(), 4096)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        output.append(text)
                        self.buffer += text
                        idle = 0
                    else:
                        self.connected = False
                        self.logged_in = False
                        return "".join(output)
                except OSError:
                    self.connected = False
                    self.logged_in = False
                    return "".join(output)
            else:
                idle += 1
                if idle > 3:
                    break
        return "".join(output)

    # ── Memory management ──────────────────────────────────────────

    def ensure_memory_dir(self):
        """Create data/ directory if it doesn't exist."""
        if not os.path.isdir(self.memory_dir):
            os.makedirs(self.memory_dir)

    def read_player(self):
        """Read current player memory file."""
        self.ensure_memory_dir()
        if os.path.isfile(self.player_file):
            with open(self.player_file, "r") as f:
                return f.read()
        return ""

    def write_player(self, content):
        """Write player state to data/player.md."""
        self.ensure_memory_dir()
        with open(self.player_file, "w") as f:
            f.write(content)

    def read_world(self):
        """Read current world memory file."""
        self.ensure_memory_dir()
        if os.path.isfile(self.world_file):
            with open(self.world_file, "r") as f:
                return f.read()
        return ""

    def write_world(self, content):
        """Write world state to data/world.md."""
        self.ensure_memory_dir()
        with open(self.world_file, "w") as f:
            f.write(content)

    def save_player_from_mud(self, command="scan", output=None):
        """Run a command (default: scan) and save the output as player state."""
        if output is None:
            output = self.send_command(command)
        if not output:
            print("[No output to save]", file=sys.stderr)
            return
        header = (
            f"# Player State\n"
            f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"```\n"
            f"{output}\n"
            f"```\n"
        )
        self.write_player(header)
        print("[Saved player state]", file=sys.stderr)

    def save_world_from_mud(self, command="look", output=None):
        """Run a command (default: look) and save the output as world state."""
        if output is None:
            output = self.send_command(command)
        if not output:
            print("[No output to save]", file=sys.stderr)
            return
        header = (
            f"# World State\n"
            f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"```\n"
            f"{output}\n"
            f"```\n"
        )
        self.write_world(header)
        print("[Saved world state]", file=sys.stderr)

    def status(self):
        """Return current connection/memory status."""
        return {
            "connected": self.connected,
            "logged_in": self.logged_in,
            "nc_variant": self.nc_variant,
            "player_memory": os.path.isfile(self.player_file),
            "world_memory": os.path.isfile(self.world_file),
        }


# ── Interactive mode ──────────────────────────────────────────────

SHORTCUTS = {
    "scan": ("!scan", "Run scan and save to player.md"),
    "save_player": ("!scan", "Run scan and save to player.md"),
    "look": ("!look", "Run look and save to world.md"),
    "save_world": ("!look", "Run look and save to world.md"),
    "status": ("!status", "Show connection and memory status"),
    "mem": ("!mem", "Read memory files"),
    "read_memory": ("!mem", "Read memory files"),
    "q": ("!q", "Quit and disconnect"),
    "quit": ("!q", "Quit and disconnect"),
    "help": ("!help", "Show this help"),
    "cleanup": ("!cleanup", "Quit MUD and kill tmux session"),
}


INTERACTIVE_HELP = """
Shortcuts:
  !scan   / !save_player  - Run 'scan' and save player state to data/player.md
  !look   / !save_world   - Run 'look' and save world state to data/world.md
  !status                 - Show connection and memory status
  !mem                    - Read memory files
  !mem player/world       - Read specific memory file
  !q / !quit              - Quit MUD only (keeps tmux session running)
  !cleanup                - Quit MUD and kill tmux session (recommended end-of-session)
  !help                   - Show this help

Any other input (without !) is sent directly to the MUD as a game command.
"""


def _handle_shortcut(session, args_str):
    """Handle an !-prefixed shortcut. Returns True if handled, False if should quit."""
    parts = args_str.strip().split(None, 1)
    cmd = parts[0].lower() if parts else ""

    if cmd in ("!scan", "!save_player"):
        if not session.connected or not session.logged_in:
            if not session.connect():
                return True
            if not session.login():
                return True
        session.save_player_from_mud()
        return True

    if cmd in ("!look", "!save_world"):
        if not session.connected or not session.logged_in:
            if not session.connect():
                return True
            if not session.login():
                return True
        session.save_world_from_mud()
        return True

    if cmd == "!status":
        st = session.status()
        print(f"  Connected:   {st['connected']}")
        print(f"  Logged in:   {st['logged_in']}")
        print(f"  nc variant:  {st['nc_variant']}")
        print(f"  Player mem:  {'yes' if st['player_memory'] else 'no'}")
        print(f"  World mem:   {'yes' if st['world_memory'] else 'no'}")
        return True

    if cmd in ("!mem", "!read_memory"):
        if len(parts) < 2 or parts[1].lower() in ("both", "all", ""):
            f = "both"
        else:
            f = parts[1].lower()
        if f in ("player", "both"):
            p = session.read_player()
            if p:
                print("--- PLAYER MEMORY ---")
                print(p)
            else:
                print("[No player memory file found]")
        if f in ("world", "both"):
            w = session.read_world()
            if w:
                print("--- WORLD MEMORY ---")
                print(w)
            else:
                print("[No world memory file found]")
        return True

    if cmd in ("!cleanup",):
        print("[Cleaning up: disconnecting MUD and killing tmux session]", file=sys.stderr)
        try:
            os.system("tmux kill-session -t play-mud 2>/dev/null")
        except OSError:
            pass
        print("[Disconnecting...]", file=sys.stderr)
        return False

    if cmd in ("!q", "!quit"):
        print("[Disconnecting...]", file=sys.stderr)
        return False

    if cmd == "!help":
        print(INTERACTIVE_HELP)
        return True

    # Unknown shortcut, warn but continue
    print(f"  Unknown shortcut: {args_str}. Type '!help' for available commands.", file=sys.stderr)
    return True


def interactive_loop(session, host, port, user, password):
    """Run the interactive readline loop with persistent MUD connection.

    MUD output streams directly to stdout in real-time.
    User types commands at the readline prompt; input without ! goes to MUD.
    """
    session.host = host
    session.port = port
    session.user = user
    session.password = password

    print("=" * 60)
    print("  MUD Interactive Mode — persistent nc session")
    print("  Type MUD commands directly. Use ! for client shortcuts.")
    print("  Type !help for shortcuts. Type !q to quit.")
    print("=" * 60)

    # Connect and login
    if not session.connect():
        print("[Failed to connect to MUD]", file=sys.stderr)
        sys.exit(1)
    if not session.login():
        print("[Login failed]", file=sys.stderr)
        sys.exit(1)

    # Drain any initial output after login
    session.drain_output(timeout=1.0)

    print("", file=sys.stderr)  # blank line before prompt

    # Readline setup
    prompt = "mud> "

    try:
        while True:
            # Check if nc subprocess died and reconnect
            if session.process:
                session.process.poll()
                if session.process.returncode is not None:
                    print("[nc process exited. Reconnecting...]", file=sys.stderr)
                    time.sleep(0.5)
                    if not session.connect():
                        continue
                    if not session.login():
                        continue
                    session.drain_output(timeout=1.0)
                    continue

            # Check if connection lost (MUD server closed)
            if not session.connected:
                print("[Connection lost. Reconnecting...]", file=sys.stderr)
                time.sleep(0.5)
                if not session.connect():
                    continue
                if not session.login():
                    continue
                session.drain_output(timeout=1.0)
                continue

            # Non-blocking select: wait for stdin OR MUD output
            inputs = []
            if session.process and session.process.stdout:
                inputs.append(session.process.stdout)
            inputs.append(sys.stdin)

            try:
                ready, _, _ = select.select(inputs, [], [], 0.5)
            except (ValueError, OSError):
                # stdin may be closed or broken during shutdown
                break

            if ready:
                # Drain any MUD output first (it's the priority)
                for fd in ready:
                    if fd is sys.stdin:
                        continue
                    try:
                        chunk = os.read(fd.fileno(), 4096)
                        if chunk:
                            text = chunk.decode("utf-8", errors="replace")
                            # Print MUD output to stdout (raw, including ANSI)
                            sys.stdout.write(text)
                            sys.stdout.flush()
                    except OSError:
                        session.connected = False
                        session.logged_in = False

            # Now read user input (non-blocking)
            try:
                ready_in, _, _ = select.select([sys.stdin], [], [], 0)
            except (ValueError, OSError):
                break

            if ready_in:
                line = sys.stdin.readline()
                if not line:
                    # stdin closed — exit gracefully
                    break

                line = line.rstrip('\n')
                if not line:
                    continue

                # Check for shortcut
                if line.startswith("!"):
                    if not _handle_shortcut(session, line):
                        break  # user typed !q
                else:
                    # Send to MUD
                    try:
                        if not session.send(line):
                            print("[Connection lost]", file=sys.stderr)
                            break
                    except (BrokenPipeError, OSError):
                        session.connected = False
                        print("[Connection lost]", file=sys.stderr)
                        break

    except (KeyboardInterrupt, EOFError):
        print("", file=sys.stderr)
    finally:
        print("[Disconnecting...]", file=sys.stderr)
        session.stop()


def _is_tty():
    """Check if stdin is connected to a terminal."""
    return sys.stdin.isatty()


def _ensure_tmux_session(host, port, user, password):
    """Start an interactive MUD session in a detached tmux session if not in a TTY.
    Returns True if we spawned a tmux session (caller should exit), False if caller
    should run interactively."""
    if _is_tty():
        return False

    if not subprocess.run(["which", "tmux"], capture_output=True).returncode == 0:
        print("[Warning: tmux not available, running in foreground]", file=sys.stderr)
        return False

    session_name = "play-mud"
    check = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    if check.returncode == 0:
        print(f"[tmux session '{session_name}' already exists]", file=sys.stderr)
        print(f"Reattach with: tmux attach -t {session_name}", file=sys.stderr)
        sys.exit(0)

    print(f"[Starting interactive MUD in tmux session '{session_name}']", file=sys.stderr)
    cmd_parts = [
        sys.executable, __file__, "interactive",
        "--host", host,
        "--port", str(port),
        "--user", user,
        "--pass", password,
    ]
    subprocess.Popen(
        ["tmux", "new-session", "-d", "-s", session_name, "-x", "200", "-y", "50"] + cmd_parts,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    print(f"[Session '{session_name}' started]", file=sys.stderr)
    print(f"Attach with: tmux attach -t {session_name}", file=sys.stderr)
    print(f"Monitor output: tmux capture-pane -t {session_name} -p", file=sys.stderr)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="MUD Client using nc (netcat) — interactive mode only",
        prog="mud_client.py",
    )

    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"MUD server hostname (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"MUD server port (default: {DEFAULT_PORT})")
    parser.add_argument("--user", default=DEFAULT_USER,
                        help=f"Username (default: {DEFAULT_USER})")
    parser.add_argument("--pass", dest="password", default=DEFAULT_PASS,
                        help=f"Password (default: {DEFAULT_PASS})")

    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # Interactive mode
    interactive_parser = subparsers.add_parser("interactive", help="Start interactive persistent session")
    interactive_parser.add_argument("--user", default=DEFAULT_USER)
    interactive_parser.add_argument("--pass", dest="password", default=DEFAULT_PASS)
    interactive_parser.add_argument("--host", default=DEFAULT_HOST)
    interactive_parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args()

    # ── Default: interactive mode ─────────────────────────────────
    if not args.action:
        _ensure_tmux_session(args.host, args.port, args.user, args.password)
        session = MUDSession(
            host=args.host, port=args.port,
            user=args.user, password=args.password,
        )
        interactive_loop(session,
                         host=args.host, port=args.port,
                         user=args.user, password=args.password)
        return

    # ── Interactive mode ──────────────────────────────────────────
    if args.action == "interactive":
        session = MUDSession(
            host=args.host, port=args.port,
            user=args.user, password=args.password,
        )
        interactive_loop(session,
                         host=args.host, port=args.port,
                         user=args.user, password=args.password)
        return


if __name__ == "__main__":
    main()
