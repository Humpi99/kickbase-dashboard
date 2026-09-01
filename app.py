"""
Kickbase Liga-Dashboard.

Ansichten:
- Manager
- Liga
- Transfermarkt
"""

from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from kickbase_api import KickbaseAPI
from transfermarkt import render_transfer_market


# ---------------------------------------------------------
# Konstanten
# ---------------------------------------------------------

COLOR_POSITIVE = "#12a150"
COLOR_NEGATIVE = "#e03131"
COLOR_NEUTRAL = "#1c1c1c"
COLOR_LABEL = "#8a8a8a"
COLOR_LINE = "#e6e6e6"

BASE_BUDGET = 150_000_000
REQUIRED_LINEUP_SIZE = 11

IMAGE_BASE_URL = "https://kickbase.b-cdn.net/"

TEAM_LOGO_SIZE = 17
PLAYER_PHOTO_SIZE = 24
TEAM_LOGO_SIZE_MOBILE = 14
PLAYER_PHOTO_SIZE_MOBILE = 20

LEAGUE_HEADER_MAIN = "#f2f4f7"
LEAGUE_HEADER_TREND = "#eaf6ef"
LEAGUE_HEADER_BUDGET = "#fff3e3"


# ---------------------------------------------------------
# Allgemeine Hilfsfunktionen
# ---------------------------------------------------------

