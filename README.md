# fcookex — Firefox Cookie Exporter CLI

Search Firefox cookies by keyword, export all matching cookies in one shot or interactively pick the ones you want, and save them as a [Netscape HTTP Cookie File](https://curl.se/docs/http-cookies.html) — the format accepted by curl, yt-dlp, wget, and most download tools.

---

## Requirements

- Python 3.12+
- Firefox installed with at least one profile
  - Linux: `~/.mozilla/firefox/`
  - macOS: `~/Library/Application Support/Firefox/`
  - Windows: `%APPDATA%\Mozilla\Firefox\`

## Installation

```bash
# Clone the repository
git clone https://github.com/marceltoledo/firefox_cookie_exporter_cli.git
cd firefox_cookie_exporter_cli

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the package
pip install .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

---

## Usage

```
fcookex --search <keyword>
        [--profile <name>]
        [--output <filename>]
        [--append]
        [--all]
        [--show-values]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--search` | `-s` | **required** | Filter cookies by host, name, or value |
| `--profile` | `-p` | default profile | Firefox profile name to read from |
| `--output` | `-o` | `cookies_<ISO8601>.txt` | Output filename (no path, `.txt` added if absent) |
| `--append` | `-a` | off | Append to an existing file instead of overwriting |
| `--all` | `-A` | off | Export **all** matching cookies without the interactive selection prompt |
| `--show-values` | — | off | Reveal cookie values in the interactive selection list (ignored with `--all`) |

### Interactive selection (without `--all`)

After the search runs, a checkbox list is shown. Use the keyboard to select cookies:

| Key | Action |
|-----|--------|
| `Space` | Toggle selection |
| `↑` / `↓` | Move cursor |
| `Enter` | Confirm and export |

Cookie values are masked as `***` by default. Pass `--show-values` to reveal them (a confirmation prompt will appear).

---

## Examples

**Export all cookies for a domain in one shot (no interactive prompt):**

```bash
fcookex --search youtube.com --all --output youtube-cookies
# Writes all matching cookies to export/youtube-cookies.txt
```

**Search and export cookies for a domain using the default profile (interactive):**

```bash
fcookex --search youtube.com
```

**Use a specific Firefox profile:**

```bash
fcookex --search github.com --profile work
```

**Custom output filename:**

```bash
fcookex --search example.com --output my_session
# Writes to export/my_session.txt
```

**Append cookies to an existing file:**

```bash
fcookex --search api.example.com --output saved --append
```

**Reveal cookie values during interactive selection:**

```bash
fcookex --search example.com --show-values
```

---

## Output

Exported files are written to the `export/` directory relative to where you run the command. The default filename is `cookies_<ISO8601>.txt`, e.g. `export/cookies_20260418T153000Z.txt`.

The file format is standard Netscape:

```
# Netscape HTTP Cookie File
# https://curl.se/docs/http-cookies.html

.example.com	TRUE	/	TRUE	9999999999	session_id	abc123
```

### Using with curl

```bash
curl -b export/cookies_20260418T153000Z.txt https://example.com
```

### Using with yt-dlp

```bash
yt-dlp --cookies export/cookies_20260418T153000Z.txt https://example.com/video
```

---

## Notes

- **Firefox must be closed** (or at least the target profile not in use) for a consistent read. The tool warns if a lock file is detected but proceeds with a copy of the database.
- `--output` accepts a bare filename only. Paths containing `/` or `..` are rejected to prevent accidental writes outside the `export/` directory.
- `--all` skips the interactive checkbox entirely — every cookie matched by `--search` is written to the output file. Combine with `--output` to give the file a predictable name.
- In `--append` mode, the Netscape header is written only once (skipped if the file already has content), keeping the file valid for consumers.

---

## Running tests

```bash
pytest tests/ -v
```

---

## License

See [LICENSE](LICENSE).
