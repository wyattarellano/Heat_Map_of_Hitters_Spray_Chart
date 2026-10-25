"""Create a hitter spray heat map using a target pitcher's throwing hand."""

import argparse
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import requests
from pybaseball import cache, playerid_lookup, plot_stadium, statcast_batter


FIELD_EXTENT = (0, 250, -250, 0)
MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people/{player_id}"


#Signature: str -> date
#Purpose: Parse a YYYY-MM-DD command-line argument into a date, or raise an argparse error
def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD format") from exc


#Signature: str | None, str | None, int | None, str -> int
#Purpose: Return the given MLBAM ID, or look one up from the player's first and last name
def resolve_player_id(first_name: str | None, last_name: str | None, player_id: int | None, role: str) -> int:
    if player_id is not None:
        return player_id

    if not first_name or not last_name:
        raise ValueError(f"Provide --{role}-id or both --{role}-first-name and --{role}-last-name")

    matches = playerid_lookup(last_name, first_name)
    if matches.empty:
        raise ValueError(f"No player found for {first_name} {last_name}")

    matches = matches.dropna(subset=["key_mlbam"]).drop_duplicates("key_mlbam")
    if len(matches) != 1:
        candidates = matches[["name_first", "name_last", "key_mlbam"]].to_string(index=False)
        raise ValueError(
            f"More than one {role} matched. Re-run with --{role}-id. Candidates:\n"
            f"{candidates}"
        )

    return int(matches.iloc[0]["key_mlbam"])


#Signature: int, DataFrame -> str
#Purpose: Return the pitcher's throwing hand ("L" or "R"), read from the batter's Statcast data
#         if they faced each other, otherwise looked up from the MLB Stats API
def get_pitcher_hand(pitcher_id: int, batter_data) -> str:
    hands = []
    if {"pitcher", "p_throws"}.issubset(batter_data.columns):
        faced = batter_data.loc[batter_data["pitcher"].eq(pitcher_id), "p_throws"]
        hands = faced.dropna().str.upper().unique()

    if len(hands) == 0:
        try:
            response = requests.get(MLB_PEOPLE_URL.format(player_id=pitcher_id), timeout=10)
            response.raise_for_status()
            hands = [response.json()["people"][0]["pitchHand"]["code"].upper()]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise ValueError(f"Could not look up throwing hand for pitcher ID {pitcher_id}") from exc

    if len(hands) != 1 or hands[0] not in {"L", "R"}:
        raise ValueError(f"Could not determine one throwing hand for pitcher ID {pitcher_id}")
    return hands[0]


#Signature: DataFrame, str -> DataFrame
#Purpose: Keep balls in play with hit coordinates against pitchers of the given hand, excluding home runs
def fieldable_balls(data, pitcher_hand: str):
    subset = data.loc[data["p_throws"].eq(pitcher_hand)]
    subset = subset.dropna(subset=["events", "hc_x", "hc_y"])
    return subset.loc[subset["events"].ne("home_run")]