def first_value(data, keys, default=None):
    """Gibt den ersten vorhandenen Wert zurück."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def first_text(data, keys):
    """Gibt den ersten nicht leeren Text zurück."""
    if not isinstance(data, dict):
        return ""

    for key in keys:
        value = data.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def to_number(value):
    """Wandelt einen Wert sicher in eine Zahl um."""
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_currency(value):
    """Formatiert einen Betrag in Millionen Euro."""
    number = to_number(value)

    if number is None:
        return "—"

    amount = number / 1_000_000
    text = f"{amount:,.2f}"
    text = text.replace(",", "X")
    text = text.replace(".", ",")
    text = text.replace("X", ".")

    return f"{text} Mio. €"


def format_signed_currency(value):
    """Formatiert einen Betrag mit Vorzeichen."""
    number = to_number(value)

    if number is None:
        return "—"

    if number >= 0:
        return f"+{format_currency(number)}"

    return f"-{format_currency(abs(number))}"


def format_points(value):
    """Formatiert Punkte."""
    number = to_number(value)

    if number is None:
        return "—"

    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")

    text = f"{number:,.1f}"
    text = text.replace(",", "X")
    text = text.replace(".", ",")
    text = text.replace("X", ".")

    return text


def format_average_points(value):
    """Formatiert den Punktedurchschnitt."""
    number = to_number(value)

    if number is None:
        return "—"

    return f"{number:.1f}".replace(".", ",")


def tone_of(value):
    """Bestimmt den Farbton eines Zahlenwertes."""
    number = to_number(value)

    if number is None or number == 0:
        return "neutral"

    return "plus" if number > 0 else "minus"


def collect_dictionaries(data, depth=0):
    """Sammelt verschachtelte Dictionaries."""
    found = []

    if depth > 8:
        return found

    if isinstance(data, dict):
        found.append(data)

        for value in data.values():
            found.extend(
                collect_dictionaries(
                    value,
                    depth + 1,
                )
            )

    elif isinstance(data, list):
        for item in data:
            found.extend(
                collect_dictionaries(
                    item,
                    depth + 1,
                )
            )

    return found


def flatten_fields(value, prefix="", depth=0):
    """Wandelt Daten für die Diagnose in Zeilen um."""
    rows = []

    if depth > 5:
        return rows

    if isinstance(value, dict):
        for key, nested_value in value.items():
            field_name = f"{prefix}{key}"

            if isinstance(nested_value, (dict, list)):
                rows.extend(
                    flatten_fields(
                        nested_value,
                        f"{field_name}.",
                        depth + 1,
                    )
                )
            else:
                rows.append(
                    {
                        "Feld": field_name,
                        "Wert": repr(nested_value),
                    }
                )

    elif isinstance(value, list):
        rows.append(
            {
                "Feld": f"{prefix}[Liste]",
                "Wert": f"{len(value)} Einträge",
            }
        )

        for index, item in enumerate(value[:3]):
            rows.extend(
                flatten_fields(
                    item,
                    f"{prefix}{index}.",
                    depth + 1,
                )
            )

    return rows


def sort_frame(
    frame,
    columns,
    key,
    default_column,
    compact=False,
):
    """Sortiert eine Tabelle über stabile Auswahlfelder."""
    available = [
        column
        for column in columns
        if column in frame.columns
    ]

    if not available:
        return frame.reset_index(drop=True)

    default_index = (
        available.index(default_column)
        if default_column in available
        else 0
    )

    if compact:
        sort_column = st.selectbox(
            "Sortieren nach",
            available,
            index=default_index,
            key=f"{key}_column",
        )

        direction = st.selectbox(
            "Reihenfolge",
            ["Absteigend", "Aufsteigend"],
            key=f"{key}_direction",
        )
    else:
        left, right = st.columns([3, 2])

        sort_column = left.selectbox(
            "Sortieren nach",
            available,
            index=default_index,
            key=f"{key}_column",
        )

        direction = right.selectbox(
            "Reihenfolge",
            ["Absteigend", "Aufsteigend"],
            key=f"{key}_direction",
        )

    return frame.sort_values(
        sort_column,
        ascending=(direction == "Aufsteigend"),
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)


# ---------------------------------------------------------
# IDs und Namen
# ---------------------------------------------------------

def get_league_id(league):
    value = first_value(
        league,
        ["id", "i", "leagueId", "li"],
        "",
    )

    return str(value) if value is not None else ""


def get_league_name(league):
    return str(
        first_value(
            league,
            ["name", "n", "leagueName", "ln"],
            "Unbekannte Liga",
        )
    )


def get_manager_id(manager):
    value = first_value(
        manager,
        [
            "id",
            "i",
            "u",
            "userId",
            "uid",
            "ui",
        ],
        "",
    )

    return str(value) if value is not None else ""


def get_manager_name(manager):
    return str(
        first_value(
            manager,
            [
                "name",
                "unm",
                "n",
                "username",
                "un",
                "teamName",
                "tn",
            ],
            "Unbekannter Manager",
        )
    )


def get_player_id(player):
    value = first_value(
        player,
        [
            "id",
            "i",
            "playerId",
            "pi",
            "pid",
        ],
    )

    return str(value) if value is not None else None


def get_player_name(player):
    first_name = first_value(
        player,
        ["firstName", "fn", "pfn"],
        "",
    )

    last_name = first_value(
        player,
        ["lastName", "ln", "pln"],
        "",
    )

    combined = f"{first_name} {last_name}".strip()

    if combined:
        return combined

    name = first_value(
        player,
        ["name", "n", "playerName", "pn"],
    )

    return str(name) if name else "Unbekannt"


def get_short_player_name(player):
    last_name = first_value(
        player,
        ["lastName", "ln", "pln"],
    )

    if last_name:
        return str(last_name)

    return get_player_name(player)


# ---------------------------------------------------------
# Listen erkennen
# ---------------------------------------------------------

def looks_like_league(item):
    if not isinstance(item, dict):
        return False

    has_id = any(
        key in item
        for key in ["id", "i", "leagueId", "li"]
    )

    has_name = any(
        key in item
        for key in ["name", "n", "leagueName", "ln"]
    )

    return has_id and has_name


def looks_like_manager(item):
    if not isinstance(item, dict):
        return False

    if not get_manager_id(item):
        return False

    if get_manager_name(item) == "Unbekannter Manager":
        return False

    markers = {
        "unm",
        "u",
        "userId",
        "uid",
        "ui",
        "tv",
        "teamValue",
        "placement",
        "rank",
        "shp",
        "uim",
    }

    return bool(markers.intersection(item.keys()))


def find_list(
    value,
    check_function,
    preferred_keys,
    depth=0,
):
    if depth > 8:
        return []

    if isinstance(value, list):
        matches = [
            item
            for item in value
            if check_function(item)
        ]

        if matches:
            return matches

        for item in value:
            result = find_list(
                item,
                check_function,
                preferred_keys,
                depth + 1,
            )

            if result:
                return result

    elif isinstance(value, dict):
        for key in preferred_keys:
            if key in value:
                result = find_list(
                    value[key],
                    check_function,
                    preferred_keys,
                    depth + 1,
                )

                if result:
                    return result

        for key, nested_value in value.items():
            if key in {
                "tkn",
                "token",
                "accessToken",
            }:
                continue

            result = find_list(
                nested_value,
                check_function,
                preferred_keys,
                depth + 1,
            )

            if result:
                return result

    return []


def find_leagues(value):
    return find_list(
        value,
        looks_like_league,
        ["leagues", "lgs", "ls", "srvl"],
    )


def find_managers(value):
    return find_list(
        value,
        looks_like_manager,
        [
            "us",
            "users",
            "u",
            "managers",
            "ranking",
            "items",
            "it",
        ],
    )


# ---------------------------------------------------------
# Eigenen Manager erkennen
# ---------------------------------------------------------

def has_own_manager_marker(manager):
    if not isinstance(manager, dict):
        return False

    for key in [
        "me",
        "isMe",
        "isOwn",
        "own",
        "currentUser",
        "isCurrentUser",
    ]:
        value = manager.get(key)

        if value is True or value == 1 or value == "1":
            return True

    return False


def resolve_own_manager_id(api, managers):
    own_user_id = getattr(api, "own_user_id", None)

    if own_user_id is not None:
        own_text = str(own_user_id)

        for manager in managers:
            if get_manager_id(manager) == own_text:
                return own_text

    for manager in managers:
        if has_own_manager_marker(manager):
            return get_manager_id(manager)

    return None


def is_own_manager(own_manager_id, manager_id):
    if not own_manager_id:
        return False

    return str(own_manager_id) == str(manager_id)


def order_managers_own_first(managers, own_manager_id):
    if not own_manager_id:
        return managers

    return sorted(
        managers,
        key=lambda manager: (
            0
            if is_own_manager(
                own_manager_id,
                get_manager_id(manager),
            )
            else 1
        ),
    )


# ---------------------------------------------------------
# Spielerwerte
# ---------------------------------------------------------

MARKET_VALUE_KEYS = [
    "mv",
    "marketValue",
    "currentValue",
    "cv",
]

PROFIT_KEYS = [
    "mvgl",
    "profit",
    "prof",
]

DAILY_CHANGE_KEYS = [
    "tfhmvt",
    "mvt",
    "sdmvt",
    "dmv",
]

PLAYER_TOTAL_POINTS_KEYS = [
    "p",
    "pts",
    "points",
    "totalPoints",
    "total_points",
    "seasonPoints",
    "season_points",
    "tp",
]

PLAYER_AVERAGE_POINTS_KEYS = [
    "ap",
    "avg",
    "average",
    "averagePoints",
    "average_points",
    "avgPoints",
    "avg_points",
    "pointsAverage",
    "points_average",
    "pointsPerMatch",
    "points_per_match",
    "ppg",
]

PLAYER_MATCH_COUNT_KEYS = [
    "appearances",
    "matches",
    "games",
    "playedMatches",
    "played_matches",
    "matchCount",
    "match_count",
    "apps",
    "mp",
    "mdc",
]


def get_market_value(player):
    return to_number(
        first_value(
            player,
            MARKET_VALUE_KEYS,
        )
    )


def get_profit(player):
    return to_number(
        first_value(
            player,
            PROFIT_KEYS,
        )
    )


def get_buy_price(player):
    market_value = get_market_value(player)
    profit = get_profit(player)

    if market_value is None or profit is None:
        return None

    return market_value - profit


def get_daily_change(player):
    return to_number(
        first_value(
            player,
            DAILY_CHANGE_KEYS,
        )
    )


def get_lineup_slot(player):
    if not isinstance(player, dict):
        return None

    number = to_number(player.get("lo"))

    if number is None:
        return None

    if 0 <= number <= 10:
        return int(number)

    return None


def is_in_lineup(player):
    return get_lineup_slot(player) is not None


def get_points_from_dictionary(data):
    if not isinstance(data, dict):
        return None, None

    total = to_number(
        first_value(
            data,
            PLAYER_TOTAL_POINTS_KEYS,
        )
    )

    average = to_number(
        first_value(
            data,
            PLAYER_AVERAGE_POINTS_KEYS,
        )
    )

    match_count = to_number(
        first_value(
            data,
            PLAYER_MATCH_COUNT_KEYS,
        )
    )

    if (
        average is None
        and total is not None
        and match_count is not None
        and match_count > 0
    ):
        average = total / match_count

    return total, average


def find_player_points(data, player_id=None, depth=0):
    if depth > 8:
        return None, None

    if isinstance(data, dict):
        current_id = first_value(
            data,
            ["id", "i", "playerId", "pi", "pid"],
        )

        id_matches = (
            player_id is None
            or current_id is None
            or str(current_id) == str(player_id)
        )

        if id_matches:
            total, average = get_points_from_dictionary(
                data
            )

            if total is not None or average is not None:
                return total, average

        for nested_value in data.values():
            total, average = find_player_points(
                nested_value,
                player_id,
                depth + 1,
            )

            if total is not None or average is not None:
                return total, average

    elif isinstance(data, list):
        for item in data:
            total, average = find_player_points(
                item,
                player_id,
                depth + 1,
            )

            if total is not None or average is not None:
                return total, average

    return None, None


def load_player_points(api, league_id, player):
    player_id = get_player_id(player)

    total, average = get_points_from_dictionary(
        player
    )

    if total is not None and average is not None:
        return total, average

    if not player_id:
        return total, average

    cache_key = (
        f"player_points_v4_{league_id}_{player_id}"
    )

    if cache_key in st.session_state:
        cached = st.session_state[cache_key]

        return (
            cached.get("total"),
            cached.get("average"),
        )

    paths = [
        f"/v4/players/{player_id}",
        (
            f"/v4/leagues/{league_id}"
            f"/players/{player_id}"
        ),
        (
            f"/v4/competitions/1"
            f"/players/{player_id}"
        ),
    ]

    for path in paths:
        try:
            details = api.get(path)
        except Exception:
            continue

        found_total, found_average = (
            find_player_points(
                details,
                player_id,
            )
        )

        if total is None:
            total = found_total

        if average is None:
            average = found_average

        if total is not None and average is not None:
            break

    st.session_state[cache_key] = {
        "total": total,
        "average": average,
    }

    return total, average


def points_cell_html(total, average):
    if to_number(total) is None:
        return "—"

    total_text = format_points(total)

    if to_number(average) is None:
        return total_text

    return (
        f"{total_text} "
        "<span class='points-average'>"
        f"({format_average_points(average)} Ø)"
        "</span>"
    )


# ---------------------------------------------------------
# Managerpunkte
# ---------------------------------------------------------

def contains_current_matchday(value, depth=0):
    if depth > 8:
        return False

    if isinstance(value, dict):
        if value.get("cur") is True:
            return True

        for nested_value in value.values():
            if contains_current_matchday(
                nested_value,
                depth + 1,
            ):
                return True

    elif isinstance(value, list):
        for item in value:
            if contains_current_matchday(
                item,
                depth + 1,
            ):
                return True

    return False


def collect_manager_seasons(value, depth=0):
    seasons = []

    if depth > 8:
        return seasons

    if isinstance(value, dict):
        season_name = value.get("sn")
        season_id = value.get("sid")

        accumulated_points = to_number(
            value.get("ap")
        )

        total_points = to_number(
            value.get("tp")
        )

        is_season = (
            (
                season_name is not None
                or season_id is not None
            )
            and (
                accumulated_points is not None
                or total_points is not None
            )
        )

        if is_season:
            seasons.append(
                {
                    "name": str(season_name or ""),
                    "id": season_id,
                    "points": (
                        accumulated_points
                        if accumulated_points is not None
                        else total_points
                    ),
                    "current": contains_current_matchday(
                        value.get("it", [])
                    ),
                }
            )

        for nested_value in value.values():
            seasons.extend(
                collect_manager_seasons(
                    nested_value,
                    depth + 1,
                )
            )

    elif isinstance(value, list):
        for item in value:
            seasons.extend(
                collect_manager_seasons(
                    item,
                    depth + 1,
                )
            )

    return seasons


def choose_current_season_points(seasons):
    if not seasons:
        return None

    now = datetime.now()

    start_year = (
        now.year
        if now.month >= 7
        else now.year - 1
    )

    expected_name = (
        f"{start_year}/{start_year + 1}"
    )

    for season in seasons:
        if season["name"] == expected_name:
            return season["points"]

    for season in seasons:
        if season["current"]:
            return season["points"]

    def season_sort_value(season):
        season_id = to_number(season.get("id"))

        return (
            season_id
            if season_id is not None
            else -1
        )

    newest = max(
        seasons,
        key=season_sort_value,
    )

    return newest["points"]


def load_manager_points(
    api,
    league_id,
    manager_id,
):
    cache_key = (
        f"manager_points_v3_"
        f"{league_id}_{manager_id}"
    )

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    base = (
        f"/v4/leagues/{league_id}"
        f"/managers/{manager_id}"
    )

    user_base = (
        f"/v4/leagues/{league_id}"
        f"/users/{manager_id}"
    )

    paths = [
        f"{base}/performance",
        f"{base}/dashboard",
        f"{base}/profile",
        f"{base}/points",
        f"{base}/history",
        base,
        f"{user_base}/stats",
        f"{user_base}/profile",
    ]

    points = None

    for path in paths:
        try:
            data = api.get(path)
        except Exception:
            continue

        seasons = collect_manager_seasons(data)

        points = choose_current_season_points(
            seasons
        )

        if points is not None:
            break

    st.session_state[cache_key] = points

    return points


# ---------------------------------------------------------
# Vereins- und Spielplandaten
# ---------------------------------------------------------

TEAM_ID_KEYS = [
    "tid",
    "teamId",
    "ti",
    "clubId",
    "ci",
]

TEAM_NAME_KEYS = [
    "teamName",
    "clubName",
    "tn",
    "cn",
]

TEAM_SHORT_KEYS = [
    "tabb",
    "teamAbbreviation",
    "abbreviation",
    "tsym",
    "symbol",
    "shortName",
    "sn",
]

TEAM_IMAGE_KEYS = [
    "tim",
    "teamImage",
    "teamLogo",
    "clubImage",
    "clubLogo",
    "logo",
    "logoUrl",
    "crest",
    "badge",
    "tiy",
]

PLAYER_IMAGE_KEYS = [
    "pim",
    "playerImage",
    "plim",
    "profileImage",
    "image",
    "imageUrl",
    "img",
]


def build_image_url(value):
    if not isinstance(value, str):
        return ""

    cleaned = value.strip()

    if not cleaned:
        return ""

    if cleaned.startswith(("http://", "https://")):
        return cleaned

    if cleaned.startswith("//"):
        return f"https:{cleaned}"

    return IMAGE_BASE_URL + cleaned.lstrip("/")


def get_team_id(player):
    value = first_value(
        player,
        TEAM_ID_KEYS,
    )

    if value is None:
        return None

    if isinstance(value, (dict, list, bool)):
        return None

    return str(value)


def looks_like_team(item):
    if not isinstance(item, dict):
        return False

    if any(
        key in item
        for key in [
            "mv",
            "mvgl",
            "tfhmvt",
            "pim",
            "pn",
        ]
    ):
        return False

    team_id = first_value(
        item,
        ["id", "i", "tid", "teamId"],
    )

    if team_id is None:
        return False

    return bool(
        first_text(
            item,
            [
                "name",
                "n",
                "shortName",
                "sn",
                "tabb",
                "teamName",
                "tn",
            ],
        )
        or first_text(item, TEAM_IMAGE_KEYS)
    )


def extract_team_info(sources):
    teams = {}

    for source in sources:
        data = source.get("data")

        for item in collect_dictionaries(data):
            if not looks_like_team(item):
                continue

            team_id = str(
                first_value(
                    item,
                    ["id", "i", "tid", "teamId"],
                )
            )

            entry = teams.setdefault(
                team_id,
                {
                    "name": "",
                    "long_name": "",
                    "logo": "",
                },
            )

            if not entry["name"]:
                entry["name"] = first_text(
                    item,
                    TEAM_SHORT_KEYS,
                )

            if not entry["long_name"]:
                entry["long_name"] = first_text(
                    item,
                    [
                        "name",
                        "n",
                        "teamName",
                        "tn",
                    ],
                )

            if not entry["logo"]:
                entry["logo"] = build_image_url(
                    first_text(
                        item,
                        TEAM_IMAGE_KEYS,
                    )
                )

    for entry in teams.values():
        if not entry["name"]:
            entry["name"] = entry["long_name"]

    return teams


def get_team_name(team_id, teams):
    if not team_id:
        return ""

    entry = teams.get(str(team_id), {})

    return (
        entry.get("name")
        or entry.get("long_name")
        or ""
    )


def get_team_logo(team_id, teams):
    if not team_id:
        return ""

    return teams.get(
        str(team_id),
        {},
    ).get("logo", "")


def get_club_label(player, teams):
    direct = first_text(
        player,
        TEAM_SHORT_KEYS + TEAM_NAME_KEYS,
    )

    if direct:
        return direct

    return get_team_name(
        get_team_id(player),
        teams,
    )


def get_player_club_logo(player, teams):
    direct = build_image_url(
        first_text(
            player,
            TEAM_IMAGE_KEYS,
        )
    )

    if direct:
        return direct

    return get_team_logo(
        get_team_id(player),
        teams,
    )


def get_player_photo(player):
    return build_image_url(
        first_text(
            player,
            PLAYER_IMAGE_KEYS,
        )
    )


def image_html(
    url,
    label,
    size,
    css_class,
):
    safe_label = escape(str(label or ""))

    if not url:
        return ""

    return (
        f"<img src='{escape(url)}' "
        f"alt='{safe_label}' "
        f"title='{safe_label}' "
        f"class='{css_class}' "
        f"style='height:{size}px;width:{size}px;' />"
    )


def parse_any_date(value):
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed
        except ValueError:
            pass

    number = to_number(value)

    if number is None:
        return None

    try:
        if number > 10_000_000_000:
            number /= 1000

        if number > 1_000_000_000:
            return datetime.fromtimestamp(
                number,
                tz=timezone.utc,
            )
    except (
        ValueError,
        OSError,
        OverflowError,
    ):
        pass

    return None


def extract_matches(sources):
    matches = []
    seen = set()
    now = datetime.now(timezone.utc)

    for source in sources:
        for item in collect_dictionaries(
            source.get("data")
        ):
            home_id = first_value(
                item,
                [
                    "t1",
                    "homeTeamId",
                    "home",
                    "ht",
                ],
            )

            away_id = first_value(
                item,
                [
                    "t2",
                    "awayTeamId",
                    "away",
                    "at",
                ],
            )

            if home_id is None or away_id is None:
                continue

            if isinstance(home_id, (dict, list, bool)):
                continue

            if isinstance(away_id, (dict, list, bool)):
                continue

            match_date = None

            for key in [
                "dt",
                "date",
                "kickoff",
                "startDate",
                "md",
            ]:
                match_date = parse_any_date(
                    item.get(key)
                )

                if match_date is not None:
                    break

            if match_date is None or match_date < now:
                continue

            signature = (
                str(home_id),
                str(away_id),
                match_date.isoformat(),
            )

            if signature in seen:
                continue

            seen.add(signature)

            matches.append(
                {
                    "home_id": str(home_id),
                    "away_id": str(away_id),
                    "home_logo": build_image_url(
                        first_text(
                            item,
                            [
                                "t1im",
                                "t1i",
                                "homeTeamImage",
                                "htim",
                            ],
                        )
                    ),
                    "away_logo": build_image_url(
                        first_text(
                            item,
                            [
                                "t2im",
                                "t2i",
                                "awayTeamImage",
                                "atim",
                            ],
                        )
                    ),
                    "home_name": first_text(
                        item,
                        [
                            "t1n",
                            "homeTeamName",
                            "htn",
                        ],
                    ),
                    "away_name": first_text(
                        item,
                        [
                            "t2n",
                            "awayTeamName",
                            "atn",
                        ],
                    ),
                    "date": match_date,
                }
            )

    return matches


def build_next_matches(matches, count=2):
    by_team = {}

    for match in sorted(
        matches,
        key=lambda item: item["date"],
    ):
        date_text = match["date"].strftime(
            "%d.%m."
        )

        by_team.setdefault(
            match["home_id"],
            [],
        ).append(
            {
                "opponent_id": match["away_id"],
                "opponent_logo": match["away_logo"],
                "opponent_name": match["away_name"],
                "place": "H",
                "date": date_text,
            }
        )

        by_team.setdefault(
            match["away_id"],
            [],
        ).append(
            {
                "opponent_id": match["home_id"],
                "opponent_logo": match["home_logo"],
                "opponent_name": match["home_name"],
                "place": "A",
                "date": date_text,
            }
        )

    return {
        team_id: entries[:count]
        for team_id, entries in by_team.items()
    }


def load_team_and_match_data(api, league_id):
    try:
        competition_sources, _ = (
            api.get_competition()
        )
    except Exception:
        competition_sources = []

    try:
        team_sources, _ = api.get_teams()
    except Exception:
        team_sources = []

    try:
        match_sources, _ = api.get_matches(
            league_id
        )
    except Exception:
        match_sources = []

    all_sources = (
        competition_sources
        + team_sources
        + match_sources
    )

    teams = extract_team_info(all_sources)
    matches = extract_matches(match_sources)

    return {
        "teams": teams,
        "next_matches": build_next_matches(
            matches
        ),
        "sources": all_sources,
    }


def build_next_matches_text(
    team_id,
    next_matches,
    teams,
):
    entries = next_matches.get(
        str(team_id or ""),
        [],
    )

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent = (
            entry.get("opponent_name")
            or get_team_name(
                entry["opponent_id"],
                teams,
            )
            or "Gegner"
        )

        parts.append(
            f"{entry['place']} "
            f"{opponent} "
            f"{entry['date']}"
        )

    return " · ".join(parts)


def build_next_matches_html(
    team_id,
    next_matches,
    teams,
    logo_size,
):
    entries = next_matches.get(
        str(team_id or ""),
        [],
    )

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent_id = entry["opponent_id"]

        opponent_name = (
            entry.get("opponent_name")
            or get_team_name(opponent_id, teams)
            or "Gegner"
        )

        opponent_logo = (
            entry.get("opponent_logo")
            or get_team_logo(opponent_id, teams)
        )

        logo = image_html(
            opponent_logo,
            opponent_name,
            logo_size,
            "team-logo",
        )

        parts.append(
            "<span class='match-entry'>"
            f"<b>{entry['place']}</b>"
            f"{logo}"
            f"<span>{entry['date']}</span>"
            "</span>"
        )

    return "".join(parts)


# ---------------------------------------------------------
# Spieltag
# ---------------------------------------------------------

def collect_future_dates(data, depth=0):
    dates = []

    if depth > 7:
        return dates

    now = datetime.now(timezone.utc)

    if isinstance(data, dict):
        for key, value in data.items():
            if key in {
                "dt",
                "date",
                "startDate",
                "kickoff",
                "md",
                "mdst",
                "deadline",
            }:
                parsed = parse_any_date(value)

                if parsed is not None and parsed > now:
                    dates.append(parsed)

            dates.extend(
                collect_future_dates(
                    value,
                    depth + 1,
                )
            )

    elif isinstance(data, list):
        for item in data:
            dates.extend(
                collect_future_dates(
                    item,
                    depth + 1,
                )
            )

    return dates


def find_days_to_matchday(api, league_id):
    paths = [
        f"/v4/leagues/{league_id}/matchdays",
        f"/v4/leagues/{league_id}/matchday",
        "/v4/competitions/1/matchdays",
        "/v4/competitions/1/matchday",
        "/v4/matchdays",
    ]

    now = datetime.now(timezone.utc)

    for path in paths:
        try:
            data = api.get(path)
        except Exception:
            continue

        dates = collect_future_dates(data)

        if dates:
            difference = min(dates) - now

            return max(
                0,
                int(
                    (
                        difference.total_seconds()
                        + 86_399
                    )
                    // 86_400
                ),
            )

    return None


# ---------------------------------------------------------
# Kader und Kennzahlen
# ---------------------------------------------------------

def find_players(data):
    candidates = []

    for item in collect_dictionaries(data):
        if (
            get_player_id(item)
            and get_market_value(item) is not None
        ):
            candidates.append(item)

    players_by_id = {}

    for player in candidates:
        player_id = get_player_id(player)
        existing = players_by_id.get(player_id)

        if existing is None or len(player) > len(existing):
            players_by_id[player_id] = player

    return list(players_by_id.values())


def load_manager_players(
    api,
    league_id,
    manager_id,
):
    try:
        data = api.get_manager_squad(
            league_id,
            manager_id,
        )

        return find_players(data), None
    except Exception as error:
        return [], str(error)


def compute_stats(players):
    stats = {
        "squad_value": 0.0,
        "lineup_value": 0.0,
        "trading_value": 0.0,
        "buy_total": 0.0,
        "buy_lineup": 0.0,
        "buy_trading": 0.0,
        "profit_in_club": 0.0,
        "trend_total": 0.0,
        "trend_lineup": 0.0,
        "trend_trading": 0.0,
        "lineup_count": 0,
        "trading_count": 0,
        "player_count": len(players),
    }

    for player in players:
        market_value = (
            get_market_value(player) or 0.0
        )

        buy_price = (
            get_buy_price(player) or 0.0
        )

        profit = get_profit(player) or 0.0
        trend = get_daily_change(player) or 0.0

        stats["squad_value"] += market_value
        stats["buy_total"] += buy_price
        stats["profit_in_club"] += profit
        stats["trend_total"] += trend

        if is_in_lineup(player):
            stats["lineup_value"] += market_value
            stats["buy_lineup"] += buy_price
            stats["trend_lineup"] += trend
            stats["lineup_count"] += 1
        else:
            stats["trading_value"] += market_value
            stats["buy_trading"] += buy_price
            stats["trend_trading"] += trend
            stats["trading_count"] += 1

    return stats


def get_lineup_matchday_value(
    stats,
    days_to_matchday,
):
    return (
        stats["lineup_value"]
        + stats["trend_lineup"]
        * days_to_matchday
    )


def load_realized_profit(
    api,
    league_id,
    manager_id,
):
    try:
        value, _ = api.get_realized_profit(
            league_id,
            manager_id,
        )

        return value
    except Exception:
        return None


def load_real_budget(api, league_id):
    try:
        value, _ = api.get_budget(league_id)
        return value
    except Exception:
        return None


def compute_budget(
    stats,
    total_profit,
    bonus,
    days_to_matchday,
    real_balance=None,
):
    if real_balance is not None:
        balance = real_balance
    else:
        balance = (
            BASE_BUDGET
            + bonus
            + total_profit
            - stats["squad_value"]
        )

    after_sale = (
        balance
        + stats["trading_value"]
    )

    at_matchday = (
        after_sale
        + stats["trend_trading"]
        * days_to_matchday
    )

    return {
        "balance": balance,
        "after_sale": after_sale,
        "at_matchday": at_matchday,
    }


def compute_own_bonus(
    api,
    league_id,
    own_manager_id,
    real_balance,
):
    if not own_manager_id or real_balance is None:
        return None

    players, _ = load_manager_players(
        api,
        league_id,
        own_manager_id,
    )

    if not players:
        return None

    stats = compute_stats(players)

    realized = load_realized_profit(
        api,
        league_id,
        own_manager_id,
    )

    total_profit = (
        stats["profit_in_club"]
        + (realized or 0.0)
    )

    calculated = (
        BASE_BUDGET
        + total_profit
        - stats["squad_value"]
    )

    return {
        "plain": calculated,
        "real": real_balance,
        "bonus": real_balance - calculated,
    }


# ---------------------------------------------------------
# HTML-Tabellen
# ---------------------------------------------------------

def signed_value_html(value):
    number = to_number(value)
    text = format_signed_currency(value)

    if number is None or number == 0:
        return escape(text)

    css_class = (
        "value-plus"
        if number > 0
        else "value-minus"
    )

    return (
        f"<span class='{css_class}'>"
        f"{escape(text)}"
        "</span>"
    )


def render_squad_table(
    frame,
    columns,
    compact,
):
    """Zeigt die bereits sortierte Spielerliste ohne Links."""
    headers = "".join(
        f"<th>{escape(column)}</th>"
        for column in columns
    )

    rows = []

    for _, row in frame.iterrows():
        row_class = (
            "trading"
            if row["Status"] == "Trading"
            else ""
        )

        cells = []

        for column in columns:
            if column == "Spieler":
                content = row["_player_html"]

            elif column == "Punkte":
                content = points_cell_html(
                    row["Punkte"],
                    row["_average_points"],
                )

            elif column == "Nächste Spiele":
                content = row["_matches_html"]

            elif column in {
                "Einstandspreis",
                "Marktwert",
            }:
                content = escape(
                    format_currency(row[column])
                )

            elif column in {
                "Gewinn gesamt",
                "Trend 24 Stunden",
            }:
                content = signed_value_html(
                    row[column]
                )

            else:
                value = row[column]

                if value is None:
                    content = "—"
                else:
                    content = escape(str(value))

            cells.append(f"<td>{content}</td>")

        rows.append(
            f"<tr class='{row_class}'>"
            f"{''.join(cells)}"
            "</tr>"
        )

    table_class = (
        "squad-table mobile"
        if compact
        else "squad-table"
    )

    st.markdown(
        "<div class='table-wrapper'>"
        f"<table class='{table_class}'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


def build_squad_label(
    player_count,
    lineup_count,
):
    total = to_number(player_count)
    lineup = to_number(lineup_count)

    if total is None:
        return "—"

    total_text = str(int(total))

    if (
        lineup is None
        or int(lineup) == REQUIRED_LINEUP_SIZE
    ):
        return total_text

    return f"{total_text} ({int(lineup)})"


def league_header_class(column):
    if column in {
        "Trend Start 11",
        "Trend Trading",
        "Trend gesamt",
    }:
        return "league-header-trend"

    if column in {
        "Budget",
        "Nach Verkauf",
        "Budget Spieltag",
        "S11 Spieltag",
    }:
        return "league-header-budget"

    return "league-header-main"


def format_league_value(column, value):
    if column == "Punkte":
        return format_points(value)

    if column in {
        "Start 11",
        "Trading",
        "Kaderwert",
        "S11 Spieltag",
    }:
        return format_currency(value)

    if value is None:
        return "—"

    return str(value)


def render_league_table(
    frame,
    columns,
    compact,
):
    """Zeigt die Liga mit farbigen Spaltenköpfen ohne Links."""
    headers = "".join(
        (
            f"<th class='{league_header_class(column)}'>"
            f"{escape(column)}"
            "</th>"
        )
        for column in columns
    )

    rows = []

    signed_columns = {
        "Gewinn gesamt",
        "Trend Start 11",
        "Trend Trading",
        "Trend gesamt",
        "Budget",
        "Nach Verkauf",
        "Budget Spieltag",
    }

    for _, row in frame.iterrows():
        cells = []

        for column in columns:
            if column == "Manager":
                display_name = (
                    f"● {row['Manager']}"
                    if row["Ich"]
                    else row["Manager"]
                )

                content = (
                    "<span class='manager-name'>"
                    f"{escape(display_name)}"
                    "</span>"
                )

            elif column == "Kader":
                label = build_squad_label(
                    row["Kader"],
                    row["Startelf-Anzahl"],
                )

                lineup_count = to_number(
                    row["Startelf-Anzahl"]
                )

                warning = (
                    lineup_count is None
                    or int(lineup_count)
                    != REQUIRED_LINEUP_SIZE
                )

                css_class = (
                    "squad-warning"
                    if warning
                    else ""
                )

                content = (
                    f"<span class='{css_class}'>"
                    f"{escape(label)}"
                    "</span>"
                )

            elif column in signed_columns:
                content = signed_value_html(
                    row[column]
                )

            else:
                content = escape(
                    format_league_value(
                        column,
                        row[column],
                    )
                )

            cells.append(f"<td>{content}</td>")

        rows.append(
            f"<tr>{''.join(cells)}</tr>"
        )

    table_class = (
        "league-table mobile"
        if compact
        else "league-table"
    )

    st.markdown(
        "<div class='table-wrapper league-wrapper'>"
        f"<table class='{table_class}'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# KPI-Blöcke
# ---------------------------------------------------------

def kpi_block(title, entries, compact):
    colors = {
        "neutral": COLOR_NEUTRAL,
        "plus": COLOR_POSITIVE,
        "minus": COLOR_NEGATIVE,
    }

    value_size = 19 if compact else 24

    st.markdown(
        f"<div class='kpi-title'>{escape(title)}</div>",
        unsafe_allow_html=True,
    )

    columns = st.columns(len(entries))

    for column, entry in zip(columns, entries):
        label, value, notes, tone = entry

        notes_html = "".join(
            (
                "<div class='kpi-note'>"
                f"{escape(str(note))}"
                "</div>"
            )
            for note in notes
            if note
        )

        column.markdown(
            "<div class='kpi-card'>"
            f"<div class='kpi-label'>{escape(label)}</div>"
            f"<div class='kpi-value' "
            f"style='font-size:{value_size}px;"
            f"color:{colors.get(tone, COLOR_NEUTRAL)};'>"
            f"{value}"
            "</div>"
            f"{notes_html}"
            "</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

APP_STYLE = """
<style>
.login-heading {
    text-align: center;
    margin-top: 3rem;
    font-size: 2rem;
    font-weight: 750;
}

