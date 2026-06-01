# penknife (script kiddie tool) (101 on how to larp)

```
██████╗ ███████╗███╗   ██╗██╗  ██╗███╗   ██╗██╗███████╗███████╗
██╔══██╗██╔════╝████╗  ██║██║ ██╔╝████╗  ██║██║██╔════╝██╔════╝
██████╔╝█████╗  ██╔██╗ ██║█████╔╝ ██╔██╗ ██║██║█████╗  █████╗
██╔═══╝ ██╔══╝  ██║╚██╗██║██╔═██╗ ██║╚██╗██║██║██╔══╝  ██╔══╝
██║     ███████╗██║ ╚████║██║  ██╗██║ ╚████║██║██║     ███████╗
╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝     ╚══════╝
```

A tiny TUI launcher for your pentest toolkit. Run it, arrow-key to a tool,
pick a preset, tweak the command, launch. Zero dependencies, stdlib `curses`
only.

## Install

```bash
git clone https://github.com/markart25/penknife
cd penknife
chmod +x penknife.py
sudo cp penknife.py /usr/local/bin/penknife
```

Then just run `penknife`.

## Usage

```
penknife            launch the menu
penknife --help     help
penknife --config   print the config path
penknife --reset    restore default tools
```

Flow: **tool list → preset → editable command → launch**. After the tool
exits you drop back into penknife.

Tools that aren't installed show a dim `✗` but you can still select them.

## Keys

| key            | action       |
|----------------|--------------|
| `↑`/`↓` `j`/`k`| move         |
| `enter` `l`    | select       |
| `esc` `h`      | back         |
| `q`            | quit         |

In the command editor: `enter` runs, `esc` cancels, arrows/home/end move.

## Config

Tools live in `~/.config/penknife/tools.json`, created on first run. Edit it
to add, remove, or re-order tools and presets:

```json
{
  "tools": [
    {
      "name": "nmap",
      "category": "recon",
      "description": "network/port scanner",
      "presets": [
        { "name": "Quick scan", "command": "nmap -T4 -F {target}" },
        { "name": "Custom", "command": "nmap " }
      ]
    }
  ]
}
```

- `name` — display name (and the binary checked for, unless `check` is set)
- `check` — optional, the binary to look for if it differs (e.g. metasploit → `msfconsole`)
- `category` — free-text tag shown in the list
- `presets[].command` — the command, with `{placeholder}` hints you fill in the editor

Placeholders like `{target}`, `{wordlist}`, `{port}` are just reminders —
penknife flags any you leave unfilled before launch.

Comes with ~26 tools out of the box (nmap, ffuf, gobuster, sqlmap, hydra,
netexec, responder, metasploit, and more).

## Notes

Commands run through your shell exactly as shown in the editor — penknife
doesn't sanitise them. It's a launcher for tools *you* control, on targets
*you're authorised to test*.

## Licence

MIT. Patches welcome.
