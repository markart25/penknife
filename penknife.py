#!/usr/bin/env python3
"""
penknife - a tiny TUI launcher for your pentest toolkit.

Run it, arrow-key to a tool, pick a preset, tweak the command, launch.
Tools and presets live in ~/.config/penknife/tools.json - edit to taste.
Zero dependencies, stdlib curses only.
"""

import curses
import json
import locale
import os
import re
import shutil
import subprocess
import sys

__version__ = "0.1.0"

CONFIG_DIR = os.path.expanduser("~/.config/penknife")
CONFIG_FILE = os.path.join(CONFIG_DIR, "tools.json")

# ─── Banner (ANSI Shadow, matching bosif) ──────────────────────────────────
BANNER = r"""
██████╗ ███████╗███╗   ██╗██╗  ██╗███╗   ██╗██╗███████╗███████╗
██╔══██╗██╔════╝████╗  ██║██║ ██╔╝████╗  ██║██║██╔════╝██╔════╝
██████╔╝█████╗  ██╔██╗ ██║█████╔╝ ██╔██╗ ██║██║█████╗  █████╗
██╔═══╝ ██╔══╝  ██║╚██╗██║██╔═██╗ ██║╚██╗██║██║██╔══╝  ██╔══╝
██║     ███████╗██║ ╚████║██║  ██╗██║ ╚████║██║██║     ███████╗
╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝
"""
_RAW_BANNER_LINES = BANNER.strip("\n").splitlines()
_BANNER_W = max(len(ln) for ln in _RAW_BANNER_LINES)
# pad every line to the same width so they all share ONE left margin
BANNER_LINES = [ln.ljust(_BANNER_W) for ln in _RAW_BANNER_LINES]

HELP = f"""penknife {__version__} - a tiny TUI launcher for your pentest toolkit made by markart25 on github

usage: penknife [options]

  (no args)     launch the interactive menu
  -h, --help    show this help
  -v, --version show version
  --config      print the config file path
  --reset       overwrite the config file with the built-in defaults

config: {CONFIG_FILE}
  edit this json to add, remove, or re-order tools and presets.

keys:
  ↑/↓ or j/k    move
  enter or l    select
  esc or h      back
  q             quit
"""