.login-subheading {
    text-align: center;
    color: #777777;
    margin-bottom: 1.4rem;
}

.login-security {
    padding: 0.8rem 1rem;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    background: #fafafa;
    color: #666666;
    margin-top: 0.8rem;
}

.top-nav-label {
    color: #8a8a8a;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0.25rem 0 0.35rem;
}

.table-wrapper {
    width: 100%;
    overflow-x: auto;
    margin: 0.5rem 0 0.7rem;
}

.squad-table,
.league-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
}

.squad-table {
    min-width: 1050px;
}

.league-table {
    min-width: 1380px;
    border: 1px solid #e6e6e6;
}

.squad-table.mobile {
    min-width: 930px;
    font-size: 0.74rem;
}

.league-table.mobile {
    min-width: 1060px;
    font-size: 0.72rem;
}

.squad-table th,
.league-table th {
    text-align: left;
    padding: 0.6rem 0.55rem;
    border-bottom: 1px solid #dedede;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    white-space: nowrap;
}

.squad-table th {
    background: #f2f4f7;
    color: #555555;
}

.squad-table td,
.league-table td {
    padding: 0.5rem 0.55rem;
    border-bottom: 1px solid #eeeeee;
    white-space: nowrap;
    vertical-align: middle;
}

.squad-table tr.trading td {
    color: #9a9a9a;
    background: #fafafa;
}