#Signature: Axes, DataFrame, str, str -> PolyCollection | None
#Purpose: Draw the stadium outline and a hexbin heat map (each hexagon's % of batted balls) on ax;
#         returns None when there are no balls to plot
def plot_hand_panel(ax, balls, pitcher_hand: str, stadium: str):
    hand_label = "Left-handed pitchers" if pitcher_hand == "L" else "Right-handed pitchers"
    plot_stadium(stadium, title=hand_label, axis=ax)
    ax.set_xlim(FIELD_EXTENT[0], FIELD_EXTENT[1])
    ax.set_ylim(FIELD_EXTENT[2], FIELD_EXTENT[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"{hand_label} (n={len(balls):,})")

    if balls.empty:
        ax.text(
            125,
            -125,
            "No chartable balls in play",
            ha="center",
            va="center",
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
        )
        return None

    collection = ax.hexbin(
        balls["hc_x"],
        -balls["hc_y"],
        gridsize=28,
        extent=FIELD_EXTENT,
        mincnt=1,
        cmap="YlOrRd",
        linewidths=0,
        alpha=0.8,
    )
    collection.set_array(collection.get_array() / len(balls) * 100)
    return collection


#Signature: DataFrame, str, str, str, str, Path, bool -> None
#Purpose: Build the full heat map figure (panel, colorbar, titles), save it as a PNG,
#         and optionally show it in a window
def build_heatmap(
    data,
    batter_label: str,
    pitcher_label: str,
    pitcher_hand: str,
    stadium: str,
    output: Path,
    show: bool = False,
) -> None:
    required = {"p_throws", "events", "hc_x", "hc_y"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Statcast data is missing required columns: {', '.join(sorted(missing))}")

    balls = fieldable_balls(data, pitcher_hand)
    fig, ax = plt.subplots(figsize=(8, 8))
    collection = plot_hand_panel(ax, balls, pitcher_hand, stadium)
    if collection is not None:
        collection.set_clim(0, float(collection.get_array().max()))
        fig.colorbar(
            collection,
            ax=ax,
            shrink=0.78,
            label="Share of batted balls per hexagon (%)",
        )

    hand_label = "left-handed" if pitcher_hand == "L" else "right-handed"
    fig.suptitle(
        f"{batter_label}: spray by pitcher hand\n"
        f"Target pitcher: {pitcher_label} ({hand_label})",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.02,
        "Map includes this hitter's fieldable balls against all pitchers of the target's hand; home runs excluded.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    print(f"Target pitcher throws {hand_label}.")
    print(f"Included {len(balls):,} fieldable batted balls against {hand_label} pitchers.")
    print(f"Saved heat map to {output.resolve()}")
    if show:
        plt.show()
    else:
        plt.close(fig)


#Signature: int, int, str, str, str, str, str, Path, bool -> str
#Purpose: Fetch the hitter's Statcast data, find the target pitcher's hand, build the heat map,
#         and return the pitcher's hand
def create_heatmap_for_pitcher(
    batter_id: int,
    pitcher_id: int,
    start_date: str,
    end_date: str,
    batter_label: str,
    pitcher_label: str,
    stadium: str = "generic",
    output: Path = Path("output/spray_heatmap.png"),
    show: bool = False,
) -> str:
    batter_data = statcast_batter(start_date, end_date, batter_id)
    pitcher_hand = get_pitcher_hand(pitcher_id, batter_data)
    build_heatmap(batter_data, batter_label, pitcher_label, pitcher_hand, stadium, output, show)
    return pitcher_hand


#Signature: None -> None
#Purpose: Parse command-line arguments, resolve player IDs and labels, and run the heat map pipeline
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a hitter spray heat map based on a target pitcher's throwing hand."
    )
    parser.add_argument("--first-name", help="Hitter's first name")
    parser.add_argument("--last-name", help="Hitter's last name")
    parser.add_argument("--player-id", type=int, help="Hitter's MLBAM ID")
    parser.add_argument("--pitcher-first-name", help="Target pitcher's first name")
    parser.add_argument("--pitcher-last-name", help="Target pitcher's last name")
    parser.add_argument("--pitcher-id", type=int, help="Target pitcher's MLBAM ID")
    parser.add_argument("--start-date", required=True, type=iso_date, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, type=iso_date, help="End date, YYYY-MM-DD")
    parser.add_argument(
        "--stadium",
        default="generic",
        help="pybaseball stadium key for the field outline (default: generic)",
    )
    parser.add_argument("--output", type=Path, help="Output PNG path")
    parser.add_argument("--show", action="store_true", help="Open the chart in a window after saving")
    args = parser.parse_args()
    cache.enable()

    if args.start_date > args.end_date:
        parser.error("--start-date must be on or before --end-date")

    try:
        batter_id = resolve_player_id(args.first_name, args.last_name, args.player_id, "batter")
        pitcher_id = resolve_player_id(
            args.pitcher_first_name,
            args.pitcher_last_name,
            args.pitcher_id,
            "pitcher",
        )
    except ValueError as exc:
        parser.error(str(exc))

    batter_label = " ".join(part for part in (args.first_name, args.last_name) if part)
    if not batter_label:
        batter_label = f"Batter {batter_id}"
    pitcher_label = " ".join(
        part for part in (args.pitcher_first_name, args.pitcher_last_name) if part
    )
    if not pitcher_label:
        pitcher_label = f"Pitcher {pitcher_id}"

    output = args.output
    if output is None:
        slug = f"{batter_label}_{pitcher_label}".lower().replace(" ", "_")
        output = Path("output") / (
            f"{slug}_spray_heatmap_{args.start_date}_{args.end_date}.png"
        )

    print(f"Fetching hitter data for {batter_label}...")
    print(f"Looking up throwing hand for {pitcher_label}...")
    try:
        create_heatmap_for_pitcher(
            batter_id=batter_id,
            pitcher_id=pitcher_id,
            start_date=args.start_date.isoformat(),
            end_date=args.end_date.isoformat(),
            batter_label=batter_label,
            pitcher_label=pitcher_label,
            stadium=args.stadium,
            output=output,
            show=args.show,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()