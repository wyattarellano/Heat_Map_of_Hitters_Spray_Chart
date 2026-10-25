# Heat_Map_of_Hitters_Spray_Chart
This is a side project I'm working on for data and software engineering experience. I want to produce a heat map of a hitter's spray chart for a given pitcher.

# Why?

There are plenty of spray charts out there for baseball hitters, however I have not been able to find a heat map for a hitter based upon a pitcher's style. This repo will have all the code to create a heat map on a hitters spray chart for optimal defensive positioning.

# Setup

Requires Python 3.10 or newer.

```bash
git clone https://github.com/wyattarellano/Heat_Map_of_Hitters_Spray_Chart.git
cd Heat_Map_of_Hitters_Spray_Chart
python -m venv .venv
```

Activate the virtual environment:

- Windows (PowerShell): `.\.venv\Scripts\Activate.ps1`
- macOS / Linux: `source .venv/bin/activate`

Then install the dependencies:

```bash
pip install -r requirements.txt
```

# Usage

Give the script a hitter, a target pitcher, and a date range:

```bash
python spray_heatmap_using_pitcher_handedness.py --first-name Aaron --last-name Judge --pitcher-first-name Chris --pitcher-last-name Sale --start-date 2025-03-30 --end-date 2025-10-01 --stadium yankees
```

The heat map is saved as a PNG in the `output/` folder.

## Options

| Flag | Required | Description |
|---|---|---|
| `--first-name`, `--last-name` | Yes, or `--player-id` | Hitter's name |
| `--player-id` | Yes, or hitter's name | Hitter's MLBAM ID |
| `--pitcher-first-name`, `--pitcher-last-name` | Yes, or `--pitcher-id` | Target pitcher's name |
| `--pitcher-id` | Yes, or pitcher's name | Target pitcher's MLBAM ID |
| `--start-date`, `--end-date` | Yes | Date range in `YYYY-MM-DD` format |
| `--stadium` | No | Stadium outline to draw, e.g. `yankees` (default: `generic`) |
| `--output` | No | Custom path for the PNG |
| `--show` | No | Open the chart in a window after saving |

If a name matches more than one player, the script lists the matching players and their IDs. Re-run it with `--player-id` or `--pitcher-id`.

## What the chart shows

The script looks up which hand the target pitcher throws with. It then maps where the hitter's batted balls went against **all** pitchers who throw with that hand during the date range. Home runs are left out, since fielders can't position for them. Each hexagon's color shows the share of the hitter's batted balls that landed there.

# Acknowledgement

I created this project because of my interest in baseball savant and data analytics. I want to thank my coaches at Seton Hall University for always being there to help me out with any questions I have during my time here

# Credit

I used pybaseball to create this. The link to it is here: https://github.com/jldbc/pybaseball

