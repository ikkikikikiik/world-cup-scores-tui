Built this because I wanted a lowkey World Cup scoreboard for work that wouldn't distract me too much.

## Requirements

- Python 3.10+

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Web dashboard

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.
<img width="853" height="539" alt="image" src="https://github.com/user-attachments/assets/11d1b84a-d6d1-41c2-b646-49e2e3446327" />

## Terminal dashboard (TUI)

```bash
python tui.py
```

Keys:

- `r` — refresh now
- `q` — quit
<img width="500" height="320" alt="image" src="https://github.com/user-attachments/assets/774f37cc-4814-417f-a968-42c6bc39ab06" />
<img width="500" height="320" alt="image" src="https://github.com/user-attachments/assets/c748baff-ce3a-46b6-8534-182cc49bf86a" />

## API

- `GET /` — Dashboard UI
- `GET /api/scoreboard` — Normalized scoreboard data

## Notes

- This uses ESPN's public, undocumented API. It may change or become unavailable.
