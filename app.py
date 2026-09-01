"""
Kickbase Liga-Dashboard.

Ansichten:
- Manager
- Liga
- Transfermarkt

Optimiert für Desktop und Handy.
"""

from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

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
    """Formatiert die Gesamtpunkte."""
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


def table_height(row_count, compact=False):
    """Berechnet die Höhe einer Streamlit-Tabelle."""
    row_height = 30 if compact else 35
    header_height = 34 if compact else 38

    return int(header_height + row_count * row_height)


def sort_controls(
    frame,
    columns,
    key,
    default_column,
    compact=False,
):
    """Zeigt Sortierfelder und sortiert die Tabelle."""
    available = [
        column
        for column in columns
        if column in frame.columns
    ]

    if not available:
        return frame.reset_index(drop=True)

    if default_column in available:
        default_index = available.index(default_column)
    else:
        default_index = 0

    if compact:
        left = st.container()
        right = st.container()
    else:
        left, right = st.columns([3, 2])

    sort_column = left.selectbox(
        "Sortieren nach",
        available,
        index=default_index,
        key=f"{key}_spalte",
    )

    direction = right.selectbox(
        "Reihenfolge",
        ["Absteigend", "Aufsteigend"],
        key=f"{key}_richtung",
    )

    return frame.sort_values(
        sort_column,
        ascending=(direction == "Aufsteigend"),
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)


def flatten_fields(value, prefix="", depth=0):
    """Wandelt verschachtelte Daten in eine Tabelle um."""
    rows = []

    if depth > 4:
        return rows

    if isinstance(value, dict):
        for key, nested_value in value.items():
            path = f"{prefix}{key}"

            if isinstance(nested_value, (dict, list)):
                rows.extend(
                    flatten_fields(
                        nested_value,
                        f"{path}.",
                        depth + 1,
                    )
                )
            else:
                number = to_number(nested_value)

                rows.append(
                    {
                        "Feld": path,
                        "Wert": repr(nested_value),
                        "Als Betrag": (
                            format_currency(number)
                            if (
                                number is not None
                                and abs(number) >= 1000
                            )
                            else ""
                        ),
                    }
                )

    elif isinstance(value, list):
        rows.append(
            {
                "Feld": f"{prefix}[Liste]",
                "Wert": f"{len(value)} Einträge",
                "Als Betrag": "",
            }
        )

        if value:
            rows.extend(
                flatten_fields(
                    value[0],
                    f"{prefix}0.",
                    depth + 1,
                )
            )

    return rows


def collect_dictionaries(data, depth=0):
    """Sammelt rekursiv alle Dictionaries."""
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


# ---------------------------------------------------------
# Namen und IDs
# ---------------------------------------------------------

def get_league_id(league):
    """Ermittelt die Liga-ID."""
    value = first_value(
        league,
        ["id", "i", "leagueId", "li"],
        "",
    )

    return str(value) if value is not None else ""


def get_league_name(league):
    """Ermittelt den Ligannamen."""
    return str(
        first_value(
            league,
            ["name", "n", "leagueName", "ln"],
            "Unbekannte Liga",
        )
    )


def get_manager_id(manager):
    """Ermittelt die Manager-ID."""
    value = first_value(
        manager,
        ["id", "i", "userId", "uid", "ui"],
        "",
    )

    return str(value) if value is not None else ""


def get_manager_name(manager):
    """Ermittelt den Managernamen."""
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
    """Ermittelt die Spieler-ID."""
    value = first_value(
        player,
        ["id", "i", "playerId", "pi", "pid"],
    )

    return str(value) if value is not None else None


def get_player_name(player):
    """Ermittelt den Spielernamen."""
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

    single_name = first_value(
        player,
        ["name", "n", "playerName", "pn"],
    )

    if single_name:
        return str(single_name)

    return "Unbekannt"


def get_short_player_name(player):
    """Gibt einen kurzen Spielernamen zurück."""
    last_name = first_value(
        player,
        ["lastName", "ln", "pln"],
    )

    if last_name:
        return str(last_name)

    return get_player_name(player)


# ---------------------------------------------------------
# Eigenen Manager erkennen
# ---------------------------------------------------------

def has_own_manager_marker(manager):
    """Prüft mögliche Kennzeichnungen des eigenen Managers."""
    if not isinstance(manager, dict):
        return False

    possible_keys = [
        "me",
        "isMe",
        "isOwn",
        "own",
        "currentUser",
        "isCurrentUser",
    ]

    for key in possible_keys:
        value = manager.get(key)

        if value is True or value == 1 or value == "1":
            return True

    return False


def resolve_own_manager_id(api, managers):
    """Ermittelt die ID des angemeldeten Managers."""
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


def order_managers_own_first(managers, own_manager_id):
    """Setzt den eigenen Manager an die erste Stelle."""
    if not own_manager_id:
        return managers

    return sorted(
        managers,
        key=lambda manager: (
            0
            if get_manager_id(manager) == str(own_manager_id)
            else 1
        ),
    )


def is_own_manager(own_manager_id, manager_id):
    """Prüft, ob es der eigene Manager ist."""
    if not own_manager_id:
        return False

    return str(own_manager_id) == str(manager_id)


# ---------------------------------------------------------
# Vereins- und Spielerbilder
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
    """Baut eine vollständige Bildadresse."""
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


def looks_like_team(item):
    """Prüft, ob ein Objekt ein Verein sein könnte."""
    if not isinstance(item, dict):
        return False

    player_markers = [
        "mv",
        "marketValue",
        "mvgl",
        "tfhmvt",
        "firstName",
        "pfn",
        "pln",
    ]

    if any(marker in item for marker in player_markers):
        return False

    team_id = first_value(
        item,
        ["id", "i", "tid", "teamId"],
    )

    if team_id is None:
        return False

    if isinstance(team_id, (dict, list, bool)):
        return False

    has_name = bool(
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
    )

    has_image = bool(
        first_text(item, TEAM_IMAGE_KEYS)
    )

    return has_name or has_image


def extract_team_info(sources):
    """Erstellt eine Zuordnung von Vereinen und Logos."""
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
                    [
                        "tabb",
                        "shortName",
                        "sn",
                        "symbol",
                    ],
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

    for source in sources:
        data = source.get("data")

        for item in collect_dictionaries(data):
            team_id = first_value(
                item,
                TEAM_ID_KEYS,
            )

            if team_id is None:
                continue

            if isinstance(team_id, (dict, list, bool)):
                continue

            logo = build_image_url(
                first_text(
                    item,
                    TEAM_IMAGE_KEYS,
                )
            )

            if not logo:
                continue

            entry = teams.setdefault(
                str(team_id),
                {
                    "name": "",
                    "long_name": "",
                    "logo": "",
                },
            )

            if not entry["logo"]:
                entry["logo"] = logo

            if not entry["name"]:
                entry["name"] = first_text(
                    item,
                    TEAM_SHORT_KEYS,
                )

            if not entry["long_name"]:
                entry["long_name"] = first_text(
                    item,
                    TEAM_NAME_KEYS,
                )

    for entry in teams.values():
        if not entry["name"]:
            entry["name"] = entry["long_name"]

    return teams


def get_team_id(player):
    """Ermittelt die Vereins-ID eines Spielers."""
    value = first_value(player, TEAM_ID_KEYS)

    if value is None:
        return None

    if isinstance(value, (dict, list, bool)):
        return None

    return str(value)


def get_team_name(team_id, teams):
    """Gibt den Vereinsnamen zurück."""
    if not team_id:
        return ""

    entry = teams.get(str(team_id))

    if not entry:
        return ""

    return (
        entry.get("name")
        or entry.get("long_name")
        or ""
    )


def get_team_logo(team_id, teams):
    """Gibt die Adresse des Vereinslogos zurück."""
    if not team_id:
        return ""

    entry = teams.get(str(team_id))

    if not entry:
        return ""

    return entry.get("logo", "")


def get_club_label(player, teams=None):
    """Ermittelt eine kurze Vereinsbezeichnung."""
    short_name = first_text(
        player,
        TEAM_SHORT_KEYS,
    )

    if short_name:
        return short_name

    club_name = first_value(
        player,
        TEAM_NAME_KEYS,
    )

    if isinstance(club_name, dict):
        club_name = first_text(
            club_name,
            ["name", "n"],
        )

    if isinstance(club_name, str) and club_name.strip():
        return club_name.strip()

    if teams:
        return get_team_name(
            get_team_id(player),
            teams,
        )

    return ""


def get_player_club_logo(player, teams=None):
    """Ermittelt das Vereinslogo eines Spielers."""
    direct_logo = build_image_url(
        first_text(
            player,
            TEAM_IMAGE_KEYS,
        )
    )

    if direct_logo:
        return direct_logo

    if teams:
        return get_team_logo(
            get_team_id(player),
            teams,
        )

    return ""


def get_player_photo(player):
    """Ermittelt das Bild eines Spielers."""
    return build_image_url(
        first_text(
            player,
            PLAYER_IMAGE_KEYS,
        )
    )


