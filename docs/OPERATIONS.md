# Operations and Troubleshooting

Reviewed for TrendClip Studio v0.5.0 on 2026-11-20.

## Start and stop

Run the one-time Setup launcher before the first start or after replacing the Python environment:

- macOS: `Setup TrendClip Studio.command`
- Windows: `Setup TrendClip Studio.bat`
- Linux: `./setup-trendclip.sh`

Setup installs Python packages only inside `.venv`. Python 3.10+, FFmpeg/ffprobe, and Node.js LTS are explicit system prerequisites and are never silently installed.

Start with `Start TrendClip Studio.command` on macOS, `Start TrendClip Studio.bat` on Windows, or `./start-trendclip.sh` on Linux. The local server opens `http://127.0.0.1:8765`; only the default niche refreshes in the background so startup remains responsive. From an activated project environment, the equivalent command is:

```bash
python3 -m trendclip studio
```

Stop a terminal-run server with `Ctrl+C`. Publishing is always manual in this release.

## Normal workflow

1. Refresh stories if needed and choose a source.
2. Optionally refine the GTA 6 search query.
3. Leave **Chrome YouTube session** off unless the selected source specifically requires the signed-in browser session.
4. Analyze the selected source as a third-party local review draft. TrendClip downloads audio plus a small visual proxy and prepares up to three draft recommendations.
5. If no candidate passes the editorial quality gate, choose another source instead of forcing a weak clip. Otherwise create the recommended balanced Top pick draft, or optionally choose punchy High energy or clean Quick hit. Only that video range is downloaded at full quality for rendering, and each created variation remains available.
6. Download the package and upload manually if you decide it is appropriate.

The browser-session switch controls access only. It does not establish ownership or publication rights.

## Diagnostics

`state/logs/studio.log` is newline-delimited JSON. `state/jobs/<job-id>/job.json` holds durable stages and history. Log messages are length-bounded and redact project/home paths and common secret labels; cookie values are never stored or logged.

Useful checks:

```bash
python3 -m unittest discover -s tests -v
tail -n 50 state/logs/studio.log
```

If a video says sign-in is required, enable the Chrome-session switch and make sure YouTube is signed in within Chrome. If YouTube provides no playable formats, update the project environment so yt-dlp and its matching EJS package remain current; Studio automatically enables the installed Node runtime for challenge solving. Some sources may still be unavailable and should be skipped.

## Verification record

On 2026-11-22 the full suite passed 80 tests locally, and the adaptive-framing commit passed the hosted Windows, macOS, and Linux matrix with Python 3.10 and 3.12. Python compilation, browser JavaScript syntax, macOS/Linux launcher syntax, and Windows PowerShell parsing passed in CI. Live loopback dashboard/API smoke checks passed locally where applicable, and desktop plus 390×844 responsive layouts were visually verified. The local doctor passed Python, private environment, FFmpeg, ffprobe, Node.js, yt-dlp, Faster Whisper, OpenCV, project storage, and Codex detection. A bounded real Codex CLI smoke test using the signed-in ChatGPT session selected the stronger fighter-jet candidate from a real cached transcript and returned schema-valid rationale; it used no cookies or publishing action. Eight live GTA 6 sources were evaluated locally, three layouts produced structurally valid real-media renders, and the embedded-portrait news case was rerendered with adaptive framing: 56% detection confidence, one stable crop, 60% of frames cropped, and landscape inserts preserved by hysteresis. Downloaded media and evaluation outputs remain ignored. Windows/Linux real-hardware media-pipeline smoke tests and a rights-cleared creator benchmark remain required before a packaged release.
