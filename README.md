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
<img width="1505" height="998" alt="image" src="https://github.com/user-attachments/assets/11d1b84a-d6d1-41c2-b646-49e2e3446327" />

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Terminal dashboard (TUI)
Waiting for next game:
<img width="853" height="539" alt="image" src="https://github.com/user-attachments/assets/774f37cc-4814-417f-a968-42c6bc39ab06" />
Live:
<img width="833" height="547" alt="image" src="https://github.com/user-attachments/assets/0332012a-1833-471c-9035-a0bf8b746862" />


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
