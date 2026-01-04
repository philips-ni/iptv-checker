# iptv-checker

A CLI tool to check IPTV playlists and streams for validity using `ffprobe` and `ffmpeg`. It can filter out dead links and detect common "Error" or "Channel Offline" screens using visual analysis.

## Prerequisites

This tool requires `ffmpeg` and `ffprobe` to be installed and available in your system's PATH.

- **Linux:** `sudo apt install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Installation

You can install the package directly from the source:

```bash
pip install .
```

For development purposes, install it in editable mode:

```bash
pip install -e .
```

## Usage

Once installed, the `iptv-checker` command will be available in your terminal.

### Basic Usage

Check a single URL:
```bash
iptv-checker --url "http://example.com/stream.m3u8"
```

Clean an M3U playlist file (the file will be overwritten with only working links):
```bash
iptv-checker --file playlist.m3u
```

### Advanced Usage

**Thorough Mode:**
Perform a deep check by capturing a video frame and analyzing it for error text (requires `Pillow`).
```bash
iptv-checker --file playlist.m3u --thorough
```

**Parallel Workers:**
Speed up checking large playlists by using multiple threads (default is 1).
```bash
iptv-checker --file playlist.m3u --workers 10
```

**Keep Captured Frames:**
Keep the frames captured during thorough validation for manual inspection.
```bash
iptv-checker --file playlist.m3u --thorough --keep-frames --output-dir my_captures
```

### All Options

| Option | Shortcut | Description |
|--------|----------|-------------|
| `--file` | `-f` | Path to a file containing URLs to test (M3U or CSV). |
| `--url` | `-u` | A single URL to test. |
| `--thorough`| `-t` | Perform 2nd level validation by capturing video frames. |
| `--keep-frames`| `-k` | Keep the captured video frames (requires `--thorough`). |
| `--workers` | `-w` | Number of parallel workers (default: 1). |
| `--output-dir`| `-o` | Directory to save captured images (default: `captured_images`). |

## Supported Formats

- **M3U Playlists:** Handles `#EXTINF` tags and preserves them for working links.
- **CSV/Text:** Lines formatted as `Channel Name,URL`.
- **Raw URLs:** Plain list of URLs.

## Development

To build the package distribution:

```bash
pip install build
python -m build
```