.league-table tbody tr:hover td {
    background: #fafafa;
}

.league-header-main {
    background: #f2f4f7;
}

.league-header-trend {
    background: #eaf6ef;
}

.league-header-budget {
    background: #fff3e3;
}

.manager-name {
    color: #1c1c1c;
    font-weight: 700;
}

.squad-warning {
    color: #e03131;
    font-weight: 700;
}

.value-plus {
    color: #12a150;
    font-weight: 600;
}

.value-minus {
    color: #e03131;
    font-weight: 600;
}

.points-average {
    color: #8a8a8a;
    font-size: 0.82em;
}

.player-cell {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.player-photo {
    object-fit: cover;
    border-radius: 50%;
    background: #f0f0f0;
}

.team-logo {
    object-fit: contain;
}

.player-name {
    font-weight: 600;
}

.match-entry {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    margin-right: 0.6rem;
}

.kpi-title {
    border-top: 1px solid #e6e6e6;
    padding-top: 10px;
    margin-top: 18px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8a8a8a;
}

.kpi-card {
    padding: 6px 0 2px;
}

.kpi-label,
.kpi-note {
    font-size: 12px;
    color: #8a8a8a;
}

.kpi-note {
    line-height: 1.5;
}

.kpi-value {
    font-weight: 700;
    padding: 2px 0 4px;
}

@media (max-width: 640px) {
    .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-top: 2.1rem !important;
    }

    .kpi-value {
        font-size: 16px !important;
        white-space: nowrap;
    }

    .kpi-note {
        font-size: 10px;
    }
}
</style>
"""


# ---------------------------------------------------------
# Seiteneinstellungen
# ---------------------------------------------------------

st.set_page_config(
    page_title="Kickbase Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    APP_STYLE,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Login
# ---------------------------------------------------------

if not st.session_state.get("logged_in"):
    _, login_column, _ = st.columns(
        [1, 1.15, 1]
    )

    with login_column:
        st.markdown(
            """
            <div class="login-heading">
                ⚽ Kickbase Dashboard
            </div>
            <div class="login-subheading">
                Melde dich mit deinem Kickbase-Konto an.
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            email = st.text_input(
                "Kickbase-E-Mail-Adresse",
            )

            password = st.text_input(
                "Kickbase-Passwort",
                type="password",
            )

            submitted = st.form_submit_button(
                "Einloggen",
                type="primary",
                use_container_width=True,
            )

        st.markdown(
            """
            <div class="login-security">
                🔒 Dein Passwort wird nicht gespeichert.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if submitted:
            if not email or not password:
                st.warning(
                    "Bitte E-Mail und Passwort eingeben."
                )
            else:
                try:
                    with st.spinner(
                        "Anmeldung läuft …"
                    ):
                        api = KickbaseAPI()

                        result = api.login(
                            email,
                            password,
                        )

                        leagues = find_leagues(
                            result
                        )

                    if not leagues:
                        st.error(
                            "Es wurde keine Liga erkannt."
                        )
                        st.stop()

                    st.session_state["api"] = api
                    st.session_state["leagues"] = leagues
                    st.session_state["logged_in"] = True
                    st.session_state["view"] = "Manager"
                    st.session_state[
                        "came_from_league"
                    ] = False

                    st.rerun()

                except Exception as error:
                    st.error(str(error))

    st.stop()


# ---------------------------------------------------------
# Grundeinstellungen
# ---------------------------------------------------------

api = st.session_state["api"]
leagues = st.session_state["leagues"]

if "view" not in st.session_state:
    st.session_state["view"] = "Manager"

compact = st.sidebar.toggle(
    "📱 Handy-Ansicht",
    value=False,
)

league_index = st.sidebar.selectbox(
    "Liga auswählen",
    range(len(leagues)),
    format_func=lambda index: (
        get_league_name(leagues[index])
    ),
)

selected_league = leagues[league_index]
league_id = get_league_id(selected_league)
league_name = get_league_name(selected_league)

show_realized = st.sidebar.checkbox(
    "Transferhistorie zusätzlich laden",
    value=not compact,
)

kpis_expanded = st.sidebar.checkbox(
    "Kennzahlen aufgeklappt starten",
    value=False,
)

team_logo_size = (
    TEAM_LOGO_SIZE_MOBILE
    if compact
    else TEAM_LOGO_SIZE
)

player_photo_size = (
    PLAYER_PHOTO_SIZE_MOBILE
    if compact
    else PLAYER_PHOTO_SIZE
)


# ---------------------------------------------------------
# Vereine und Spiele laden
# ---------------------------------------------------------

matches_key = (
    f"team_matches_v9_{league_id}"
)

if matches_key not in st.session_state:
    with st.spinner(
        "Vereine und Spielplan werden geladen …"
    ):
        st.session_state[matches_key] = (
            load_team_and_match_data(
                api,
                league_id,
            )
        )

matches_info = st.session_state[matches_key]
teams = matches_info["teams"]
next_matches = matches_info["next_matches"]


# ---------------------------------------------------------
# Budget und Spieltag
# ---------------------------------------------------------

budget_key = f"own_budget_{league_id}"

if budget_key not in st.session_state:
    st.session_state[budget_key] = (
        load_real_budget(api, league_id)
    )

own_budget = st.session_state[budget_key]

matchday_key = (
    f"matchday_days_{league_id}"
)

if matchday_key not in st.session_state:
    st.session_state[matchday_key] = (
        find_days_to_matchday(
            api,
            league_id,
        )
    )

found_days = st.session_state[matchday_key]

default_days = (
    int(found_days)
    if found_days is not None
    else 3
)

days_key = (
    f"days_to_matchday_{league_id}"
)

if days_key not in st.session_state:
    st.session_state[days_key] = default_days

days_to_matchday = st.sidebar.number_input(
    "Tage bis zum Spieltag",
    min_value=0,
    max_value=30,
    step=1,
    key=days_key,
)

if found_days is None:
    st.sidebar.caption(
        "Der Spieltag konnte nicht automatisch "
        "ermittelt werden."
    )
else:
    st.sidebar.caption(
        "Der nächste Spieltag wurde automatisch "
        "berücksichtigt."
    )


# ---------------------------------------------------------
# Titel und Navigation
# ---------------------------------------------------------

if compact:
    st.markdown(
        f"### ⚽ {escape(league_name)}",
        unsafe_allow_html=True,
    )
else:
    st.title(f"⚽ {league_name}")

st.markdown(
    "<div class='top-nav-label'>Ansicht</div>",
    unsafe_allow_html=True,
)

manager_nav, league_nav, market_nav = (
    st.columns(3)
)

with manager_nav:
    if st.button(
        "👤 Manager",
        key="nav_manager",
        type=(
            "primary"
            if st.session_state["view"] == "Manager"
            else "secondary"
        ),
        use_container_width=True,
    ):
        st.session_state["view"] = "Manager"
        st.session_state[
            "came_from_league"
        ] = False
        st.rerun()

with league_nav:
    if st.button(
        "🏆 Liga",
        key="nav_league",
        type=(
            "primary"
            if st.session_state["view"] == "Liga"
            else "secondary"
        ),
        use_container_width=True,
    ):
        st.session_state["view"] = "Liga"
        st.session_state[
            "came_from_league"
        ] = False
        st.rerun()

with market_nav:
    if st.button(
        "🛒 Transfermarkt",
        key="nav_market",
        type=(
            "primary"
            if (
                st.session_state["view"]
                == "Transfermarkt"
            )
            else "secondary"
        ),
        use_container_width=True,
    ):
        st.session_state["view"] = (
            "Transfermarkt"
        )
        st.session_state[
            "came_from_league"
        ] = False
        st.rerun()

view = st.session_state["view"]

if view == "Transfermarkt":
    render_transfer_market(
        api,
        league_id,
        compact=compact,
    )
    st.stop()


# ---------------------------------------------------------
# Manager laden
# ---------------------------------------------------------

with st.spinner("Manager werden geladen …"):
    ranking_sources, ranking_errors = (
        api.get_ranking(league_id)
    )

managers = []

for source in ranking_sources:
    managers = find_managers(
        source.get("data")
    )

    if managers:
        break

if not managers:
    st.error(
        "Es konnten keine Manager geladen werden."
    )

    if ranking_errors:
        with st.expander("Fehlerdetails"):
            st.write(ranking_errors)

    st.stop()

own_manager_id = resolve_own_manager_id(
    api,
    managers,
)

managers = order_managers_own_first(
    managers,
    own_manager_id,
)

manager_lookup = {
    get_manager_id(manager): manager
    for manager in managers
}

manager_ids = list(manager_lookup.keys())


# ---------------------------------------------------------
# Budget-Einstellungen
# ---------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.markdown("### Budget")

st.sidebar.caption(
    f"Grundwert fest: "
    f"{format_currency(BASE_BUDGET)}"
)

bonus_info_key = (
    f"own_bonus_info_{league_id}"
)

if bonus_info_key not in st.session_state:
    st.session_state[bonus_info_key] = (
        compute_own_bonus(
            api,
            league_id,
            own_manager_id,
            own_budget,
        )
    )

bonus_info = st.session_state[bonus_info_key]

suggested_bonus = (
    bonus_info["bonus"] / 1_000_000
    if bonus_info
    else 0.0
)

bonus_key = f"bonus_mio_{league_id}"

if bonus_key not in st.session_state:
    st.session_state[bonus_key] = round(
        suggested_bonus,
        2,
    )

bonus_mio = st.sidebar.number_input(
    "Bonus in Mio. €",
    min_value=-200.0,
    max_value=500.0,
    step=0.5,
    key=bonus_key,
)

bonus = bonus_mio * 1_000_000

if st.sidebar.button(
    "Bonus neu berechnen",
    key="recalculate_bonus",
    use_container_width=True,
):
    for state_key in list(st.session_state.keys()):
        if (
            state_key == bonus_info_key
            or state_key == budget_key
            or state_key.startswith(
                f"league_rows_v18_{league_id}"
            )
        ):
            st.session_state.pop(
                state_key,
                None,
            )

    st.rerun()

if bonus_info:
    st.sidebar.caption(
        "Eigene Berechnung ohne Bonus: "
        + format_currency(
            bonus_info["plain"]
        )
    )

    st.sidebar.caption(
        "Eigenes Budget: "
        + format_currency(
            bonus_info["real"]
        )
    )

    st.sidebar.caption(
        "Differenz als Bonus: "
        + format_signed_currency(
            bonus_info["bonus"]
        )
    )

st.sidebar.markdown("---")

if st.sidebar.button(
    "Abmelden",
    key="logout",
    use_container_width=True,
):
    st.session_state.clear()
    st.rerun()


# ---------------------------------------------------------
# Ligaansicht
# ---------------------------------------------------------

if view == "Liga":
    st.subheader("Liga-Vergleich")

    cache_key = (
        f"league_rows_v18_{league_id}"
    )

    if st.button(
        "Daten neu laden",
        key="reload_league_data",
    ):
        st.session_state.pop(
            cache_key,
            None,
        )

        for manager_id in manager_ids:
            st.session_state.pop(
                (
                    f"manager_points_v3_"
                    f"{league_id}_{manager_id}"
                ),
                None,
            )

        st.rerun()

    if cache_key not in st.session_state:
        rows = []

        progress = st.progress(
            0.0,
            text="Ligadaten werden geladen …",
        )

        for index, manager in enumerate(
            managers
        ):
            manager_id = get_manager_id(
                manager
            )

            players, _ = load_manager_players(
                api,
                league_id,
                manager_id,
            )

            stats = compute_stats(players)

            realized = load_realized_profit(
                api,
                league_id,
                manager_id,
            )

            points = load_manager_points(
                api,
                league_id,
                manager_id,
            )

            rows.append(
                {
                    "Manager-ID": manager_id,
                    "Manager": get_manager_name(
                        manager
                    ),
                    "Ich": is_own_manager(
                        own_manager_id,
                        manager_id,
                    ),
                    "Startelf-Anzahl": (
                        stats["lineup_count"]
                    ),
                    "Kader": (
                        stats["player_count"]
                    ),
                    "Punkte": points,
                    "Start 11": (
                        stats["lineup_value"]
                    ),
                    "Trading": (
                        stats["trading_value"]
                    ),
                    "Kaderwert": (
                        stats["squad_value"]
                    ),
                    "Gewinn gesamt": (
                        stats["profit_in_club"]
                        + (realized or 0.0)
                    ),
                    "Trend Start 11": (
                        stats["trend_lineup"]
                    ),
                    "Trend Trading": (
                        stats["trend_trading"]
                    ),
                    "Trend gesamt": (
                        stats["trend_total"]
                    ),
                    "S11 Spieltag": (
                        get_lineup_matchday_value(
                            stats,
                            days_to_matchday,
                        )
                    ),
                }
            )

            progress.progress(
                (index + 1) / len(managers),
                text=(
                    "Ligadaten werden geladen … "
                    f"{index + 1} von "
                    f"{len(managers)}"
                ),
            )

        progress.empty()
        st.session_state[cache_key] = rows

    league_frame = pd.DataFrame(
        st.session_state[cache_key]
    )

    league_frame["Budget"] = (
        BASE_BUDGET
        + bonus
        + league_frame["Gewinn gesamt"]
        - league_frame["Kaderwert"]
    )

    if own_budget is not None:
        league_frame.loc[
            league_frame["Ich"],
            "Budget",
        ] = own_budget

    league_frame["Nach Verkauf"] = (
        league_frame["Budget"]
        + league_frame["Trading"]
    )

    league_frame["Budget Spieltag"] = (
        league_frame["Nach Verkauf"]
        + league_frame["Trend Trading"]
        * days_to_matchday
    )

    if compact:
        visible_columns = [
            "Manager",
            "Punkte",
            "Kader",
            "Kaderwert",
            "Gewinn gesamt",
            "Trend gesamt",
            "Budget",
            "Nach Verkauf",
            "Budget Spieltag",
            "S11 Spieltag",
        ]
    else:
        visible_columns = [
            "Manager",
            "Punkte",
            "Kader",
            "Start 11",
            "Trading",
            "Kaderwert",
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
            "Budget",
            "Nach Verkauf",
            "Budget Spieltag",
            "S11 Spieltag",
        ]

    league_frame = sort_frame(
        league_frame,
        visible_columns,
        key="league_sort",
        default_column="Punkte",
        compact=compact,
    )

    render_league_table(
        league_frame,
        visible_columns,
        compact,
    )

    st.caption(
        "Hellgrau: Mannschaftswerte. "
        "Hellgrün: Trends. "
        "Hellorange: Budget und Prognosen."
    )

    st.markdown("#### Manager öffnen")

    manager_to_open = st.selectbox(
        "Manager auswählen",
        league_frame["Manager-ID"].tolist(),
        format_func=lambda manager_id: (
            get_manager_name(
                manager_lookup[str(manager_id)]
            )
        ),
        key="league_manager_to_open",
    )

    if st.button(
        "Manageransicht öffnen",
        key="open_manager_view",
        use_container_width=compact,
    ):
        selection_key = (
            f"manager_selection_{league_id}"
        )

        st.session_state[selection_key] = str(
            manager_to_open
        )

        st.session_state["view"] = "Manager"
        st.session_state[
            "came_from_league"
        ] = True

        st.rerun()

    st.stop()


# ---------------------------------------------------------
# Manageransicht
# ---------------------------------------------------------

if st.session_state.get("came_from_league"):
    if st.button(
        "← Zurück zur Liga-Übersicht",
        key="back_to_league",
    ):
        st.session_state["view"] = "Liga"
        st.session_state[
            "came_from_league"
        ] = False
        st.rerun()

selection_key = (
    f"manager_selection_{league_id}"
)

if selection_key not in st.session_state:
    st.session_state[selection_key] = (
        own_manager_id
        if own_manager_id in manager_ids
        else manager_ids[0]
    )

if (
    st.session_state[selection_key]
    not in manager_ids
):
    st.session_state[selection_key] = (
        own_manager_id
        if own_manager_id in manager_ids
        else manager_ids[0]
    )

selected_manager_id = st.selectbox(
    "Manager auswählen",
    manager_ids,
    key=selection_key,
    format_func=lambda manager_id: (
        (
            "● "
            if is_own_manager(
                own_manager_id,
                manager_id,
            )
            else ""
        )
        + get_manager_name(
            manager_lookup[manager_id]
        )
    ),
)

selected_manager_name = get_manager_name(
    manager_lookup[selected_manager_id]
)

viewing_self = is_own_manager(
    own_manager_id,
    selected_manager_id,
)

with st.spinner("Kader wird geladen …"):
    players, squad_error = (
        load_manager_players(
            api,
            league_id,
            selected_manager_id,
        )
    )

realized_profit = None

if players:
    realized_profit = load_realized_profit(
        api,
        league_id,
        selected_manager_id,
    )

stats = compute_stats(players)

total_profit = stats["profit_in_club"]

if realized_profit is not None:
    total_profit += realized_profit

budget = compute_budget(
    stats,
    total_profit,
    bonus,
    days_to_matchday,
    real_balance=(
        own_budget
        if viewing_self
        else None
    ),
)

with st.expander(
    (
        f"Kennzahlen: {selected_manager_name}"
        + (" ●" if viewing_self else "")
    ),
    expanded=(
        kpis_expanded
        or st.session_state.get(
            "came_from_league",
            False,
        )
    ),
):
    kpi_block(
        "Mannschaft",
        [
            (
                "Start 11",
                format_currency(
                    stats["lineup_value"]
                ),
                [
                    (
                        "Am Spieltag: "
                        + format_currency(
                            get_lineup_matchday_value(
                                stats,
                                days_to_matchday,
                            )
                        )
                    ),
                    (
                        "Einstand: "
                        + format_currency(
                            stats["buy_lineup"]
                        )
                    ),
                    (
                        f"{stats['lineup_count']} "
                        "Spieler"
                    ),
                ],
                "neutral",
            ),
            (
                "Trading",
                format_currency(
                    stats["trading_value"]
                ),
                [
                    (
                        "Einstand: "
                        + format_currency(
                            stats["buy_trading"]
                        )
                    ),
                    (
                        f"{stats['trading_count']} "
                        "Spieler"
                    ),
                ],
                "neutral",
            ),
            (
                "Gesamt",
                format_currency(
                    stats["squad_value"]
                ),
                [
                    (
                        "Einstand: "
                        + format_currency(
                            stats["buy_total"]
                        )
                    ),
                    (
                        f"{stats['player_count']} "
                        "Spieler"
                    ),
                ],
                "neutral",
            ),
        ],
        compact,
    )

    kpi_block(
        "Gewinn",
        [
            (
                "Realisiert",
                (
                    format_signed_currency(
                        realized_profit
                    )
                    if realized_profit is not None
                    else "—"
                ),
                [
                    "Gewinn aus abgeschlossenen Verkäufen"
                ],
                tone_of(realized_profit),
            ),
            (
                "Im Verein",
                format_signed_currency(
                    stats["profit_in_club"]
                ),
                [
                    "Noch nicht realisierter Gewinn"
                ],
                tone_of(
                    stats["profit_in_club"]
                ),
            ),
            (
                "Gesamt",
                format_signed_currency(
                    total_profit
                ),
                [
                    "Realisiert plus im Verein"
                ],
                tone_of(total_profit),
            ),
        ],
        compact,
    )

    kpi_block(
        "Trend",
        [
            (
                "Start 11",
                format_signed_currency(
                    stats["trend_lineup"]
                ),
                ["Letzte 24 Stunden"],
                tone_of(
                    stats["trend_lineup"]
                ),
            ),
            (
                "Trading",
                format_signed_currency(
                    stats["trend_trading"]
                ),
                ["Letzte 24 Stunden"],
                tone_of(
                    stats["trend_trading"]
                ),
            ),
            (
                "Gesamt",
                format_signed_currency(
                    stats["trend_total"]
                ),
                ["Letzte 24 Stunden"],
                tone_of(
                    stats["trend_total"]
                ),
            ),
        ],
        compact,
    )

    kpi_block(
        (
            "Budget"
            if viewing_self
            else "Budget geschätzt"
        ),
        [
            (
                "Budget",
                format_signed_currency(
                    budget["balance"]
                ),
                [
                    (
                        "Aktuelles Budget"
                        if viewing_self
                        else (
                            f"{format_currency(BASE_BUDGET)} "
                            "Grundwert plus Bonus und Gewinn, "
                            "minus Kaderwert"
                        )
                    )
                ],
                tone_of(budget["balance"]),
            ),
            (
                "Nach Verkauf",
                format_signed_currency(
                    budget["after_sale"]
                ),
                [
                    (
                        "Plus Trading: "
                        + format_currency(
                            stats["trading_value"]
                        )
                    ),
                    (
                        f"{stats['trading_count']} "
                        "Spieler"
                    ),
                ],
                tone_of(
                    budget["after_sale"]
                ),
            ),
            (
                "Budget Spieltag",
                format_signed_currency(
                    budget["at_matchday"]
                ),
                [
                    (
                        f"Prognose in "
                        f"{days_to_matchday} Tagen"
                    ),
                    (
                        "Trend Trading: "
                        + format_signed_currency(
                            stats["trend_trading"]
                        )
                        + " pro Tag"
                    ),
                ],
                tone_of(
                    budget["at_matchday"]
                ),
            ),
        ],
        compact,
    )


# ---------------------------------------------------------
# Spielerliste
# ---------------------------------------------------------

st.subheader(
    (
        "Kader"
        if compact
        else f"Kader von {selected_manager_name}"
    )
)

if (
    players
    and stats["lineup_count"]
    != REQUIRED_LINEUP_SIZE
):
    st.warning(
        f"Die Startelf enthält "
        f"{stats['lineup_count']} Spieler "
        f"statt {REQUIRED_LINEUP_SIZE}."
    )

if squad_error:
    st.error(
        "Kader konnte nicht geladen werden: "
        f"{squad_error}"
    )

elif not players:
    st.info("Keine Spieler gefunden.")

else:
    positions = {
        1: "Torwart",
        2: "Abwehr",
        3: "Mittelfeld",
        4: "Sturm",
    }

    player_rows = []

    progress = st.progress(
        0.0,
        text="Spielerpunkte werden geladen …",
    )

    for index, player in enumerate(players):
        try:
            position = positions.get(
                int(
                    first_value(
                        player,
                        ["position", "pos"],
                        0,
                    )
                ),
                "Unbekannt",
            )
        except (TypeError, ValueError):
            position = "Unbekannt"

        player_name = (
            get_short_player_name(player)
            if compact
            else get_player_name(player)
        )

        club_name = get_club_label(
            player,
            teams,
        )

        photo = image_html(
            get_player_photo(player),
            player_name,
            player_photo_size,
            "player-photo",
        )

        club_logo_url = get_player_club_logo(
            player,
            teams,
        )

        club_logo = (
            image_html(
                club_logo_url,
                club_name,
                team_logo_size,
                "team-logo",
            )
            if club_logo_url
            else (
                f"<span>{escape(club_name)}</span>"
                if club_name
                else ""
            )
        )

        total_points, average_points = (
            load_player_points(
                api,
                league_id,
                player,
            )
        )

        team_id = get_team_id(player)

        player_rows.append(
            {
                "Spieler": player_name,
                "_player_html": (
                    "<div class='player-cell'>"
                    f"{photo}"
                    f"{club_logo}"
                    f"<span class='player-name'>"
                    f"{escape(player_name)}"
                    "</span>"
                    "</div>"
                ),
                "Position": position,
                "Status": (
                    "Start 11"
                    if is_in_lineup(player)
                    else "Trading"
                ),
                "Punkte": total_points,
                "_average_points": average_points,
                "Nächste Spiele": (
                    build_next_matches_text(
                        team_id,
                        next_matches,
                        teams,
                    )
                ),
                "_matches_html": (
                    build_next_matches_html(
                        team_id,
                        next_matches,
                        teams,
                        team_logo_size,
                    )
                ),
                "Einstandspreis": (
                    get_buy_price(player)
                ),
                "Marktwert": (
                    get_market_value(player)
                ),
                "Gewinn gesamt": (
                    get_profit(player)
                ),
                "Trend 24 Stunden": (
                    get_daily_change(player)
                ),
            }
        )

        progress.progress(
            (index + 1) / len(players),
            text=(
                "Spielerpunkte werden geladen … "
                f"{index + 1} von {len(players)}"
            ),
        )

    progress.empty()

    player_frame = pd.DataFrame(
        player_rows
    )

    player_columns = [
        "Spieler",
        "Position",
        "Status",
        "Punkte",
        "Nächste Spiele",
        "Einstandspreis",
        "Marktwert",
        "Gewinn gesamt",
        "Trend 24 Stunden",
    ]

    player_frame = sort_frame(
        player_frame,
        player_columns,
        key=(
            f"player_sort_{league_id}_"
            f"{selected_manager_id}"
        ),
        default_column="Gewinn gesamt",
        compact=compact,
    )

    render_squad_table(
        player_frame,
        player_columns,
        compact,
    )

    st.caption(
        "Punkte zeigt die Gesamtpunkte. "
        "In Klammern steht der Durchschnitt."
    )

    st.caption(
        "Die Spielerliste wird über die beiden "
        "Auswahlfelder oberhalb der Tabelle sortiert."
    )


# ---------------------------------------------------------
# Diagnosebereiche
# ---------------------------------------------------------

with st.expander(
    "Alle Daten zu einem Spieler"
):
    if players:
        inspect_index = st.selectbox(
            "Spieler auswählen",
            range(len(players)),
            format_func=lambda index: (
                get_player_name(players[index])
            ),
            key="diagnostic_player",
        )

        inspect_player = players[
            inspect_index
        ]

        total_points, average_points = (
            load_player_points(
                api,
                league_id,
                inspect_player,
            )
        )

        st.markdown(
            "Punkte: "
            + points_cell_html(
                total_points,
                average_points,
            ),
            unsafe_allow_html=True,
        )

        fields = flatten_fields(
            inspect_player
        )

        if fields:
            st.dataframe(
                pd.DataFrame(fields),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

        st.write("**Rohdaten:**")
        st.json(inspect_player)

if not compact:
    with st.expander(
        "Diagnose Vereine und Spielplan"
    ):
        st.write(
            f"Erkannte Vereine: {len(teams)}"
        )

        st.write(
            "Vereine mit nächsten Spielen: "
            f"{len(next_matches)}"
        )

        if st.button(
            "Vereine und Spielplan neu laden",
            key="reload_matches",
        ):
            st.session_state.pop(
                matches_key,
                None,
            )
            st.rerun()

        if teams:
            st.json(teams)

        if next_matches:
            st.json(next_matches)

    with st.expander(
        "Alle Daten zu diesem Manager"
    ):
        st.write(
            f"Ausgewählter Manager: "
            f"{selected_manager_name}"
        )

        if st.button(
            "Manager-Daten laden",
            key="load_manager_diagnostics",
        ):
            try:
                sources, errors = (
                    api.explore_manager(
                        league_id,
                        selected_manager_id,
                    )
                )
            except Exception as error:
                sources = []
                errors = [str(error)]

            st.session_state[
                "manager_diagnostic_sources"
            ] = sources

            st.session_state[
                "manager_diagnostic_errors"
            ] = errors

        diagnostic_sources = (
            st.session_state.get(
                "manager_diagnostic_sources",
                [],
            )
        )

        for index, source in enumerate(
            diagnostic_sources,
            start=1,
        ):
            with st.expander(
                f"Datensatz {index}"
            ):
                st.json(
                    source.get("data")
                )

        diagnostic_errors = (
            st.session_state.get(
                "manager_diagnostic_errors",
                [],
            )
        )

        if diagnostic_errors:
            st.warning(
                "Einige zusätzlichen Daten "
                "konnten nicht geladen werden."
            )