def image_html(
    url,
    label,
    size=TEAM_LOGO_SIZE,
    css_class="team-logo",
):
    """Baut ein kleines HTML-Bild."""
    safe_label = escape(str(label or ""))

    if not url:
        return safe_label

    return (
        f"<img src='{escape(url)}' "
        f"alt='{safe_label}' "
        f"title='{safe_label}' "
        f"class='{css_class}' "
        f"style='height:{size}px;width:{size}px;' />"
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

TOTAL_POINTS_KEYS = [
    "p",
    "pts",
    "points",
    "totalPoints",
    "total_points",
    "seasonPoints",
    "season_points",
    "tp",
]

AVERAGE_POINTS_KEYS = [
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

APPEARANCE_KEYS = [
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

LINEUP_FIELD = "lo"


def get_market_value(player):
    """Liest den Marktwert."""
    return to_number(
        first_value(
            player,
            MARKET_VALUE_KEYS,
        )
    )


def get_profit(player):
    """Liest den Marktwertgewinn."""
    return to_number(
        first_value(
            player,
            PROFIT_KEYS,
        )
    )


def get_buy_price(player):
    """Berechnet den Einstandspreis."""
    market_value = get_market_value(player)
    profit = get_profit(player)

    if market_value is None or profit is None:
        return None

    return market_value - profit


def get_daily_change(player):
    """Liest den Trend der letzten 24 Stunden."""
    return to_number(
        first_value(
            player,
            DAILY_CHANGE_KEYS,
        )
    )


def get_points_from_dictionary(data):
    """Liest Gesamtpunkte und Durchschnitt aus einem Datenblock."""
    if not isinstance(data, dict):
        return None, None

    total_points = to_number(
        first_value(
            data,
            TOTAL_POINTS_KEYS,
        )
    )

    average_points = to_number(
        first_value(
            data,
            AVERAGE_POINTS_KEYS,
        )
    )

    appearances = to_number(
        first_value(
            data,
            APPEARANCE_KEYS,
        )
    )

    if (
        average_points is None
        and total_points is not None
        and appearances is not None
        and appearances > 0
    ):
        average_points = total_points / appearances

    return total_points, average_points


def find_player_points(
    data,
    player_id=None,
    depth=0,
):
    """Sucht Punktedaten in den Spielerdetails."""
    if depth > 8:
        return None, None

    if isinstance(data, dict):
        current_id = first_value(
            data,
            [
                "id",
                "i",
                "playerId",
                "pi",
                "pid",
            ],
        )

        id_matches = (
            player_id is None
            or current_id is None
            or str(current_id) == str(player_id)
        )

        if id_matches:
            total_points, average_points = (
                get_points_from_dictionary(data)
            )

            if (
                total_points is not None
                or average_points is not None
            ):
                return total_points, average_points

        for nested_value in data.values():
            total_points, average_points = (
                find_player_points(
                    nested_value,
                    player_id,
                    depth + 1,
                )
            )

            if (
                total_points is not None
                or average_points is not None
            ):
                return total_points, average_points

    elif isinstance(data, list):
        for item in data:
            total_points, average_points = (
                find_player_points(
                    item,
                    player_id,
                    depth + 1,
                )
            )

            if (
                total_points is not None
                or average_points is not None
            ):
                return total_points, average_points

    return None, None


def load_player_points(
    api,
    league_id,
    player,
):
    """Lädt und speichert die Punkte eines Spielers."""
    player_id = get_player_id(player)

    total_points, average_points = (
        get_points_from_dictionary(player)
    )

    if (
        total_points is not None
        and average_points is not None
    ):
        return total_points, average_points

    if not player_id:
        return total_points, average_points

    cache_key = (
        f"player_points_v2_{league_id}_{player_id}"
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

    loaded_total = total_points
    loaded_average = average_points

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

        if loaded_total is None:
            loaded_total = found_total

        if loaded_average is None:
            loaded_average = found_average

        if (
            loaded_total is not None
            and loaded_average is not None
        ):
            break

    st.session_state[cache_key] = {
        "total": loaded_total,
        "average": loaded_average,
    }

    return loaded_total, loaded_average


def points_cell_html(
    total_points,
    average_points,
):
    """Baut die gemeinsame Punkteanzeige."""
    if to_number(total_points) is None:
        return "—"

    total_text = format_points(total_points)

    if to_number(average_points) is None:
        return total_text

    average_text = format_average_points(
        average_points
    )

    return (
        f"{total_text} "
        "<span class='points-average'>"
        f"({average_text} Ø)"
        "</span>"
    )


def get_lineup_slot(player):
    """Liest einen gültigen Startelfplatz."""
    if not isinstance(player, dict):
        return None

    value = player.get(LINEUP_FIELD)

    if value is None:
        return None

    number = to_number(value)

    if number is None:
        return None

    if 0 <= number <= 10:
        return int(number)

    return None


def is_in_lineup(player):
    """Prüft, ob ein Spieler aufgestellt ist."""
    return get_lineup_slot(player) is not None


def get_lineup_matchday_value(
    stats,
    days_to_matchday,
):
    """Berechnet den prognostizierten S11-Marktwert."""
    return (
        stats["lineup_value"]
        + stats["trend_lineup"]
        * days_to_matchday
    )


# ---------------------------------------------------------
# Spieltag und nächste Spiele
# ---------------------------------------------------------

MATCHDAY_DATE_KEYS = [
    "dt",
    "date",
    "startDate",
    "kickoff",
    "md",
    "mdst",
    "deadline",
]

HOME_TEAM_KEYS = [
    "t1",
    "homeTeamId",
    "home",
    "ht",
]

AWAY_TEAM_KEYS = [
    "t2",
    "awayTeamId",
    "away",
    "at",
]

HOME_IMAGE_KEYS = [
    "t1im",
    "t1i",
    "homeTeamImage",
    "htim",
]

AWAY_IMAGE_KEYS = [
    "t2im",
    "t2i",
    "awayTeamImage",
    "atim",
]

HOME_NAME_KEYS = [
    "t1n",
    "homeTeamName",
    "htn",
]

AWAY_NAME_KEYS = [
    "t2n",
    "awayTeamName",
    "atn",
]

MATCH_DATE_KEYS = [
    "dt",
    "date",
    "kickoff",
    "startDate",
    "md",
]


def parse_date_text(text):
    """Wandelt einen ISO-Datumstext um."""
    if not isinstance(text, str) or len(text) < 8:
        return None

    cleaned = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def parse_any_date(value):
    """Liest ein Datum aus Text oder Zeitstempel."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        parsed = parse_date_text(value)

        if parsed is not None:
            return parsed

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
        return None

    return None


def collect_future_dates(data, depth=0):
    """Sammelt passende zukünftige Datumswerte."""
    found = []

    if depth > 6:
        return found

    now = datetime.now(timezone.utc)

    if isinstance(data, dict):
        for key, value in data.items():
            if key in MATCHDAY_DATE_KEYS:
                parsed = parse_any_date(value)

                if (
                    parsed is not None
                    and parsed > now
                ):
                    found.append(parsed)

            found.extend(
                collect_future_dates(
                    value,
                    depth + 1,
                )
            )

    elif isinstance(data, list):
        for item in data:
            found.extend(
                collect_future_dates(
                    item,
                    depth + 1,
                )
            )

    return found


def find_days_to_matchday(api, league_id):
    """Sucht die verbleibenden Tage bis zum Spieltag."""
    paths = [
        f"/v4/leagues/{league_id}/matchdays",
        f"/v4/leagues/{league_id}/matchday",
        "/v4/competitions/1/matchdays",
        "/v4/competitions/1/matchday",
        "/v4/matchdays",
        f"/v4/leagues/{league_id}/season",
    ]

    now = datetime.now(timezone.utc)

    for path in paths:
        try:
            data = api.get(path)
        except Exception:
            continue

        dates = collect_future_dates(data)

        if not dates:
            continue

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


def extract_matches(match_sources):
    """Sammelt kommende Spiele."""
    matches = []
    seen = set()
    now = datetime.now(timezone.utc)

    for source in match_sources:
        data = source.get("data")

        for item in collect_dictionaries(data):
            home_id = first_value(
                item,
                HOME_TEAM_KEYS,
            )

            away_id = first_value(
                item,
                AWAY_TEAM_KEYS,
            )

            if home_id is None or away_id is None:
                continue

            if isinstance(
                home_id,
                (dict, list, bool),
            ):
                continue

            if isinstance(
                away_id,
                (dict, list, bool),
            ):
                continue

            match_date = None

            for key in MATCH_DATE_KEYS:
                match_date = parse_any_date(
                    item.get(key)
                )

                if match_date is not None:
                    break

            if (
                match_date is None
                or match_date < now
            ):
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
                            HOME_IMAGE_KEYS,
                        )
                    ),
                    "away_logo": build_image_url(
                        first_text(
                            item,
                            AWAY_IMAGE_KEYS,
                        )
                    ),
                    "home_name": first_text(
                        item,
                        HOME_NAME_KEYS,
                    ),
                    "away_name": first_text(
                        item,
                        AWAY_NAME_KEYS,
                    ),
                    "date": match_date,
                }
            )

    return matches


def build_next_matches(matches, count=2):
    """Baut je Verein die nächsten Spiele."""
    by_team = {}

    sorted_matches = sorted(
        matches,
        key=lambda entry: entry["date"],
    )

    for match in sorted_matches:
        home_id = match["home_id"]
        away_id = match["away_id"]
        date_text = match["date"].strftime("%d.%m.")

        by_team.setdefault(
            home_id,
            [],
        ).append(
            {
                "opponent_id": away_id,
                "opponent_logo": match["away_logo"],
                "opponent_name": match["away_name"],
                "place": "H",
                "date": date_text,
            }
        )

        by_team.setdefault(
            away_id,
            [],
        ).append(
            {
                "opponent_id": home_id,
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
    """Lädt Vereinsdaten und Spielplan."""
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
        "competition_sources": competition_sources,
        "team_sources": team_sources,
        "match_sources": match_sources,
    }


def build_next_matches_html(
    team_id,
    next_matches,
    teams,
    logo_size=TEAM_LOGO_SIZE,
):
    """Baut die Spielanzeige mit Vereinslogos."""
    entries = next_matches.get(
        str(team_id or ""),
        [],
    )

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent_id = entry["opponent_id"]

        opponent_logo = (
            entry.get("opponent_logo")
            or get_team_logo(
                opponent_id,
                teams,
            )
        )

        opponent_name = (
            entry.get("opponent_name")
            or get_team_name(
                opponent_id,
                teams,
            )
            or "Gegner"
        )

        logo_html = image_html(
            opponent_logo,
            opponent_name,
            logo_size,
        )

        parts.append(
            "<span class='match-entry'>"
            "<span class='match-place'>"
            f"{entry['place']}"
            "</span>"
            f"{logo_html}"
            "<span class='match-date'>"
            f"{entry['date']}"
            "</span>"
            "</span>"
        )

    return "".join(parts)


def build_next_matches_text(
    team_id,
    next_matches,
    teams,
):
    """Baut einen Text für Sortierung und Fallback."""
    entries = next_matches.get(
        str(team_id or ""),
        [],
    )

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent_name = (
            entry.get("opponent_name")
            or get_team_name(
                entry["opponent_id"],
                teams,
            )
            or entry["opponent_id"]
        )

        parts.append(
            f"{entry['place']} "
            f"{opponent_name} "
            f"{entry['date']}"
        )

    return " · ".join(parts)


# ---------------------------------------------------------
# Listenerkennung
# ---------------------------------------------------------

def looks_like_league(item):
    """Prüft, ob ein Objekt eine Liga sein könnte."""
    if not isinstance(item, dict):
        return False

    has_id = any(
        key in item
        for key in [
            "id",
            "i",
            "leagueId",
            "li",
        ]
    )

    has_name = any(
        key in item
        for key in [
            "name",
            "n",
            "leagueName",
            "ln",
        ]
    )

    return has_id and has_name


def looks_like_manager(item):
    """Prüft, ob ein Objekt ein Manager sein könnte."""
    if not isinstance(item, dict):
        return False

    if not get_manager_id(item):
        return False

    if get_manager_name(item) == "Unbekannter Manager":
        return False

    manager_fields = {
        "unm",
        "userId",
        "uid",
        "ui",
        "teamValue",
        "tv",
        "points",
        "pt",
        "placement",
        "rank",
        "teamName",
        "username",
        "budget",
        "shp",
        "uim",
    }

    return bool(
        manager_fields.intersection(
            item.keys()
        )
    )


def looks_like_player_with_value(item):
    """Prüft, ob ein Objekt ein Spieler sein könnte."""
    return (
        isinstance(item, dict)
        and get_market_value(item) is not None
    )


def find_list(
    value,
    check_function,
    keys,
    depth=0,
):
    """Sucht rekursiv eine passende Liste."""
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
                keys,
                depth + 1,
            )

            if result:
                return result

    elif isinstance(value, dict):
        for key in keys:
            if key in value:
                result = find_list(
                    value[key],
                    check_function,
                    keys,
                    depth + 1,
                )

                if result:
                    return result

        for key, nested_value in value.items():
            if key in [
                "tkn",
                "token",
                "accessToken",
            ]:
                continue

            result = find_list(
                nested_value,
                check_function,
                keys,
                depth + 1,
            )

            if result:
                return result

    return []


def find_leagues(value):
    """Sucht die Ligaliste."""
    return find_list(
        value,
        looks_like_league,
        [
            "leagues",
            "lgs",
            "ls",
            "srvl",
        ],
    )


def find_managers(value):
    """Sucht die Managerliste."""
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


def find_players_with_value(value):
    """Sucht Spieler mit Marktwert."""
    return find_list(
        value,
        looks_like_player_with_value,
        [
            "players",
            "p",
            "it",
            "items",
            "squad",
            "pl",
        ],
    )


# ---------------------------------------------------------
# Transferdaten
# ---------------------------------------------------------

def extract_transfer_events(data, depth=0):
    """Sammelt mögliche Transferereignisse."""
    events = []

    if depth > 6:
        return events

    if isinstance(data, list):
        for item in data:
            events.extend(
                extract_transfer_events(
                    item,
                    depth + 1,
                )
            )

        return events

    if not isinstance(data, dict):
        return events

    player_id = first_value(
        data,
        ["pi", "playerId", "pid", "plid"],
    )

    amount = to_number(
        first_value(
            data,
            ["trp", "price", "pr", "value", "v"],
        )
    )

    buyer = first_value(
        data,
        ["byr", "buyerId", "bid"],
    )

    seller = first_value(
        data,
        ["slr", "sellerId", "sid"],
    )

    if (
        player_id is not None
        and amount is not None
        and (
            buyer is not None
            or seller is not None
        )
    ):
        events.append(
            {
                "player_id": str(player_id),
                "amount": amount,
                "buyer": (
                    str(buyer)
                    if buyer is not None
                    else None
                ),
                "seller": (
                    str(seller)
                    if seller is not None
                    else None
                ),
                "name": get_player_name(data),
            }
        )

    for nested_value in data.values():
        events.extend(
            extract_transfer_events(
                nested_value,
                depth + 1,
            )
        )

    return events


def load_feed_transfers(
    api,
    league_id,
    manager_id,
):
    """Berechnet realisierte Gewinne aus Transfers."""
    events = []
    raw_samples = []

    try:
        sources, _ = api.get_manager_transfers(
            league_id,
            manager_id,
        )

        for source in sources:
            events.extend(
                extract_transfer_events(
                    source["data"]
                )
            )

            if len(raw_samples) < 1:
                raw_samples.append(
                    source["data"]
                )
    except Exception:
        pass

    for start in range(0, 400, 25):
        try:
            sources, _ = api.get_league_feed(
                league_id,
                start,
            )
        except Exception:
            break

        page_events = []

        for source in sources:
            page_events.extend(
                extract_transfer_events(
                    source["data"]
                )
            )

            if start == 0 and len(raw_samples) < 2:
                raw_samples.append(
                    source["data"]
                )

        if not page_events:
            break

        events.extend(page_events)

    purchases = {}
    sales = {}
    names = {}

    for event in events:
        player_id = event["player_id"]

        if event["name"] != "Unbekannt":
            names[player_id] = event["name"]

        if event["buyer"] == str(manager_id):
            purchases.setdefault(
                player_id,
                [],
            ).append(event["amount"])

        if event["seller"] == str(manager_id):
            sales.setdefault(
                player_id,
                [],
            ).append(event["amount"])

    realized = 0.0
    trades = []

    for player_id, sale_prices in sales.items():
        buy_prices = purchases.get(
            player_id,
            [],
        )

        for index, sale_price in enumerate(
            sale_prices
        ):
            if index < len(buy_prices):
                buy_price = buy_prices[index]
                known_price = True
            else:
                buy_price = 0.0
                known_price = False

            profit = sale_price - buy_price
            realized += profit

            trades.append(
                {
                    "Spieler": names.get(
                        player_id,
                        player_id,
                    ),
                    "Kaufpreis": (
                        buy_price
                        if known_price
                        else None
                    ),
                    "Verkaufspreis": sale_price,
                    "Gewinn": profit,
                }
            )

    return realized, trades, raw_samples


# ---------------------------------------------------------
# Kennzahlen und Budget
# ---------------------------------------------------------

def compute_stats(players):
    """Berechnet alle Kennzahlen einer Spielerliste."""
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
        market_value = get_market_value(player) or 0.0
        buy_price = get_buy_price(player) or 0.0
        daily_change = get_daily_change(player) or 0.0
        profit = get_profit(player) or 0.0

        stats["squad_value"] += market_value
        stats["buy_total"] += buy_price
        stats["profit_in_club"] += profit
        stats["trend_total"] += daily_change

        if is_in_lineup(player):
            stats["lineup_value"] += market_value
            stats["buy_lineup"] += buy_price
            stats["trend_lineup"] += daily_change
            stats["lineup_count"] += 1
        else:
            stats["trading_value"] += market_value
            stats["buy_trading"] += buy_price
            stats["trend_trading"] += daily_change
            stats["trading_count"] += 1

    return stats


def compute_budget(
    stats,
    total_profit,
    bonus,
    days_to_matchday,
    real_balance=None,
):
    """Berechnet die Budgetwerte."""
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


def load_manager_players(
    api,
    league_id,
    manager_id,
):
    """Lädt den Kader eines Managers."""
    try:
        squad_result = api.get_manager_squad(
            league_id,
            manager_id,
        )

        players = find_players_with_value(
            squad_result
        )

        return players, None

    except Exception as error:
        return [], str(error)


def load_realized_profit(
    api,
    league_id,
    manager_id,
):
    """Lädt den realisierten Gewinn."""
    try:
        value, _ = api.get_realized_profit(
            league_id,
            manager_id,
        )

        return value
    except Exception:
        return None


def load_real_budget(api, league_id):
    """Lädt das eigene Budget."""
    try:
        value, _ = api.get_budget(league_id)
        return value
    except Exception:
        return None


def compute_own_bonus(
    api,
    league_id,
    own_manager_id,
    real_balance,
):
    """Berechnet einen Bonusvorschlag."""
    if not own_manager_id:
        return None

    if real_balance is None:
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

    plain_balance = (
        BASE_BUDGET
        + total_profit
        - stats["squad_value"]
    )

    return {
        "plain": plain_balance,
        "real": real_balance,
        "bonus": real_balance - plain_balance,
        "profit": total_profit,
        "squad_value": stats["squad_value"],
    }


# ---------------------------------------------------------
# Liga-Tabellenformatierung
# ---------------------------------------------------------

def build_squad_label(
    player_count,
    lineup_count,
):
    """Baut die Anzeige der Kadergröße."""
    total = to_number(player_count)
    lineup = to_number(lineup_count)

    if total is None:
        return "—"

    total_text = str(int(total))

    if lineup is None:
        return total_text

    if int(lineup) == REQUIRED_LINEUP_SIZE:
        return total_text

    return f"{total_text} ({int(lineup)})"


def color_by_value(value):
    """Färbt positive und negative Zahlen."""
    number = to_number(value)

    if number is None or number == 0:
        return ""

    if number > 0:
        return (
            f"color:{COLOR_POSITIVE};"
            "font-weight:600"
        )

    return (
        f"color:{COLOR_NEGATIVE};"
        "font-weight:600"
    )


def apply_value_colors(styled, columns):
    """Färbt Zahlen mit Pandas Styler."""
    if not columns:
        return styled

    if hasattr(styled, "map"):
        return styled.map(
            color_by_value,
            subset=columns,
        )

    return styled.applymap(
        color_by_value,
        subset=columns,
    )


def get_header_background(column):
    """Gibt die Gruppenfarbe eines Spaltenkopfes zurück."""
    trend_columns = {
        "Trend Start 11",
        "Trend Trading",
        "Trend gesamt",
    }

    budget_columns = {
        "Budget",
        "Nach Verkauf",
        "Budget Spieltag",
        "S11 Spieltag",
    }

    if column in trend_columns:
        return LEAGUE_HEADER_TREND

    if column in budget_columns:
        return LEAGUE_HEADER_BUDGET

    return LEAGUE_HEADER_MAIN


def add_grouped_header_styles(styled, frame):
    """Färbt die Spaltenköpfe nach Gruppen."""
    table_styles = []

    for index, column in enumerate(frame.columns):
        table_styles.append(
            {
                "selector": (
                    "th.col_heading.level0."
                    f"col{index}"
                ),
                "props": [
                    (
                        "background-color",
                        get_header_background(
                            column
                        ),
                    ),
                    ("color", "#3f4650"),
                    ("font-weight", "700"),
                ],
            }
        )

    return styled.set_table_styles(
        table_styles,
        overwrite=False,
    )


def style_league_table(
    frame,
    lineup_counts=None,
):
    """Formatiert die Liga-Tabelle."""
    signed_columns = [
        column
        for column in [
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
            "Budget",
            "Nach Verkauf",
            "Budget Spieltag",
        ]
        if column in frame.columns
    ]

    currency_columns = [
        column
        for column in [
            "Start 11",
            "Trading",
            "Kaderwert",
            "S11 Spieltag",
        ]
        if column in frame.columns
    ]

    styled = apply_value_colors(
        frame.style,
        signed_columns,
    )

    styled = add_grouped_header_styles(
        styled,
        frame,
    )

    if (
        lineup_counts is not None
        and "Kader" in frame.columns
    ):

        def color_squad(column):
            styles = []

            for count in lineup_counts:
                number = to_number(count)

                if (
                    number is None
                    or int(number)
                    != REQUIRED_LINEUP_SIZE
                ):
                    styles.append(
                        f"color:{COLOR_NEGATIVE};"
                        "font-weight:700"
                    )
                else:
                    styles.append("")

            return styles

        styled = styled.apply(
            color_squad,
            subset=["Kader"],
        )

    formats = {}

    for column in currency_columns:
        formats[column] = format_currency

    for column in signed_columns:
        formats[column] = format_signed_currency

    return styled.format(formats)


def style_trades_table(frame):
    """Formatiert die Tabelle der Verkäufe."""
    styled = apply_value_colors(
        frame.style,
        ["Gewinn"],
    )

    return styled.format(
        {
            "Kaufpreis": lambda value: (
                "Zulosung"
                if value is None or pd.isna(value)
                else format_currency(value)
            ),
            "Verkaufspreis": format_currency,
            "Gewinn": format_signed_currency,
        }
    )


# ---------------------------------------------------------
# Sortierung der Spielertabelle
# ---------------------------------------------------------

def get_player_sort_state(columns):
    """Liest die aktuelle Spielersortierung."""
    default_column = "Gewinn gesamt"

    try:
        sort_column = st.query_params.get(
            "player_sort",
            default_column,
        )

        sort_direction = st.query_params.get(
            "player_direction",
            "desc",
        )
    except Exception:
        sort_column = default_column
        sort_direction = "desc"

    if sort_column not in columns:
        sort_column = default_column

    if sort_direction not in ["asc", "desc"]:
        sort_direction = "desc"

    return sort_column, sort_direction


def sort_player_frame(frame, columns):
    """Sortiert die Spielertabelle nach dem Spaltenkopf."""
    sort_column, sort_direction = (
        get_player_sort_state(columns)
    )

    if sort_column not in frame.columns:
        return (
            frame.reset_index(drop=True),
            sort_column,
            sort_direction,
        )

    sorted_frame = frame.sort_values(
        sort_column,
        ascending=(sort_direction == "asc"),
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)

    return (
        sorted_frame,
        sort_column,
        sort_direction,
    )


def player_header_link(
    column,
    active_column,
    active_direction,
):
    """Baut einen anklickbaren Spaltenkopf."""
    if column == active_column:
        next_direction = (
            "desc"
            if active_direction == "asc"
            else "asc"
        )

        arrow = (
            " ▲"
            if active_direction == "asc"
            else " ▼"
        )
    else:
        next_direction = "asc"
        arrow = ""

    link = (
        "?player_sort="
        f"{quote(column)}"
        "&player_direction="
        f"{next_direction}"
    )

    safe_column = escape(column)

    return (
        "<th>"
        f"<a class='player-sort-link' "
        f"href='{link}' target='_self' "
        f"title='Nach {safe_column} sortieren'>"
        f"{safe_column}"
        f"<span class='sort-arrow'>{arrow}</span>"
        "</a>"
        "</th>"
    )


# ---------------------------------------------------------
# Kadertabelle
# ---------------------------------------------------------

SQUAD_STYLE = """
<style>
.squad-wrapper {
    overflow-x: auto;
    margin-top: 0.4rem;
    margin-bottom: 0.6rem;
}

.squad-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.86rem;
}

.squad-table th {
    text-align: left;
    color: #8a8a8a;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0;
    border-bottom: 1px solid #e6e6e6;
    white-space: nowrap;
}

.player-sort-link {
    display: block;
    width: 100%;
    box-sizing: border-box;
    padding: 0.5rem 0.55rem;
    color: #737373 !important;
    text-decoration: none !important;
    cursor: pointer;
}

.player-sort-link:hover {
    color: #1c1c1c !important;
    background-color: #f4f5f6;
}

.sort-arrow {
    color: #1c1c1c;
    font-size: 0.64rem;
    letter-spacing: 0;
}

.squad-table td {
    padding: 0.45rem 0.55rem;
    border-bottom: 1px solid #f2f2f2;
    vertical-align: middle;
    white-space: nowrap;
}

.squad-table tr.trading td {
    color: #9a9a9a;
    background-color: #fafafa;
}

.squad-player {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.player-photo {
    object-fit: cover;
    border-radius: 50%;
    background: #f0f0f0;
    flex: 0 0 auto;
}

.team-logo {
    object-fit: contain;
    flex: 0 0 auto;
}

.squad-player-name {
    font-weight: 600;
    color: #1c1c1c;
}

.squad-table tr.trading .squad-player-name {
    color: #9a9a9a;
}

.match-entry {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    margin-right: 0.6rem;
}

.match-place {
    font-weight: 700;
    font-size: 0.7rem;
    color: #888888;
}

.match-date {
    font-size: 0.74rem;
    color: #777777;
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
    white-space: nowrap;
}

.squad-table tr.trading .points-average {
    color: #aaaaaa;
}

.squad-table.mobile {
    min-width: 900px;
    font-size: 0.76rem;
}

.squad-table.mobile th {
    font-size: 0.59rem;
    white-space: normal;
    line-height: 1.2;
}

.squad-table.mobile .player-sort-link {
    padding: 0.35rem 0.3rem;
}

.squad-table.mobile td {
    padding: 0.4rem 0.3rem;
    white-space: normal;
    line-height: 1.25;
}

.squad-table.mobile .squad-player {
    display: grid;
    grid-template-columns: auto auto;
    grid-template-rows: auto auto;
    justify-content: start;
    align-items: center;
    column-gap: 0.3rem;
    row-gap: 0.15rem;
    min-width: 92px;
}

.squad-table.mobile .player-photo {
    grid-column: 1;
    grid-row: 1;
}

.squad-table.mobile .team-logo {
    grid-column: 2;
    grid-row: 1;
}

.squad-table.mobile .squad-player-name {
    grid-column: 1 / 3;
    grid-row: 2;
    white-space: normal;
}

.squad-table.mobile .match-entry {
    display: flex;
    margin-right: 0;
    margin-bottom: 0.15rem;
}

@media (max-width: 640px) {
    .squad-wrapper {
        margin-left: -0.25rem;
        margin-right: -0.25rem;
    }
}
</style>
"""


def signed_cell_html(value):
    """Baut eine gefärbte HTML-Zelle."""
    number = to_number(value)
    text = format_signed_currency(value)

    if number is None or number == 0:
        return text

    css_class = (
        "value-plus"
        if number > 0
        else "value-minus"
    )

    return (
        f"<span class='{css_class}'>"
        f"{text}"
        "</span>"
    )


def render_squad_table(
    frame,
    columns,
    compact=False,
    sort_column="Gewinn gesamt",
    sort_direction="desc",
):
    """Zeichnet die Kadertabelle mit Sortierköpfen."""
    header_cells = "".join(
        player_header_link(
            column,
            sort_column,
            sort_direction,
        )
        for column in columns
    )

    body_rows = []

    for _, row in frame.iterrows():
        row_class = (
            "trading"
            if row.get("Status") == "Trading"
            else ""
        )

        cells = []

        for column in columns:
            if column == "Spieler":
                cells.append(
                    "<td>"
                    "<div class='squad-player'>"
                    f"{row['_spieler_html']}"
                    "</div>"
                    "</td>"
                )

            elif column == "Nächste Spiele":
                cells.append(
                    "<td>"
                    f"{row['_naechste_html']}"
                    "</td>"
                )

            elif column == "Punkte":
                points_html = points_cell_html(
                    row["Punkte"],
                    row["_punkte_durchschnitt"],
                )

                cells.append(
                    "<td>"
                    f"{points_html}"
                    "</td>"
                )

            elif column in [
                "Einstandspreis",
                "Marktwert",
            ]:
                cells.append(
                    "<td>"
                    f"{format_currency(row[column])}"
                    "</td>"
                )

            elif column in [
                "Gewinn gesamt",
                "Trend 24 Stunden",
            ]:
                cells.append(
                    "<td>"
                    f"{signed_cell_html(row[column])}"
                    "</td>"
                )

            else:
                value = row.get(column)

                if value is None or pd.isna(value):
                    value = "—"

                cells.append(
                    "<td>"
                    f"{escape(str(value))}"
                    "</td>"
                )

        row_attribute = (
            f" class='{row_class}'"
            if row_class
            else ""
        )

        body_rows.append(
            f"<tr{row_attribute}>"
            f"{''.join(cells)}"
            "</tr>"
        )

    table_class = (
        "squad-table mobile"
        if compact
        else "squad-table"
    )

    table_html = (
        "<div class='squad-wrapper'>"
        f"<table class='{table_class}'>"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )

    st.markdown(
        table_html,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# KPI-Blöcke
# ---------------------------------------------------------

def kpi_block(
    title,
    entries,
    compact=False,
):
    """Zeigt einen KPI-Block mit Zusatzinformationen."""
    colors = {
        "neutral": COLOR_NEUTRAL,
        "plus": COLOR_POSITIVE,
        "minus": COLOR_NEGATIVE,
    }

    value_size = 19 if compact else 24

    st.markdown(
        f"<div class='kpi-title' "
        f"style='"
        f"border-top:1px solid {COLOR_LINE};"
        f"padding-top:10px;"
        f"margin-top:18px;"
        f"font-size:12px;"
        f"font-weight:500;"
        f"letter-spacing:0.08em;"
        f"text-transform:uppercase;"
        f"color:{COLOR_LABEL};"
        f"'>"
        f"{title}"
        f"</div>",
        unsafe_allow_html=True,
    )

    columns = st.columns(len(entries))

    for column, entry in zip(columns, entries):
        label, value, notes, tone = entry
        color = colors.get(tone, COLOR_NEUTRAL)
        notes_html = ""

        for note in notes:
            if not note:
                continue

            notes_html += (
                "<div class='kpi-note' "
                f"style='"
                f"font-size:12px;"
                f"color:{COLOR_LABEL};"
                f"line-height:1.5;"
                f"'>"
                f"{escape(str(note))}"
                "</div>"
            )

        column.markdown(
            "<div class='kpi-card' "
            "style='padding:6px 0 2px 0;'>"
            "<div style='"
            "font-size:12px;"
            f"color:{COLOR_LABEL};"
            "'>"
            f"{label}"
            "</div>"
            "<div class='kpi-value' "
            "style='"
            f"font-size:{value_size}px;"
            "font-weight:700;"
            f"color:{color};"
            "padding:2px 0 4px 0;"
            "'>"
            f"{value}"
            "</div>"
            f"{notes_html}"
            "</div>",
            unsafe_allow_html=True,
        )


def tone_of(value):
    """Bestimmt die Farbe anhand des Vorzeichens."""
    number = to_number(value)

    if number is None or number == 0:
        return "neutral"

    return "plus" if number > 0 else "minus"


# ---------------------------------------------------------
# Seiteneinstellungen und CSS
# ---------------------------------------------------------

st.set_page_config(
    page_title="Kickbase Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .login-heading {
        text-align: center;
        margin-top: 3rem;
        margin-bottom: 0.25rem;
        font-size: 2rem;
        font-weight: 750;
        color: #1c1c1c;
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
        font-size: 0.85rem;
        line-height: 1.45;
        margin-top: 0.8rem;
    }

    .top-nav-label {
        color: #8a8a8a;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0.25rem 0 0.35rem 0;
    }

    section[data-testid="stSidebar"]
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
    }

    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 2.1rem !important;
        }

        h1 {
            font-size: 1.35rem !important;
        }

        h2,
        h3 {
            font-size: 1.05rem !important;
        }

        .login-heading {
            margin-top: 1.2rem;
            font-size: 1.55rem;
        }

        .kpi-value {
            font-size: 16px !important;
            white-space: nowrap;
        }

        .kpi-note {
            font-size: 10px !important;
        }

        .kpi-card {
            padding-left: 2px !important;
            padding-right: 2px !important;
        }

        .kpi-title {
            margin-top: 12px !important;
        }

        div[data-testid="stDataFrame"] {
            font-size: 12px !important;
        }

        .stCaption,
        div[data-testid="stCaptionContainer"] {
            font-size: 11px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    SQUAD_STYLE,
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
                placeholder="name@beispiel.de",
            )

            password = st.text_input(
                "Kickbase-Passwort",
                type="password",
                placeholder="Passwort",
            )

            login_clicked = (
                st.form_submit_button(
                    "Einloggen",
                    type="primary",
                    use_container_width=True,
                )
            )

        st.markdown(
            """
            <div class="login-security">
                🔒 Dein Passwort wird nicht gespeichert.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if login_clicked:
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

                        login_result = api.login(
                            email,
                            password,
                        )

                        leagues = find_leagues(
                            login_result
                        )

                    if not leagues:
                        st.error(
                            "Login erfolgreich, aber "
                            "es wurde keine Liga erkannt."
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
    help=(
        "Zeigt die Kaderdaten kompakter "
        "und teilweise zweizeilig."
    ),
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
    help=(
        "Zeigt zusätzlich bereits "
        "verkaufte Spieler und deren Gewinne."
    ),
)

kpis_expanded = st.sidebar.checkbox(
    "Kennzahlen aufgeklappt starten",
    value=False,
)


# ---------------------------------------------------------
# Vereine und Spielplan
# ---------------------------------------------------------

matches_key = f"team_matches_v7_{league_id}"

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
    with st.spinner("Budget wird geladen …"):
        st.session_state[budget_key] = (
            load_real_budget(
                api,
                league_id,
            )
        )

own_budget = st.session_state[budget_key]

matchday_key = f"matchday_days_{league_id}"

if matchday_key not in st.session_state:
    with st.spinner("Spieltag wird gesucht …"):
        st.session_state[matchday_key] = (
            find_days_to_matchday(
                api,
                league_id,
            )
        )

found_days = st.session_state[matchday_key]

if found_days is None:
    default_days = 3
    days_hint = (
        "Kein Termin konnte automatisch "
        "ermittelt werden. Bitte den Wert "
        "manuell einstellen."
    )
else:
    default_days = int(found_days)
    days_hint = (
        "Der nächste Spieltag wurde "
        "automatisch berücksichtigt."
    )

days_widget_key = (
    f"days_to_matchday_{league_id}"
)

if days_widget_key not in st.session_state:
    st.session_state[days_widget_key] = (
        default_days
    )

days_to_matchday = st.sidebar.number_input(
    "Tage bis zum Spieltag",
    min_value=0,
    max_value=30,
    step=1,
    key=days_widget_key,
    help=(
        "Dieser Wert wird für die "
        "Budget- und S11-Prognose verwendet."
    ),
)

st.sidebar.caption(days_hint)


# ---------------------------------------------------------
# Titel und Navigation
# ---------------------------------------------------------

if compact:
    st.markdown(
        f"<div style='"
        f"font-size:15px;"
        f"font-weight:650;"
        f"padding-bottom:5px;'>"
        f"⚽ {escape(league_name)}"
        f"</div>",
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
        st.session_state["came_from_league"] = False
        st.rerun()

with league_nav:
    if st.button(
        "🏆 Liga",
        key="nav_liga",
        type=(
            "primary"
            if st.session_state["view"] == "Liga"
            else "secondary"
        ),
        use_container_width=True,
    ):
        st.session_state["view"] = "Liga"
        st.session_state["came_from_league"] = False
        st.rerun()

with market_nav:
    if st.button(
        "🛒 Transfermarkt",
        key="nav_transfermarkt",
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
        st.session_state["view"] = "Transfermarkt"
        st.session_state["came_from_league"] = False
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
# Managerliste
# ---------------------------------------------------------

managers = []

with st.spinner("Manager werden geladen …"):
    ranking_sources, ranking_errors = (
        api.get_ranking(league_id)
    )

for source in ranking_sources:
    found = find_managers(source["data"])

    if found:
        managers = found
        break

if not managers:
    st.error(
        "Es konnten keine Manager geladen werden."
    )

    if ranking_errors:
        with st.expander("Fehlerdetails"):
            st.write(ranking_errors)

    if st.button("Neu anmelden"):
        st.session_state.clear()
        st.rerun()

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
    "Grundwert fest: "
    f"{format_currency(BASE_BUDGET)}"
)

bonus_info_key = (
    f"own_bonus_info_{league_id}"
)

bonus_widget_key = (
    f"bonus_mio_{league_id}"
)

if st.sidebar.button(
    "Bonus neu berechnen",
    use_container_width=True,
):
    st.session_state.pop(
        bonus_info_key,
        None,
    )

    st.session_state.pop(
        bonus_widget_key,
        None,
    )

    st.session_state.pop(
        budget_key,
        None,
    )

    st.session_state.pop(
    f"league_rows_v15_{league_id}",
    None,
    )

    st.rerun()

if bonus_info_key not in st.session_state:
    with st.spinner("Bonus wird ermittelt …"):
        st.session_state[bonus_info_key] = (
            compute_own_bonus(
                api,
                league_id,
                own_manager_id,
                own_budget,
            )
        )

own_bonus_info = st.session_state[
    bonus_info_key
]

if own_bonus_info is not None:
    suggested_bonus = (
        own_bonus_info["bonus"] / 1_000_000
    )

    bonus_hint = (
        "Vorschlag aus der Differenz "
        "zwischen berechnetem und "
        "tatsächlichem Budget."
    )
else:
    suggested_bonus = 0.0

    bonus_hint = (
        "Der Bonus konnte nicht automatisch "
        "ermittelt werden. Du kannst ihn "
        "manuell eintragen."
    )

if bonus_widget_key not in st.session_state:
    st.session_state[bonus_widget_key] = round(
        float(suggested_bonus),
        2,
    )

bonus_mio = st.sidebar.number_input(
    "Bonus in Mio. €",
    min_value=-200.0,
    max_value=500.0,
    step=0.5,
    key=bonus_widget_key,
    help=(
        "Dieser Bonus wird für die "
        "Schätzung fremder Manager verwendet."
    ),
)

bonus = bonus_mio * 1_000_000

st.sidebar.caption(bonus_hint)

if own_bonus_info is not None:
    st.sidebar.caption(
        "Eigene Berechnung ohne Bonus: "
        + format_currency(
            own_bonus_info["plain"]
        )
    )

    st.sidebar.caption(
        "Eigenes Budget: "
        + format_currency(
            own_bonus_info["real"]
        )
    )

    st.sidebar.caption(
        "Differenz als Bonus: "
        + format_signed_currency(
            own_bonus_info["bonus"]
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
# Liga-Ansicht
# ---------------------------------------------------------

def get_manager_points(manager):
    """Liest die Gesamtpunkte eines Managers aus der Ligawertung."""
    return to_number(
        first_value(
            manager,
            [
                "shp",
                "points",
                "pt",
                "pts",
                "totalPoints",
                "total_points",
                "seasonPoints",
                "season_points",
                "score",
                "scorePoints",
                "sp",
                "spt",
                "tp",
                "p",
            ],
        )
    )

def league_header_class(column):
    """Bestimmt die Farbgruppe eines Spaltenkopfes."""
    trend_columns = {
        "Trend Start 11",
        "Trend Trading",
        "Trend gesamt",
    }

    budget_columns = {
        "Budget",
        "Nach Verkauf",
        "Budget Spieltag",
        "S11 Spieltag",
    }

    if column in trend_columns:
        return "league-header-trend"

    if column in budget_columns:
        return "league-header-budget"

    return "league-header-main"


def format_league_value(column, value):
    """Formatiert einen Wert der Ligaübersicht."""
    if column == "Punkte":
        return format_points(value)

    if column in [
        "Start 11",
        "Trading",
        "Kaderwert",
        "S11 Spieltag",
    ]:
        return format_currency(value)

    if column in [
        "Gewinn gesamt",
        "Trend Start 11",
        "Trend Trading",
        "Trend gesamt",
        "Budget",
        "Nach Verkauf",
        "Budget Spieltag",
    ]:
        return format_signed_currency(value)

    if value is None:
        return "—"

    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass

    return str(value)


def league_value_html(column, value):
    """Färbt positive und negative Liga-Werte."""
    text = format_league_value(
        column,
        value,
    )

    colored_columns = {
        "Gewinn gesamt",
        "Trend Start 11",
        "Trend Trading",
        "Trend gesamt",
        "Budget",
        "Nach Verkauf",
        "Budget Spieltag",
    }

    if column not in colored_columns:
        return escape(text)

    number = to_number(value)

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


def build_manager_link(
    manager_id,
    manager_name,
    viewing_own_manager=False,
):
    """Baut einen anklickbaren Managernamen."""
    display_name = (
        f"● {manager_name}"
        if viewing_own_manager
        else manager_name
    )

    link = (
        "?open_manager="
        f"{quote(str(manager_id))}"
    )

    return (
        f"<a class='league-manager-link' "
        f"href='{link}' target='_self'>"
        f"{escape(display_name)}"
        "</a>"
    )


def render_league_table(
    frame,
    manager_ids,
    own_flags,
    lineup_counts,
    columns,
    compact=False,
):
    """Zeigt die Ligaübersicht mit farbigen Spaltenköpfen."""
    header_cells = []

    for column in columns:
        css_class = league_header_class(
            column
        )

        header_cells.append(
            f"<th class='{css_class}'>"
            f"{escape(column)}"
            "</th>"
        )

    body_rows = []

    for row_index, (_, row) in enumerate(
        frame.iterrows()
    ):
        cells = []

        manager_id = manager_ids[row_index]
        own = own_flags[row_index]
        lineup_count = lineup_counts[row_index]

        for column in columns:
            if column == "Manager":
                manager_html = build_manager_link(
                    manager_id,
                    str(row[column]),
                    own,
                )

                cells.append(
                    "<td class='league-manager-cell'>"
                    f"{manager_html}"
                    "</td>"
                )

            elif column == "Kader":
                lineup_number = to_number(
                    lineup_count
                )

                invalid_lineup = (
                    lineup_number is None
                    or int(lineup_number)
                    != REQUIRED_LINEUP_SIZE
                )

                css_class = (
                    "league-squad-warning"
                    if invalid_lineup
                    else ""
                )

                cells.append(
                    f"<td class='{css_class}'>"
                    f"{escape(str(row[column]))}"
                    "</td>"
                )

            else:
                cells.append(
                    "<td>"
                    f"{league_value_html(column, row[column])}"
                    "</td>"
                )

        body_rows.append(
            "<tr>"
            f"{''.join(cells)}"
            "</tr>"
        )

    table_class = (
        "league-table mobile"
        if compact
        else "league-table"
    )

    table_html = (
        "<div class='league-wrapper'>"
        f"<table class='{table_class}'>"
        "<thead>"
        "<tr>"
        f"{''.join(header_cells)}"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{''.join(body_rows)}"
        "</tbody>"
        "</table>"
        "</div>"
    )

    st.markdown(
        table_html,
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    .league-wrapper {
        width: 100%;
        overflow-x: auto;
        margin-top: 0.5rem;
        margin-bottom: 0.7rem;
        border: 1px solid #e6e6e6;
        border-radius: 8px;
    }

    .league-table {
        width: 100%;
        min-width: 1380px;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 0.82rem;
    }

    .league-table.mobile {
        min-width: 1040px;
        font-size: 0.74rem;
    }

    .league-table th {
        padding: 0.65rem 0.6rem;
        border-right: 1px solid rgba(0, 0, 0, 0.05);
        border-bottom: 1px solid #dedede;
        color: #3f4650;
        font-size: 0.7rem;
        font-weight: 700;
        text-align: left;
        text-transform: uppercase;
        letter-spacing: 0.035em;
        white-space: nowrap;
        position: sticky;
        top: 0;
        z-index: 2;
    }

    .league-table.mobile th {
        padding: 0.5rem 0.4rem;
        font-size: 0.62rem;
        white-space: normal;
        line-height: 1.2;
    }

    .league-header-main {
        background-color: #f2f4f7;
    }

    .league-header-trend {
        background-color: #eaf6ef;
    }

    .league-header-budget {
        background-color: #fff3e3;
    }

    .league-table td {
        padding: 0.58rem 0.6rem;
        border-right: 1px solid #f1f1f1;
        border-bottom: 1px solid #eeeeee;
        background-color: #ffffff;
        vertical-align: middle;
        white-space: nowrap;
    }

    .league-table.mobile td {
        padding: 0.48rem 0.4rem;
    }

    .league-table tbody tr:hover td {
        background-color: #fafafa;
    }

    .league-table th:last-child,
    .league-table td:last-child {
        border-right: none;
    }

    .league-table tbody tr:last-child td {
        border-bottom: none;
    }

    .league-manager-cell {
        font-weight: 700;
    }

    .league-manager-link {
        color: #1c1c1c !important;
        text-decoration: none !important;
        font-weight: 700;
    }

    .league-manager-link:hover {
        color: #1264a3 !important;
        text-decoration: underline !important;
    }

    .league-squad-warning {
        color: #e03131 !important;
        font-weight: 700;
    }

    @media (max-width: 640px) {
        .league-wrapper {
            margin-left: -0.25rem;
            margin-right: -0.25rem;
            width: calc(100% + 0.5rem);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


open_manager_id = None

try:
    open_manager_id = st.query_params.get(
        "open_manager"
    )
except Exception:
    open_manager_id = None

if (
    open_manager_id
    and str(open_manager_id) in manager_ids
):
    manager_selection_key = (
        f"manager_selection_{league_id}"
    )

    st.session_state[
        manager_selection_key
    ] = str(open_manager_id)

    st.session_state["view"] = "Manager"
    st.session_state[
        "came_from_league"
    ] = True

    try:
        del st.query_params["open_manager"]
    except Exception:
        pass

    st.rerun()


if view == "Liga":
    st.subheader("Liga-Vergleich")

    if not compact:
        st.caption(
            "Klicke auf einen Managernamen, um "
            "dessen Kader und Kennzahlen zu öffnen."
        )

    cache_key = (
        f"league_rows_v15_{league_id}"
    )

    if st.button(
        "Daten neu laden",
        key="reload_league_data",
    ):
        st.session_state.pop(
            cache_key,
            None,
        )

        st.rerun()

    if cache_key not in st.session_state:
        rows = []

        progress = st.progress(
            0.0,
            text="Kader werden geladen …",
        )

        for index, manager in enumerate(
            managers
        ):
            manager_id = get_manager_id(
                manager
            )

            manager_name = get_manager_name(
                manager
            )

            manager_points = (
                get_manager_points(
                    manager
                )
            )

            manager_players, _ = (
                load_manager_players(
                    api,
                    league_id,
                    manager_id,
                )
            )

            manager_stats = compute_stats(
                manager_players
            )

            manager_lineup_matchday_value = (
                get_lineup_matchday_value(
                    manager_stats,
                    days_to_matchday,
                )
            )

            realized = load_realized_profit(
                api,
                league_id,
                manager_id,
            )

            rows.append(
                {
                    "Manager-ID": manager_id,
                    "Manager": manager_name,
                    "Ich": is_own_manager(
                        own_manager_id,
                        manager_id,
                    ),
                    "Startelf-Anzahl": (
                        manager_stats[
                            "lineup_count"
                        ]
                    ),
                    "Kader": (
                        manager_stats[
                            "player_count"
                        ]
                    ),
                    "Punkte": manager_points,
                    "Start 11": (
                        manager_stats[
                            "lineup_value"
                        ]
                    ),
                    "Trading": (
                        manager_stats[
                            "trading_value"
                        ]
                    ),
                    "Kaderwert": (
                        manager_stats[
                            "squad_value"
                        ]
                    ),
                    "Gewinn gesamt": (
                        manager_stats[
                            "profit_in_club"
                        ]
                        + (realized or 0.0)
                    ),
                    "Trend Start 11": (
                        manager_stats[
                            "trend_lineup"
                        ]
                    ),
                    "Trend Trading": (
                        manager_stats[
                            "trend_trading"
                        ]
                    ),
                    "Trend gesamt": (
                        manager_stats[
                            "trend_total"
                        ]
                    ),
                    "S11 Spieltag": (
                        manager_lineup_matchday_value
                    ),
                }
            )

            progress.progress(
                (
                    index + 1
                )
                / len(managers),
                text=(
                    "Kader werden geladen … "
                    f"{index + 1} von "
                    f"{len(managers)}"
                ),
            )

        progress.empty()

        st.session_state[
            cache_key
        ] = rows

    league_frame = pd.DataFrame(
        st.session_state[cache_key]
    )

    league_frame["Budget"] = (
        BASE_BUDGET
        + bonus
        + league_frame[
            "Gewinn gesamt"
        ]
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
        + league_frame[
            "Trend Trading"
        ]
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

    sortable_frame = league_frame[
        [
            "Manager-ID",
            "Ich",
            "Startelf-Anzahl",
            *visible_columns,
        ]
    ].copy()

    sortable_frame = sort_controls(
        sortable_frame,
        visible_columns,
        key="liga",
        default_column="Punkte",
        compact=compact,
    )

    sorted_manager_ids = (
        sortable_frame[
            "Manager-ID"
        ].astype(str).tolist()
    )

    sorted_own_flags = (
        sortable_frame[
            "Ich"
        ].tolist()
    )

    lineup_counts = (
        sortable_frame[
            "Startelf-Anzahl"
        ].tolist()
    )

    display_frame = sortable_frame.drop(
        columns=[
            "Manager-ID",
            "Ich",
            "Startelf-Anzahl",
        ]
    )

    display_frame["Kader"] = [
        build_squad_label(
            total,
            lineup,
        )
        for total, lineup in zip(
            display_frame["Kader"],
            lineup_counts,
        )
    ]

    render_league_table(
        display_frame,
        sorted_manager_ids,
        sorted_own_flags,
        lineup_counts,
        visible_columns,
        compact=compact,
    )

    st.caption(
        "Punkte zeigt die Gesamtpunkte des "
        "Managers aus der Ligawertung."
    )

    st.caption(
        "Die hellgrauen Spaltenköpfe enthalten "
        "die allgemeinen Mannschaftswerte. "
        "Die hellgrünen Spaltenköpfe enthalten "
        "die Trends. Die hellorangenen "
        "Spaltenköpfe enthalten die Budget- "
        "und Spieltagsprognosen."
    )

    st.caption(
        "Kader zeigt die Gesamtzahl der Spieler. "
        "Wenn die Startelf nicht genau 11 Spieler "
        "enthält, wird ihre Anzahl in Klammern "
        "ergänzt und rot markiert."
    )

    st.caption(
        "S11 Spieltag zeigt den voraussichtlichen "
        "Marktwert der aktuellen Startelf am "
        "nächsten Spieltag."
    )

    if own_budget is not None:
        st.caption(
            "Beim eigenen Manager wird das "
            "tatsächliche Budget verwendet. "
            "Die anderen Budgets werden mit "
            f"{format_currency(BASE_BUDGET)} "
            "Grundwert, "
            f"{format_currency(bonus)} Bonus und "
            f"{days_to_matchday} Tagen bis zum "
            "Spieltag geschätzt."
        )
    else:
        st.caption(
            "Die Budgets werden mit "
            f"{format_currency(BASE_BUDGET)} "
            "Grundwert, "
            f"{format_currency(bonus)} Bonus und "
            f"{days_to_matchday} Tagen bis zum "
            "Spieltag geschätzt."
        )

    st.stop()

# ---------------------------------------------------------
# Manager-Ansicht
# ---------------------------------------------------------

if st.session_state.get("came_from_league"):
    if st.button("← Zurück zur Liga-Übersicht"):
        st.session_state[
            "came_from_league"
        ] = False

        st.session_state["view"] = "Liga"
        st.rerun()

selection_key = (
    f"manager_selection_{league_id}"
)

if selection_key not in st.session_state:
    if own_manager_id in manager_ids:
        st.session_state[
            selection_key
        ] = own_manager_id
    else:
        st.session_state[
            selection_key
        ] = manager_ids[0]

if st.session_state[selection_key] not in manager_ids:
    if own_manager_id in manager_ids:
        st.session_state[
            selection_key
        ] = own_manager_id
    else:
        st.session_state[
            selection_key
        ] = manager_ids[0]

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

selected_manager = manager_lookup[
    selected_manager_id
]

selected_manager_name = get_manager_name(
    selected_manager
)

viewing_self = is_own_manager(
    own_manager_id,
    selected_manager_id,
)


# ---------------------------------------------------------
# Kader und Gewinne
# ---------------------------------------------------------

with st.spinner("Kader wird geladen …"):
    players, squad_error = (
        load_manager_players(
            api,
            league_id,
            selected_manager_id,
        )
    )

realized_profit = None
realized_trades = []
feed_samples = []

if show_realized and players:
    with st.spinner(
        "Transferhistorie wird geladen …"
    ):
        (
            feed_profit,
            realized_trades,
            feed_samples,
        ) = load_feed_transfers(
            api,
            league_id,
            selected_manager_id,
        )

        realized_profit = feed_profit

if players:
    direct_profit = load_realized_profit(
        api,
        league_id,
        selected_manager_id,
    )

    if direct_profit is not None:
        realized_profit = direct_profit


# ---------------------------------------------------------
# Manager-Kennzahlen
# ---------------------------------------------------------

stats = compute_stats(players)

lineup_matchday_value = (
    get_lineup_matchday_value(
        stats,
        days_to_matchday,
    )
)

total_profit = stats["profit_in_club"]

if realized_profit is not None:
    total_profit += realized_profit

real_balance = (
    own_budget
    if viewing_self
    else None
)

budget = compute_budget(
    stats,
    total_profit,
    bonus,
    days_to_matchday,
    real_balance=real_balance,
)

open_kpis = (
    kpis_expanded
    or st.session_state.get(
        "came_from_league",
        False,
    )
)

title_marker = " ●" if viewing_self else ""

with st.expander(
    (
        f"Kennzahlen: "
        f"{selected_manager_name}"
        f"{title_marker}"
    ),
    expanded=open_kpis,
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
                            lineup_matchday_value
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
        compact=compact,
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
        compact=compact,
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
        compact=compact,
    )

    budget_title = (
        "Budget"
        if viewing_self
        else "Budget geschätzt"
    )

    kpi_block(
        budget_title,
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
        compact=compact,
    )

    st.markdown("")


# ---------------------------------------------------------
# Kadertabelle mit Punkten
# ---------------------------------------------------------

if compact:
    st.subheader("Kader")
else:
    st.subheader(
        f"Kader von {selected_manager_name}"
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

elif players:
    positions = {
        1: "Torwart",
        2: "Abwehr",
        3: "Mittelfeld",
        4: "Sturm",
    }

    player_rows = []

    points_progress = st.progress(
        0.0,
        text="Spielerpunkte werden geladen …",
    )

    for player_index, player in enumerate(
        players
    ):
        position = first_value(
            player,
            ["position", "pos"],
        )

        try:
            position_name = positions.get(
                int(position),
                "Unbekannt",
            )
        except (TypeError, ValueError):
            position_name = "Unbekannt"

        status = (
            "Start 11"
            if is_in_lineup(player)
            else "Trading"
        )

        team_id = get_team_id(player)

        club_label = get_club_label(
            player,
            teams,
        )

        club_logo = get_player_club_logo(
            player,
            teams,
        )

        player_photo = get_player_photo(player)

        (
            player_total_points,
            player_average_points,
        ) = load_player_points(
            api,
            league_id,
            player,
        )

        if compact:
            player_name = get_short_player_name(
                player
            )
        else:
            player_name = get_player_name(player)

        photo_html = ""

        if player_photo:
            photo_html = image_html(
                player_photo,
                player_name,
                player_photo_size,
                "player-photo",
            )

        club_logo_html = ""

        if club_logo:
            club_logo_html = image_html(
                club_logo,
                club_label,
                team_logo_size,
            )
        elif club_label:
            club_logo_html = (
                "<span class='match-place'>"
                f"{escape(club_label)}"
                "</span>"
            )

        player_html = (
            f"{photo_html}"
            f"{club_logo_html}"
            "<span class='squad-player-name'>"
            f"{escape(player_name)}"
            "</span>"
        )

        player_rows.append(
            {
                "Spieler": player_name,
                "_spieler_html": player_html,
                "Position": position_name,
                "Status": status,
                "Punkte": player_total_points,
                "_punkte_durchschnitt": (
                    player_average_points
                ),
                "Nächste Spiele": (
                    build_next_matches_text(
                        team_id,
                        next_matches,
                        teams,
                    )
                ),
                "_naechste_html": (
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

        points_progress.progress(
            (player_index + 1) / len(players),
            text=(
                "Spielerpunkte werden geladen … "
                f"{player_index + 1} von "
                f"{len(players)}"
            ),
        )

    points_progress.empty()

    player_frame = pd.DataFrame(player_rows)

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

    (
        player_frame,
        player_sort_column,
        player_sort_direction,
    ) = sort_player_frame(
        player_frame,
        player_columns,
    )

    render_squad_table(
        player_frame,
        player_columns,
        compact=compact,
        sort_column=player_sort_column,
        sort_direction=player_sort_direction,
    )

    st.caption(
        "Punkte zeigt zuerst die Gesamtpunkte. "
        "Der Wert in Klammern ist der "
        "durchschnittliche Punktwert pro Einsatz."
    )

    st.caption(
        "Klicke auf einen Spaltenkopf, um die "
        "Spieler zu sortieren. Ein weiterer Klick "
        "kehrt die Reihenfolge um."
    )

    st.caption(
        "Beim Spieler stehen Spielerbild "
        "und Vereinslogo. H bedeutet Heimspiel "
        "und A bedeutet Auswärtsspiel."
    )

else:
    st.info("Keine Spieler gefunden.")


# ---------------------------------------------------------
# Verkaufte Spieler
# ---------------------------------------------------------

if realized_trades:
    st.subheader("Verkaufte Spieler")

    trades_frame = pd.DataFrame(
        realized_trades
    )

    trades_frame = sort_controls(
        trades_frame,
        [
            "Spieler",
            "Kaufpreis",
            "Verkaufspreis",
            "Gewinn",
        ],
        key="verkaeufe",
        default_column="Gewinn",
        compact=compact,
    )

    st.dataframe(
        style_trades_table(trades_frame),
        use_container_width=True,
        hide_index=True,
        height=table_height(
            len(trades_frame),
            compact,
        ),
    )


# ---------------------------------------------------------
# Spielerdiagnose
# ---------------------------------------------------------

with st.expander("Alle Daten zu einem Spieler"):
    if players:
        inspect_index = st.selectbox(
            "Spieler auswählen",
            range(len(players)),
            format_func=lambda index: (
                get_player_name(players[index])
            ),
        )

        inspect_player = players[inspect_index]

        inspect_total, inspect_average = (
            load_player_points(
                api,
                league_id,
                inspect_player,
            )
        )

        st.write(
            "Punkte: "
            + points_cell_html(
                inspect_total,
                inspect_average,
            ),
            unsafe_allow_html=True,
        )

        st.write(
            "Verein: "
            + (
                get_club_label(
                    inspect_player,
                    teams,
                )
                or "nicht erkannt"
            )
        )

        st.write(
            "Spielerbild: "
            + (
                "vorhanden"
                if get_player_photo(
                    inspect_player
                )
                else "nicht vorhanden"
            )
        )

        st.write(
            "Vereinslogo: "
            + (
                "vorhanden"
                if get_player_club_logo(
                    inspect_player,
                    teams,
                )
                else "nicht vorhanden"
            )
        )

        squad_fields = flatten_fields(
            inspect_player
        )

        if squad_fields:
            st.dataframe(
                pd.DataFrame(squad_fields),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

        st.write("**Rohdaten:**")
        st.json(inspect_player)

    else:
        st.info(
            "Keine Spielerdaten vorhanden."
        )


# ---------------------------------------------------------
# Weitere Diagnosebereiche
# ---------------------------------------------------------

if not compact:
    with st.expander(
        "Diagnose Vereine und Spielplan"
    ):
        st.write(
            f"Erkannte Vereine: {len(teams)}"
        )

        logo_count = sum(
            1
            for entry in teams.values()
            if entry.get("logo")
        )

        st.write(
            f"Vereine mit Logo: {logo_count}"
        )

        st.write(
            "Vereine mit nächsten Spielen: "
            f"{len(next_matches)}"
        )

        if st.button(
            "Vereine und Spielplan neu laden"
        ):
            st.session_state.pop(
                matches_key,
                None,
            )
            st.rerun()

        if teams:
            st.write("**Erkannte Vereine:**")
            st.json(teams)

        if next_matches:
            st.write("**Nächste Spiele:**")
            st.json(next_matches)

        diagnostic_sets = (
            matches_info["competition_sources"]
            + matches_info["team_sources"]
            + matches_info["match_sources"]
        )

        if diagnostic_sets:
            st.write(
                "**Zusätzliche Rohdaten:**"
            )

            for index, source in enumerate(
                diagnostic_sets,
                start=1,
            ):
                with st.expander(
                    f"Datensatz {index}"
                ):
                    st.json(source.get("data"))

    with st.expander(
        "Alle Daten zu diesem Manager"
    ):
        st.write(
            "Ausgewählter Manager: "
            f"{selected_manager_name}"
        )

        st.write(
            "Eigener Manager: "
            + ("Ja" if viewing_self else "Nein")
        )

        if st.button("Manager-Daten laden"):
            with st.spinner(
                "Zusätzliche Daten "
                "werden geladen …"
            ):
                try:
                    (
                        manager_sources,
                        manager_errors,
                    ) = api.explore_manager(
                        league_id,
                        selected_manager_id,
                    )
                except Exception as error:
                    manager_sources = []
                    manager_errors = [str(error)]

            st.session_state[
                "manager_diagnostic_sources"
            ] = manager_sources

            st.session_state[
                "manager_diagnostic_errors"
            ] = manager_errors

        manager_sources = st.session_state.get(
            "manager_diagnostic_sources",
            [],
        )

        manager_errors = st.session_state.get(
            "manager_diagnostic_errors",
            [],
        )

        for index, source in enumerate(
            manager_sources,
            start=1,
        ):
            with st.expander(
                f"Datensatz {index}"
            ):
                st.json(source.get("data"))

        if manager_errors:
            st.warning(
                "Einige zusätzlichen Daten "
                "konnten nicht geladen werden."
            )

    with st.expander(
        "Diagnose der Transferdaten"
    ):
        if feed_samples:
            for index, sample in enumerate(
                feed_samples,
                start=1,
            ):
                with st.expander(
                    f"Datensatz {index}"
                ):
                    st.json(sample)
        else:
            st.write(
                "Keine zusätzlichen "
                "Transferdaten geladen."
            )
