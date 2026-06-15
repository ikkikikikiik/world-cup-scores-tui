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

## Terminal dashboard (TUI)

```bash
python tui.py
```

Keys:

- `r` — refresh now
- `q` — quit

## API

- `GET /` — Dashboard UI
- `GET /api/scoreboard` — Normalized scoreboard data

## Notes

- This uses ESPN's public, undocumented API. It may change or become unavailable.