# ─── Default toolkit ───────────────────────────────────────────────────────
# "check" is the binary to look for if it differs from the display name.
# placeholders like {target} are just hints - you edit them before launch.
DEFAULT_TOOLS = [
    # ── recon ──
    {"name": "nmap", "category": "recon", "description": "network/port scanner", "presets": [
        {"name": "Quick scan", "command": "nmap -T4 -F {target}"},
        {"name": "Full TCP scan", "command": "nmap -T4 -A -p- {target}"},
        {"name": "Stealth SYN scan", "command": "sudo nmap -sS -T4 {target}"},
        {"name": "Service/version", "command": "nmap -sV {target}"},
        {"name": "UDP top ports", "command": "sudo nmap -sU --top-ports 50 {target}"},
        {"name": "Vuln scripts", "command": "nmap --script vuln {target}"},
        {"name": "Custom", "command": "nmap "},
    ]},
    {"name": "masscan", "category": "recon", "description": "mass IP/port scanner", "presets": [
        {"name": "All ports", "command": "sudo masscan {target} -p1-65535 --rate=1000"},
        {"name": "Custom", "command": "sudo masscan "},
    ]},
    {"name": "rustscan", "category": "recon", "description": "fast port scanner", "presets": [
        {"name": "Quick", "command": "rustscan -a {target}"},
        {"name": "Pipe to nmap", "command": "rustscan -a {target} -- -A -sV"},
        {"name": "Custom", "command": "rustscan "},
    ]},
    # ── web ──
    {"name": "gobuster", "category": "web", "description": "dir/dns/vhost brute", "presets": [
        {"name": "Directory", "command": "gobuster dir -u {target} -w {wordlist}"},
        {"name": "DNS subdomains", "command": "gobuster dns -d {domain} -w {wordlist}"},
        {"name": "VHost", "command": "gobuster vhost -u {target} -w {wordlist}"},
        {"name": "Custom", "command": "gobuster "},
    ]},
    {"name": "ffuf", "category": "web", "description": "web fuzzer", "presets": [
        {"name": "Directory fuzz", "command": "ffuf -u {target}/FUZZ -w {wordlist}"},
        {"name": "VHost fuzz", "command": "ffuf -u {target} -H \"Host: FUZZ.{domain}\" -w {wordlist}"},
        {"name": "Param fuzz", "command": "ffuf -u {target}?FUZZ=1 -w {wordlist}"},
        {"name": "Custom", "command": "ffuf "},
    ]},
    {"name": "feroxbuster", "category": "web", "description": "recursive content scanner", "presets": [
        {"name": "Recursive dir", "command": "feroxbuster -u {target} -w {wordlist}"},
        {"name": "Custom", "command": "feroxbuster "},
    ]},
    {"name": "nikto", "category": "web", "description": "web server scanner", "presets": [
        {"name": "Scan", "command": "nikto -h {target}"},
        {"name": "Custom", "command": "nikto "},
    ]},
    {"name": "whatweb", "category": "web", "description": "web fingerprinter", "presets": [
        {"name": "Fingerprint", "command": "whatweb {target}"},
        {"name": "Aggressive", "command": "whatweb -a 3 {target}"},
        {"name": "Custom", "command": "whatweb "},
    ]},
    {"name": "sqlmap", "category": "web", "description": "sql injection tool", "presets": [
        {"name": "Test URL", "command": "sqlmap -u \"{target}\" --batch"},
        {"name": "Enumerate DBs", "command": "sqlmap -u \"{target}\" --batch --dbs"},
        {"name": "Custom", "command": "sqlmap "},
    ]},
    {"name": "wpscan", "category": "web", "description": "wordpress scanner", "presets": [
        {"name": "Enumerate", "command": "wpscan --url {target} --enumerate u,vp"},
        {"name": "Custom", "command": "wpscan "},
    ]},
    # ── password ──
    {"name": "hydra", "category": "password", "description": "login brute-forcer", "presets": [
        {"name": "SSH", "command": "hydra -l {user} -P {passlist} ssh://{target}"},
        {"name": "FTP", "command": "hydra -l {user} -P {passlist} ftp://{target}"},
        {"name": "HTTP POST form", "command": "hydra -l {user} -P {passlist} {target} http-post-form \"{path}:{params}:{failstr}\""},
        {"name": "Custom", "command": "hydra "},
    ]},
    {"name": "john", "category": "password", "description": "john the ripper", "presets": [
        {"name": "Wordlist crack", "command": "john --wordlist={wordlist} {hashfile}"},
        {"name": "Show cracked", "command": "john --show {hashfile}"},
        {"name": "Custom", "command": "john "},
    ]},
    {"name": "hashcat", "category": "password", "description": "gpu hash cracker", "presets": [
        {"name": "Wordlist", "command": "hashcat -m {mode} {hashfile} {wordlist}"},
        {"name": "Custom", "command": "hashcat "},
    ]},
    # ── exploitation ──
    {"name": "metasploit", "category": "exploit", "description": "exploitation framework", "check": "msfconsole", "presets": [
        {"name": "Console", "command": "msfconsole"},
        {"name": "Quiet console", "command": "msfconsole -q"},
        {"name": "Custom", "command": "msfconsole "},
    ]},
    {"name": "searchsploit", "category": "exploit", "description": "exploit-db search", "presets": [
        {"name": "Search", "command": "searchsploit {query}"},
        {"name": "Custom", "command": "searchsploit "},
    ]},
    # ── network ──
    {"name": "netcat", "category": "network", "description": "tcp/ip swiss army knife", "check": "nc", "presets": [
        {"name": "Listen", "command": "nc -lvnp {port}"},
        {"name": "Connect", "command": "nc {target} {port}"},
        {"name": "Custom", "command": "nc "},
    ]},
    {"name": "socat", "category": "network", "description": "multipurpose relay", "presets": [
        {"name": "Listen", "command": "socat -d -d TCP-LISTEN:{port},reuseaddr -"},
        {"name": "Custom", "command": "socat "},
    ]},
    {"name": "tcpdump", "category": "network", "description": "packet capture", "presets": [
        {"name": "Capture iface", "command": "sudo tcpdump -i {interface}"},
        {"name": "Custom", "command": "sudo tcpdump "},
    ]},
    # ── smb / ad ──
    {"name": "responder", "category": "smb/ad", "description": "llmnr/nbns poisoner", "presets": [
        {"name": "Analyze", "command": "sudo responder -I {interface} -A"},
        {"name": "Poison", "command": "sudo responder -I {interface} -wF"},
        {"name": "Custom", "command": "sudo responder "},
    ]},
    {"name": "netexec", "category": "smb/ad", "description": "network exec (ex-cme)", "presets": [
        {"name": "SMB enum", "command": "netexec smb {target}"},
        {"name": "SMB shares", "command": "netexec smb {target} -u {user} -p {password} --shares"},
        {"name": "Custom", "command": "netexec "},
    ]},
    {"name": "enum4linux", "category": "smb/ad", "description": "smb/samba enumeration", "presets": [
        {"name": "Full", "command": "enum4linux -a {target}"},
        {"name": "Custom", "command": "enum4linux "},
    ]},
    {"name": "smbclient", "category": "smb/ad", "description": "smb share client", "presets": [
        {"name": "List shares", "command": "smbclient -L //{target} -N"},
        {"name": "Custom", "command": "smbclient "},
    ]},
    # ── dns ──
    {"name": "dnsrecon", "category": "dns", "description": "dns enumeration", "presets": [
        {"name": "Standard", "command": "dnsrecon -d {domain}"},
        {"name": "Custom", "command": "dnsrecon "},
    ]},
    {"name": "fierce", "category": "dns", "description": "dns recon", "presets": [
        {"name": "Scan", "command": "fierce --domain {domain}"},
        {"name": "Custom", "command": "fierce "},
    ]},
    # ── wireless ──
    {"name": "aircrack-ng", "category": "wireless", "description": "wifi cracking suite", "presets": [
        {"name": "Crack", "command": "aircrack-ng {capfile} -w {wordlist}"},
        {"name": "Custom", "command": "aircrack-ng "},
    ]},
    # ── misc ──
    {"name": "curl", "category": "misc", "description": "http client", "presets": [
        {"name": "Headers", "command": "curl -I {target}"},
        {"name": "Verbose", "command": "curl -v {target}"},
        {"name": "Custom", "command": "curl "},
    ]},
]

# ─── colours ────────────────────────────────────────────────────────────────
C_AMBER = 1
C_RED = 2


def setup_colors():
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()  # inherit terminal bg (respects your theme)
        curses.init_pair(C_AMBER, curses.COLOR_YELLOW, -1)
        curses.init_pair(C_RED, curses.COLOR_RED, -1)
    except curses.error:
        pass


def amber():
    return curses.color_pair(C_AMBER) if curses.has_colors() else curses.A_BOLD


def red():
    return curses.color_pair(C_RED) if curses.has_colors() else curses.A_BOLD


# ─── drawing helpers ─────────────────────────────────────────────────────────
def safe_addstr(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    text = text[: max(0, w - 1 - x)]
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_line(win, y, width, segments, selected):
    """Draw a list row from (text, attr) segments. Selected = full-width bar."""
    if selected:
        try:
            win.addstr(y, 0, " " * (width - 1), curses.A_REVERSE)
        except curses.error:
            pass
        x = 0
        for text, _attr in segments:
            if x >= width - 1:
                break
            t = text[: max(0, width - 1 - x)]
            try:
                win.addstr(y, x, t, curses.A_REVERSE)
            except curses.error:
                pass
            x += len(t)
    else:
        x = 0
        for text, attr in segments:
            if x >= width - 1:
                break
            t = text[: max(0, width - 1 - x)]
            try:
                win.addstr(y, x, t, attr)
            except curses.error:
                pass
            x += len(t)


def draw_banner(win, width):
    """Big banner if it fits (wide AND tall enough), else a compact title.
    Returns the row the hint line should go on."""
    h, _ = win.getmaxyx()
    bw = max(len(ln) for ln in BANNER_LINES)
    big = width >= bw + 2 and h >= len(BANNER_LINES) + 8
    if big:
        left = max(0, (width - bw) // 2)  # ONE margin for every line
        y = 0
        for ln in BANNER_LINES:
            safe_addstr(win, y, left, ln, amber())
            y += 1
        sub = f"a tiny launcher for your toolkit, made by markart25 on github  ·  v{__version__}"
        safe_addstr(win, y, max(0, (width - len(sub)) // 2), sub, curses.A_DIM)
        return y + 2  # blank line, then hint
    safe_addstr(win, 0, 1, "penknife", amber() | curses.A_BOLD)
    safe_addstr(win, 0, 10, f"v{__version__}", curses.A_DIM)
    return 2


def breadcrumb(tool):
    def fn(win, _width):
        safe_addstr(win, 0, 1, "penknife", amber() | curses.A_BOLD)
        safe_addstr(win, 0, 10, f"› {tool['name']}", curses.A_DIM)
        return 2
    return fn


# ─── renderers ───────────────────────────────────────────────────────────────
def render_tool(tool, _width):
    segs = [("  ", 0), (tool["name"], curses.A_BOLD)]
    if not tool.get("_installed", True):
        segs.append((" ✗", red()))
    desc = tool.get("description", "")
    cat = tool.get("category", "")
    if desc:
        segs.append((f"  ·  {desc}", curses.A_DIM))
    if cat:
        segs.append((f"  [{cat}]", curses.A_DIM))
    return segs


def render_preset(preset, _width):
    return [
        ("  ", 0),
        (preset.get("name", "?"), curses.A_BOLD),
        (f"  ·  {preset.get('command', '')}", curses.A_DIM),
    ]


# ─── generic vertical selector ───────────────────────────────────────────────
def select(win, items, render_item, header_fn, hint, allow_back=False, start=0):
    idx = max(0, min(start, len(items) - 1))
    offset = 0
    while True:
        win.erase()
        h, w = win.getmaxyx()
        hint_y = header_fn(win, w)
        safe_addstr(win, hint_y, 1, hint, curses.A_DIM)
        list_top = hint_y + 2
        avail = max(1, h - list_top)

        if idx < offset:
            offset = idx
        if idx >= offset + avail:
            offset = idx - avail + 1

        for i in range(offset, min(len(items), offset + avail)):
            draw_line(win, list_top + (i - offset), w, render_item(items[i], w), i == idx)

        if offset > 0:
            safe_addstr(win, list_top - 1, w - 4, "▲", curses.A_DIM)
        if offset + avail < len(items):
            safe_addstr(win, h - 1, w - 4, "▼", curses.A_DIM)

        win.noutrefresh()
        curses.doupdate()

        ch = win.getch()
        if ch in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(items)
        elif ch in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(items)
        elif ch in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT, ord("l"), ord(" ")):
            return "select", idx
        elif ch in (ord("q"), ord("Q")):
            return "quit", idx
        elif allow_back and ch in (27, curses.KEY_BACKSPACE, 127, 8, curses.KEY_LEFT, ord("h")):
            return "back", idx
        elif ch == curses.KEY_RESIZE:
            continue


# ─── single-line command editor ──────────────────────────────────────────────
def edit_command(win, prefill):
    buf = list(prefill)
    pos = len(buf)
    curses.curs_set(1)
    try:
        while True:
            win.erase()
            h, w = win.getmaxyx()
            safe_addstr(win, 0, 1, "edit command", amber() | curses.A_BOLD)
            safe_addstr(win, 2, 1, "enter run  ·  esc cancel", curses.A_DIM)

            prompt_y = 4
            field_x = 3
            field_w = max(1, w - field_x - 1)
            s = "".join(buf)
            start = pos - (field_w - 1) if pos > field_w - 1 else 0
            safe_addstr(win, prompt_y, 1, "$ ", amber())
            safe_addstr(win, prompt_y, field_x, s[start:start + field_w], 0)

            ph = sorted(set(re.findall(r"\{[^}]+\}", s)))
            if ph:
                safe_addstr(win, prompt_y + 2, 1, "unfilled: " + " ".join(ph), curses.A_DIM)

            win.move(prompt_y, min(field_x + (pos - start), w - 1))
            win.noutrefresh()
            curses.doupdate()

            ch = win.getch()
            if ch in (curses.KEY_ENTER, 10, 13):
                return "".join(buf).strip() or None
            elif ch == 27:
                return None
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                if pos > 0:
                    del buf[pos - 1]
                    pos -= 1
            elif ch == curses.KEY_DC:
                if pos < len(buf):
                    del buf[pos]
            elif ch == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif ch == curses.KEY_RIGHT:
                pos = min(len(buf), pos + 1)
            elif ch == curses.KEY_HOME:
                pos = 0
            elif ch == curses.KEY_END:
                pos = len(buf)
            elif ch == curses.KEY_RESIZE:
                continue
            elif 32 <= ch <= 126:
                buf.insert(pos, chr(ch))
                pos += 1
    finally:
        curses.curs_set(0)


# ─── launch ───────────────────────────────────────────────────────────────────
def run_command(cmd):
    curses.endwin()
    print()
    print(f"  \033[33m▶ running\033[0m  {cmd}")
    print(f"  \033[2m{'─' * min(60, len(cmd) + 12)}\033[0m")
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print("\n  \033[2minterrupted\033[0m")
    except Exception as e:  # noqa: BLE001
        print(f"\n  \033[31merror:\033[0m {e}")
    try:
        input("\n  \033[2m[done] press enter to return to penknife\033[0m ")
    except (EOFError, KeyboardInterrupt):
        pass


def resume(win):
    curses.flushinp()
    win.clear()
    curses.curs_set(0)
    win.refresh()


# ─── main loop ─────────────────────────────────────────────────────────────────
def main(win, tools):
    curses.curs_set(0)
    setup_colors()
    win.keypad(True)
    ti = 0
    while True:
        action, ti = select(
            win, tools, render_tool, draw_banner,
            "↑↓/jk move  ·  enter select  ·  q quit",
            allow_back=False, start=ti,
        )
        if action == "quit":
            return
        tool = tools[ti]
        presets = tool.get("presets") or [
            {"name": "Custom", "command": (tool.get("check") or tool["name"].split()[0]) + " "}
        ]
        pi = 0
        while True:
            paction, pi = select(
                win, presets, render_preset, breadcrumb(tool),
                "↑↓/jk move  ·  enter select  ·  esc back  ·  q quit",
                allow_back=True, start=pi,
            )
            if paction == "quit":
                return
            if paction == "back":
                break
            cmd = edit_command(win, presets[pi].get("command", ""))
            if not cmd:
                continue
            run_command(cmd)
            resume(win)


# ─── config ─────────────────────────────────────────────────────────────────────
def load_tools():
    created = False
    if not os.path.exists(CONFIG_FILE):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump({"tools": DEFAULT_TOOLS}, f, indent=2)
            created = True
        except OSError as e:
            print(f"penknife: could not create {CONFIG_FILE}: {e}", file=sys.stderr)
            return DEFAULT_TOOLS, False
    try:
        with open(CONFIG_FILE) as f:
            tools = json.load(f).get("tools", [])
    except (json.JSONDecodeError, OSError) as e:
        print(f"penknife: error reading {CONFIG_FILE}: {e}", file=sys.stderr)
        print("penknife: falling back to built-in defaults", file=sys.stderr)
        tools = DEFAULT_TOOLS
    return tools, created


def cli():
    locale.setlocale(locale.LC_ALL, "")  # let curses render UTF-8 (the banner)
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(HELP)
        return
    if any(a in ("-v", "--version") for a in args):
        print(f"penknife {__version__}")
        return
    if "--config" in args:
        print(CONFIG_FILE)
        return
    if "--reset" in args:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump({"tools": DEFAULT_TOOLS}, f, indent=2)
        print(f"penknife: reset {CONFIG_FILE} to defaults")
        return

    tools, created = load_tools()
    if created:
        print(f"penknife: created {CONFIG_FILE}")
        print("penknife: edit it to add/remove tools and presets\n")
    if not tools:
        print(f"penknife: no tools configured - edit {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    for t in tools:
        chk = t.get("check") or t["name"].split()[0]
        t["_installed"] = shutil.which(chk) is not None

    os.environ.setdefault("ESCDELAY", "25")
    try:
        curses.wrapper(main, tools)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
