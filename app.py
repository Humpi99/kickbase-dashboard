"""
Kickbase Liga-Dashboard.

Ansichten: Manager, Liga und Transfermarkt.
Optimiert für Desktop und Handy.
"""

import json
from datetime import datetime, timedelta, timezone
from html import escape

import pandas as pd
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken
from streamlit_cookies_controller import CookieController

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

SESSION_COOKIE_NAME = "kickbase_dashboard_session"
SESSION_COOKIE_DAYS = 30

# Eine vollständige Startelf besteht aus 11 Spielern.
REQUIRED_LINEUP_SIZE = 11

# Basis für Logo-Adressen, die nur als Dateiname kommen.
IMAGE_BASE_URL = "https://kickbase.b-cdn.net/"


# ---------------------------------------------------------
# Basis-Hilfsfunktionen
# ---------------------------------------------------------

def first_value(data, keys, default=None):
    """Gibt den ersten vorhandenen Wert zurück."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


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


def table_height(row_count, compact=False):
    """Berechnet die Tabellenhöhe ohne eigenes Scrollfenster."""
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
    """Zeigt deutsche Sortierfelder und sortiert numerisch."""
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
        ascending=direction == "Aufsteigend",
        kind="stable",
    ).reset_index(drop=True)


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
    """Ermittelt den Ligennamen."""
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
    """Gibt einen kurzen Namen für die Handyansicht zurück."""
    last_name = first_value(
        player,
        ["lastName", "ln", "pln"],
    )

    if last_name:
        return str(last_name)

    return get_player_name(player)


# ---------------------------------------------------------
# Vereine, Namen und Logos
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

# Mögliche Felder mit einer Bildadresse des Vereins
TEAM_IMAGE_KEYS = [
    "tim",
    "teamImage",
    "logo",
    "logoUrl",
    "image",
    "imageUrl",
    "img",
    "pim",
    "tiy",
    "crest",
]


def build_image_url(value):
    """
    Baut eine vollständige Bildadresse.

    Kickbase liefert manchmal nur einen Dateinamen.
    """
    if not value or not isinstance(value, str):
        return ""

    cleaned = value.strip()

    if not cleaned:
        return ""

    if cleaned.startswith(("http://", "https://")):
        return cleaned

    if cleaned.startswith("//"):
        return f"https:{cleaned}"

    return IMAGE_BASE_URL + cleaned.lstrip("/")


def collect_dictionaries(data, depth=0):
    """Sammelt rekursiv alle Dictionaries."""
    found = []

    if depth > 8:
        return found

    if isinstance(data, dict):
        found.append(data)

        for value in data.values():
            found.extend(
                collect_dictionaries(value, depth + 1)
            )

    elif isinstance(data, list):
        for item in data:
            found.extend(
                collect_dictionaries(item, depth + 1)
            )

    return found


def looks_like_team(item):
    """Prüft, ob ein Objekt ein Verein sein könnte."""
    if not isinstance(item, dict):
        return False

    team_id = first_value(
        item,
        ["id", "i", "tid", "teamId"],
    )

    if team_id is None:
        return False

    if isinstance(team_id, (dict, list, bool)):
        return False

    has_name = any(
        isinstance(item.get(key), str) and item.get(key)
        for key in [
            "name",
            "n",
            "shortName",
            "sn",
            "tabb",
            "teamName",
            "tn",
        ]
    )

    has_image = any(
        isinstance(item.get(key), str) and item.get(key)
        for key in TEAM_IMAGE_KEYS
    )

    return has_name or has_image


def extract_team_info(sources):
    """
    Baut eine Zuordnung von Vereins-ID zu Name und Logo.

    Rückgabe: {"5": {"name": "FCB", "logo": "https://..."}}
    """
    teams = {}

    for source in sources:
        for item in collect_dictionaries(source.get("data")):
            if not looks_like_team(item):
                continue

            team_id = str(
                first_value(
                    item,
                    ["id", "i", "tid", "teamId"],
                )
            )

            short_name = first_value(
                item,
                ["tabb", "shortName", "sn", "symbol"],
            )

            long_name = first_value(
                item,
                ["name", "n", "teamName", "tn"],
            )

            image_value = first_value(
                item,
                TEAM_IMAGE_KEYS,
            )

            entry = teams.setdefault(
                team_id,
                {
                    "name": "",
                    "long_name": "",
                    "logo": "",
                },
            )

            if not entry["name"] and isinstance(
                short_name,
                str,
            ):
                entry["name"] = short_name.strip()

            if not entry["long_name"] and isinstance(
                long_name,
                str,
            ):
                entry["long_name"] = long_name.strip()

            if not entry["logo"]:
                entry["logo"] = build_image_url(image_value)

    # Fehlende Kurznamen mit dem langen Namen füllen
    for entry in teams.values():
        if not entry["name"]:
            entry["name"] = entry["long_name"]

    return teams


def get_team_id(player):
    """Ermittelt die Vereins-ID eines Spielers."""
    value = first_value(player, TEAM_ID_KEYS)

    if value is None or isinstance(value, (dict, list)):
        return None

    return str(value)


def get_team_name(team_id, teams):
    """Gibt den Vereinsnamen zu einer ID zurück."""
    if not team_id:
        return ""

    entry = teams.get(str(team_id))

    if not entry:
        return ""

    return entry.get("name") or entry.get("long_name") or ""


def get_team_logo(team_id, teams):
    """Gibt die Logo-Adresse zu einer ID zurück."""
    if not team_id:
        return ""

    entry = teams.get(str(team_id))

    if not entry:
        return ""

    return entry.get("logo", "")


def get_club_label(player, teams=None):
    """Ermittelt eine kurze Vereinsbezeichnung."""
    short_name = first_value(player, TEAM_SHORT_KEYS)

    if isinstance(short_name, str) and short_name.strip():
        return short_name.strip()

    club_name = first_value(player, TEAM_NAME_KEYS)

    if isinstance(club_name, dict):
        club_name = first_value(club_name, ["name", "n"])

    if isinstance(club_name, str) and club_name.strip():
        return club_name.strip()

    if teams:
        return get_team_name(get_team_id(player), teams)

    return ""


def get_player_logo(player, teams=None):
    """Ermittelt das Logo des Vereins eines Spielers."""
    direct_image = first_value(player, TEAM_IMAGE_KEYS)

    if isinstance(direct_image, str) and direct_image.strip():
        return build_image_url(direct_image)

    if teams:
        return get_team_logo(get_team_id(player), teams)

    return ""


def logo_html(url, label, size=18):
    """
    Baut ein kleines Logo-Bild.

    Ohne Adresse wird nur der Text zurückgegeben.
    """
    safe_label = escape(str(label or ""))

    if not url:
        return safe_label

    return (
        f"<img src='{escape(url)}' alt='{safe_label}' "
        f"title='{safe_label}' class='team-logo' "
        f"style='height:{size}px;width:{size}px;' />"
    )


# ---------------------------------------------------------
# Spielerfelder
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

LINEUP_FIELD = "lo"


def get_market_value(player):
    """Liest den aktuellen Marktwert."""
    return to_number(
        first_value(player, MARKET_VALUE_KEYS)
    )


def get_profit(player):
    """Liest den Marktwertgewinn seit dem Kauf."""
    return to_number(
        first_value(player, PROFIT_KEYS)
    )


def get_buy_price(player):
    """Berechnet Marktwert minus Marktwertgewinn."""
    market_value = get_market_value(player)
    profit = get_profit(player)

    if market_value is None or profit is None:
        return None

    return market_value - profit


def get_daily_change(player):
    """Liest die Änderung der letzten 24 Stunden."""
    return to_number(
        first_value(player, DAILY_CHANGE_KEYS)
    )


def get_lineup_slot(player):
    """Liest einen gültigen Startelfplatz von 0 bis 10."""
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
    """Prüft, ob ein Spieler in der Startelf steht."""
    return get_lineup_slot(player) is not None


# ---------------------------------------------------------
# Spieltag
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


def parse_date_text(text):
    """Wandelt einen ISO-Datumstext in ein Datum um."""
    if not isinstance(text, str) or len(text) < 8:
        return None

    cleaned = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def parse_any_date(value):
    """Liest ein Datum aus Text oder Zeitstempel."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        return parse_date_text(value)

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
    except (ValueError, OSError, OverflowError):
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
                parsed = parse_date_text(value)

                if parsed is not None and parsed > now:
                    found.append(parsed)

            found.extend(
                collect_future_dates(value, depth + 1)
            )

    elif isinstance(data, list):
        for item in data:
            found.extend(
                collect_future_dates(item, depth + 1)
            )

    return found


def find_days_to_matchday(api, league_id):
    """Sucht ein mögliches nächstes Spieltagsdatum."""
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

        next_date = min(dates)
        difference = next_date - now

        days = max(
            0,
            int(
                (difference.total_seconds() + 86_399)
                // 86_400
            ),
        )

        return days, path

    return None, None


# ---------------------------------------------------------
# Nächste Spiele der Vereine
# ---------------------------------------------------------

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

MATCH_DATE_KEYS = [
    "dt",
    "date",
    "kickoff",
    "startDate",
    "md",
]


def extract_matches(match_sources):
    """Sammelt kommende Spiele beider Mannschaften."""
    matches = []
    seen = set()
    now = datetime.now(timezone.utc)

    for source in match_sources:
        for item in collect_dictionaries(source.get("data")):
            home_id = first_value(item, HOME_TEAM_KEYS)
            away_id = first_value(item, AWAY_TEAM_KEYS)

            if home_id is None or away_id is None:
                continue

            if isinstance(home_id, (dict, list, bool)):
                continue

            if isinstance(away_id, (dict, list, bool)):
                continue

            match_date = None

            for key in MATCH_DATE_KEYS:
                match_date = parse_any_date(item.get(key))

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
                    "date": match_date,
                }
            )

    return matches


def build_next_matches(matches, count=2):
    """
    Baut pro Verein eine Liste der nächsten Gegner.

    Jeder Eintrag enthält Gegner-ID, Heim oder Auswärts
    und das Datum.
    """
    by_team = {}

    for match in sorted(
        matches,
        key=lambda entry: entry["date"],
    ):
        home_id = match["home_id"]
        away_id = match["away_id"]
        date_text = match["date"].strftime("%d.%m.")

        by_team.setdefault(home_id, []).append(
            {
                "opponent_id": away_id,
                "place": "H",
                "date": date_text,
            }
        )

        by_team.setdefault(away_id, []).append(
            {
                "opponent_id": home_id,
                "place": "A",
                "date": date_text,
            }
        )

    return {
        team_id: entries[:count]
        for team_id, entries in by_team.items()
    }


def load_team_and_match_data(api, league_id):
    """Lädt Vereinsdaten mit Logos und die nächsten Spiele."""
    try:
        competition_sources, competition_errors = (
            api.get_competition()
        )
    except Exception as error:
        competition_sources = []
        competition_errors = [str(error)]

    try:
        team_sources, _ = api.get_teams()
    except Exception:
        team_sources = []

    try:
        match_sources, match_errors = api.get_matches(
            league_id
        )
    except Exception as error:
        match_sources = []
        match_errors = [str(error)]

    teams = extract_team_info(
        competition_sources + team_sources
    )

    matches = extract_matches(match_sources)
    next_matches = build_next_matches(matches)

    return {
        "teams": teams,
        "next_matches": next_matches,
        "competition_sources": competition_sources,
        "competition_errors": competition_errors,
        "match_sources": match_sources,
        "match_errors": match_errors,
    }


def build_next_matches_html(team_id, next_matches, teams):
    """Baut die Anzeige der nächsten Spiele mit Logos."""
    entries = next_matches.get(str(team_id or ""), [])

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent_id = entry["opponent_id"]
        opponent_name = get_team_name(opponent_id, teams)
        opponent_logo = get_team_logo(opponent_id, teams)

        if not opponent_name:
            opponent_name = "Gegner"

        parts.append(
            "<span class='match-entry'>"
            f"<span class='match-place'>{entry['place']}</span>"
            f"{logo_html(opponent_logo, opponent_name, 16)}"
            f"<span class='match-date'>{entry['date']}</span>"
            "</span>"
        )

    return "".join(parts)


def build_next_matches_text(team_id, next_matches, teams):
    """Baut einen reinen Text für Sortierung und Fallback."""
    entries = next_matches.get(str(team_id or ""), [])

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent_name = (
            get_team_name(entry["opponent_id"], teams)
            or entry["opponent_id"]
        )

        parts.append(
            f"{entry['place']} {opponent_name} {entry['date']}"
        )

    return " · ".join(parts)


# ---------------------------------------------------------
# Datenansicht und Listenerkennung
# ---------------------------------------------------------

def flatten_fields(value, prefix="", depth=0):
    """Wandelt verschachtelte Daten in eine flache Liste."""
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
                            if number is not None
                            and abs(number) >= 1000
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


def looks_like_league(item):
    """Prüft, ob ein Objekt eine Liga sein könnte."""
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
        manager_fields.intersection(item.keys())
    )


def looks_like_player_with_value(item):
    """Prüft, ob ein Objekt einen Marktwert enthält."""
    return (
        isinstance(item, dict)
        and get_market_value(item) is not None
    )


def find_list(value, check_function, keys, depth=0):
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
            if key in ["tkn", "token", "accessToken"]:
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
    """Sucht die Liga-Liste."""
    return find_list(
        value,
        looks_like_league,
        ["leagues", "lgs", "ls", "srvl"],
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
    """Sucht Spieler mit einem Marktwert."""
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
# Verschlüsselte Anmeldung
# ---------------------------------------------------------

def get_cookie_cipher():
    """Lädt den Verschlüsselungsschlüssel aus Secrets."""
    try:
        secret = st.secrets["COOKIE_SECRET"]
    except (KeyError, FileNotFoundError):
        return None

    try:
        return Fernet(str(secret).encode("utf-8"))
    except (TypeError, ValueError):
        return None


def remove_login_cookie(cookie_controller):
    """Entfernt das gespeicherte Login-Cookie."""
    try:
        cookie_controller.remove(SESSION_COOKIE_NAME)
    except Exception:
        pass


def save_login_cookie(cookie_controller, api, leagues):
    """Speichert Token und Basisdaten verschlüsselt."""
    cipher = get_cookie_cipher()

    if cipher is None:
        return False

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=SESSION_COOKIE_DAYS)
    )

    payload = {
        "token": api.token,
        "own_user_id": api.own_user_id,
        "leagues": leagues,
        "expires_at": expires_at.isoformat(),
    }

    encrypted = cipher.encrypt(
        json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")
    ).decode("utf-8")

    try:
        cookie_controller.set(
            SESSION_COOKIE_NAME,
            encrypted,
            max_age=SESSION_COOKIE_DAYS * 24 * 60 * 60,
        )
    except Exception:
        return False

    return True


def restore_login_cookie(cookie_controller):
    """Stellt eine gültige verschlüsselte Anmeldung wieder her."""
    cipher = get_cookie_cipher()

    if cipher is None:
        return False

    try:
        encrypted = cookie_controller.get(
            SESSION_COOKIE_NAME
        )
    except Exception:
        return False

    if not encrypted:
        return False

    try:
        decrypted = cipher.decrypt(
            encrypted.encode("utf-8")
        )

        payload = json.loads(decrypted.decode("utf-8"))

        expires_at = datetime.fromisoformat(
            payload["expires_at"]
        )

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if expires_at <= datetime.now(timezone.utc):
            remove_login_cookie(cookie_controller)
            return False

        token = payload.get("token")
        leagues = payload.get("leagues")
        own_user_id = payload.get("own_user_id")

        if not token or not isinstance(leagues, list):
            remove_login_cookie(cookie_controller)
            return False

        if not leagues:
            remove_login_cookie(cookie_controller)
            return False

        api = KickbaseAPI()
        api.restore_session(
            token,
            own_user_id=own_user_id,
        )

        first_league_id = get_league_id(leagues[0])

        if not first_league_id:
            remove_login_cookie(cookie_controller)
            return False

        ranking_sources, _ = api.get_ranking(
            first_league_id
        )

        if not ranking_sources:
            remove_login_cookie(cookie_controller)
            return False

        st.session_state["api"] = api
        st.session_state["leagues"] = leagues
        st.session_state["logged_in"] = True
        st.session_state["remember_login"] = True

        return True

    except (
        InvalidToken,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        remove_login_cookie(cookie_controller)
        return False


# ---------------------------------------------------------
# Transfers
# ---------------------------------------------------------

def extract_transfer_events(data, depth=0):
    """Sammelt Einträge, die wie ein Transfer aussehen."""
    events = []

    if depth > 6:
        return events

    if isinstance(data, list):
        for item in data:
            events.extend(
                extract_transfer_events(item, depth + 1)
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
        and (buyer is not None or seller is not None)
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


def load_feed_transfers(api, league_id, manager_id):
    """Berechnet einen Feed-basierten realisierten Gewinn."""
    events = []
    raw_samples = []

    try:
        sources, _ = api.get_manager_transfers(
            league_id,
            manager_id,
        )

        for source in sources:
            events.extend(
                extract_transfer_events(source["data"])
            )

            if len(raw_samples) < 1:
                raw_samples.append(
                    {
                        "Quelle": source["path"],
                        "Daten": source["data"],
                    }
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
                extract_transfer_events(source["data"])
            )

            if start == 0 and len(raw_samples) < 2:
                raw_samples.append(
                    {
                        "Quelle": source["path"],
                        "Daten": source["data"],
                    }
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
        buy_prices = purchases.get(player_id, [])

        for index, sale_price in enumerate(sale_prices):
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
# Kennzahlen
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
    """Berechnet Kontostand, Verkauf und Spieltagsprognose."""
    if real_balance is not None:
        balance = real_balance
        is_real = True
    else:
        balance = (
            BASE_BUDGET
            + bonus
            + total_profit
            - stats["squad_value"]
        )
        is_real = False

    after_sale = balance + stats["trading_value"]

    at_matchday = (
        after_sale
        + stats["trend_trading"] * days_to_matchday
    )

    return {
        "balance": balance,
        "after_sale": after_sale,
        "at_matchday": at_matchday,
        "is_real": is_real,
    }


def load_manager_players(api, league_id, manager_id):
    """Lädt den Kader eines bestimmten Managers."""
    try:
        squad_result = api.get_manager_squad(
            league_id,
            manager_id,
        )

        return find_players_with_value(squad_result), None

    except Exception as error:
        return [], str(error)


def load_realized_profit(api, league_id, manager_id):
    """Liest den realisierten Gewinn aus prft."""
    try:
        return api.get_realized_profit(
            league_id,
            manager_id,
        )
    except Exception:
        return None, None


def load_real_budget(api, league_id):
    """Liest den echten Kontostand des eigenen Accounts."""
    try:
        return api.get_budget(league_id)
    except Exception:
        return None, None


def is_own_manager(api, manager_id):
    """Prüft, ob ein Manager der angemeldete Nutzer ist."""
    own_id = getattr(api, "own_user_id", None)

    if not own_id:
        return False

    return str(own_id) == str(manager_id)


def compute_own_bonus(api, league_id, real_balance):
    """Berechnet den Bonus aus dem echten Kontostand."""
    own_id = getattr(api, "own_user_id", None)

    if not own_id or real_balance is None:
        return None

    players, _ = load_manager_players(
        api,
        league_id,
        own_id,
    )

    if not players:
        return None

    stats = compute_stats(players)

    realized, _ = load_realized_profit(
        api,
        league_id,
        own_id,
    )

    total_profit = (
        stats["profit_in_club"] + (realized or 0.0)
    )

    plain = (
        BASE_BUDGET
        + total_profit
        - stats["squad_value"]
    )

    return {
        "plain": plain,
        "real": real_balance,
        "bonus": real_balance - plain,
        "profit": total_profit,
        "squad_value": stats["squad_value"],
    }


# ---------------------------------------------------------
# Kaderanzeige der Liga-Tabelle
# ---------------------------------------------------------

def build_squad_label(player_count, lineup_count):
    """
    Baut den Text für die Spalte Kader.

    Die Startelf-Anzahl steht nur in Klammern,
    wenn sie nicht genau 11 Spieler beträgt.
    """
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


# ---------------------------------------------------------
# Tabellenformatierung
# ---------------------------------------------------------

def currency_formatter(value):
    """Formatiert Tabellenbeträge ohne Vorzeichen."""
    return format_currency(value)


def signed_formatter(value):
    """Formatiert Tabellenbeträge mit Vorzeichen."""
    return format_signed_currency(value)


def color_by_value(value):
    """Färbt positive und negative Zahlen."""
    number = to_number(value)

    if number is None or number == 0:
        return ""

    if number > 0:
        return (
            f"color: {COLOR_POSITIVE}; font-weight: 600"
        )

    return f"color: {COLOR_NEGATIVE}; font-weight: 600"


def apply_value_colors(styled, columns):
    """Unterstützt neue und ältere Pandas-Versionen."""
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


def style_league_table(frame, lineup_counts=None):
    """
    Formatiert und färbt die Liga-Tabelle.

    Die Spalte Kader wird rot, wenn die Startelf
    nicht genau 11 Spieler enthält.
    """
    signed_columns = [
        column
        for column in [
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
            "Kontostand",
            "Nach Verkauf",
            "Am Spieltag",
        ]
        if column in frame.columns
    ]

    currency_columns = [
        column
        for column in [
            "Start 11",
            "Trading",
            "Kaderwert",
        ]
        if column in frame.columns
    ]

    styled = apply_value_colors(
        frame.style,
        signed_columns,
    )

    if (
        lineup_counts is not None
        and "Kader" in frame.columns
    ):

        def color_squad(column):
            """Färbt unvollständige Startelf-Angaben rot."""
            styles = []

            for count in lineup_counts:
                number = to_number(count)

                if (
                    number is None
                    or int(number) != REQUIRED_LINEUP_SIZE
                ):
                    styles.append(
                        f"color: {COLOR_NEGATIVE}; "
                        "font-weight: 700"
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
        formats[column] = currency_formatter

    for column in signed_columns:
        formats[column] = signed_formatter

    return styled.format(formats)


def style_trades_table(frame):
    """Formatiert die Tabelle verkaufter Spieler."""
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
            "Verkaufspreis": currency_formatter,
            "Gewinn": signed_formatter,
        }
    )


# ---------------------------------------------------------
# Kadertabelle als HTML mit Logos
# ---------------------------------------------------------

SQUAD_STYLE = (
    "<style>"
    ".squad-wrapper{overflow-x:auto;margin-top:0.4rem;"
    "margin-bottom:0.6rem;}"
    ".squad-table{width:100%;border-collapse:collapse;"
    "font-size:0.86rem;}"
    ".squad-table th{text-align:left;color:#8a8a8a;"
    "font-size:0.7rem;font-weight:600;"
    "text-transform:uppercase;letter-spacing:0.05em;"
    "padding:0.5rem 0.55rem;border-bottom:1px solid #e6e6e6;"
    "white-space:nowrap;}"
    ".squad-table td{padding:0.45rem 0.55rem;"
    "border-bottom:1px solid #f2f2f2;vertical-align:middle;"
    "white-space:nowrap;}"
    ".squad-table tr.trading td{color:#9a9a9a;"
    "background-color:#fafafa;}"
    ".squad-player{display:flex;align-items:center;"
    "gap:0.45rem;}"
    ".team-logo{object-fit:contain;border-radius:3px;"
    "flex:0 0 auto;}"
    ".squad-player-name{font-weight:600;color:#1c1c1c;}"
    ".squad-table tr.trading .squad-player-name{"
    "color:#9a9a9a;}"
    ".match-entry{display:inline-flex;align-items:center;"
    "gap:0.22rem;margin-right:0.55rem;}"
    ".match-place{font-weight:700;font-size:0.72rem;"
    "color:#777777;}"
    ".match-date{font-size:0.74rem;color:#777777;}"
    ".value-plus{color:#12a150;font-weight:600;}"
    ".value-minus{color:#e03131;font-weight:600;}"
    "@media (max-width:640px){"
    ".squad-table{font-size:0.78rem;}"
    ".squad-table th{font-size:0.62rem;padding:0.4rem;}"
    ".squad-table td{padding:0.38rem 0.4rem;}}"
    "</style>"
)


def signed_cell_html(value):
    """Baut eine gefärbte Zelle mit Vorzeichen."""
    number = to_number(value)
    text = format_signed_currency(value)

    if number is None or number == 0:
        return text

    css_class = "value-plus" if number > 0 else "value-minus"

    return f"<span class='{css_class}'>{text}</span>"


def render_squad_table(frame, columns):
    """
    Zeichnet die Kadertabelle als HTML.

    Nur so kann ein Logo direkt neben dem Namen stehen.
    """
    header_cells = "".join(
        f"<th>{escape(column)}</th>" for column in columns
    )

    body_rows = []

    for _, row in frame.iterrows():
        row_class = (
            " class='trading'"
            if row.get("Status") == "Trading"
            else ""
        )

        cells = []

        for column in columns:
            if column == "Spieler":
                cells.append(
                    "<td><div class='squad-player'>"
                    f"{row['_spieler_html']}</div></td>"
                )

            elif column == "Nächste Spiele":
                cells.append(
                    f"<td>{row['_naechste_html']}</td>"
                )

            elif column in [
                "Einstandspreis",
                "Marktwert",
            ]:
                cells.append(
                    f"<td>{format_currency(row[column])}</td>"
                )

            elif column in [
                "Gewinn gesamt",
                "Trend 24 Stunden",
            ]:
                cells.append(
                    f"<td>{signed_cell_html(row[column])}</td>"
                )

            else:
                cells.append(
                    f"<td>{escape(str(row[column]))}</td>"
                )

        body_rows.append(
            f"<tr{row_class}>{''.join(cells)}</tr>"
        )

    table_html = (
        "<div class='squad-wrapper'>"
        "<table class='squad-table'>"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )

    st.markdown(table_html, unsafe_allow_html=True)


# ---------------------------------------------------------
# KPI-Blöcke
# ---------------------------------------------------------

def kpi_block(title, entries, compact=False):
    """Zeigt einen KPI-Block mit drei Spalten."""
    colors = {
        "neutral": COLOR_NEUTRAL,
        "plus": COLOR_POSITIVE,
        "minus": COLOR_NEGATIVE,
    }

    value_size = 19 if compact else 24

    st.markdown(
        f"<div class='kpi-title' style='"
        f"border-top:1px solid {COLOR_LINE};"
        f"padding-top:10px;margin-top:18px;"
        f"font-size:12px;font-weight:500;"
        f"letter-spacing:0.08em;"
        f"text-transform:uppercase;"
        f"color:{COLOR_LABEL};'>{title}</div>",
        unsafe_allow_html=True,
    )

    columns = st.columns(len(entries))

    for column, entry in zip(columns, entries):
        label, value, notes, tone = entry
        color = colors.get(tone, COLOR_NEUTRAL)
        notes_html = ""

        if not compact:
            for note in notes:
                if note:
                    notes_html += (
                        f"<div style='font-size:12px;"
                        f"color:{COLOR_LABEL};"
                        f"line-height:1.5;'>{note}</div>"
                    )

        column.markdown(
            f"<div class='kpi-card' "
            f"style='padding:6px 0 2px 0;'>"
            f"<div style='font-size:12px;"
            f"color:{COLOR_LABEL};'>{label}</div>"
            f"<div class='kpi-value' "
            f"style='font-size:{value_size}px;"
            f"font-weight:700;color:{color};"
            f"padding:2px 0 4px 0;'>{value}</div>"
            f"{notes_html}"
            f"</div>",
            unsafe_allow_html=True,
        )


def tone_of(value):
    """Bestimmt die Farbe anhand des Vorzeichens."""
    number = to_number(value)

    if number is None or number == 0:
        return "neutral"

    return "plus" if number > 0 else "minus"


def build_budget_kpis(
    budget,
    stats,
    bonus,
    days_to_matchday,
    days_source,
    budget_source,
):
    """Baut die Einträge für den Budget-Block."""
    if budget["is_real"]:
        balance_notes = [
            "echter Kontostand aus der API",
            str(budget_source or ""),
        ]
    else:
        balance_notes = [
            (
                f"{format_currency(BASE_BUDGET)} Grundwert "
                f"plus {format_currency(bonus)} Bonus"
            ),
            "plus Gewinn, minus Kaderwert",
        ]

    return [
        (
            "Kontostand",
            format_signed_currency(budget["balance"]),
            balance_notes,
            tone_of(budget["balance"]),
        ),
        (
            "Nach Verkauf",
            format_signed_currency(budget["after_sale"]),
            [
                (
                    "plus Trading: "
                    f"{format_currency(stats['trading_value'])}"
                ),
                f"{stats['trading_count']} Spieler",
            ],
            tone_of(budget["after_sale"]),
        ),
        (
            "Am Spieltag",
            format_signed_currency(budget["at_matchday"]),
            [
                f"{days_to_matchday} Tage ({days_source})",
                (
                    "Trend Trading: "
                    f"{format_signed_currency(stats['trend_trading'])}"
                    " pro Tag"
                ),
            ],
            tone_of(budget["at_matchday"]),
        ),
    ]


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

    section[data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        border-radius: 8px;
    }

    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
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

st.markdown(SQUAD_STYLE, unsafe_allow_html=True)

cookie_controller = CookieController()


# ---------------------------------------------------------
# Login wiederherstellen
# ---------------------------------------------------------

if (
    not st.session_state.get("logged_in")
    and not st.session_state.get("cookie_checked")
):
    restored = restore_login_cookie(cookie_controller)

    st.session_state["cookie_checked"] = True

    if restored:
        st.rerun()


# ---------------------------------------------------------
# Zentraler Anmeldebildschirm
# ---------------------------------------------------------

if not st.session_state.get("logged_in"):
    left_space, login_column, right_space = st.columns(
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

            remember_login = st.checkbox(
                "30 Tage angemeldet bleiben",
                value=True,
                help=(
                    "Das Passwort wird nicht gespeichert. "
                    "Nur das Kickbase-Token wird "
                    "verschlüsselt im Browser abgelegt."
                ),
            )

            login_clicked = st.form_submit_button(
                "Einloggen",
                type="primary",
                use_container_width=True,
            )

        if get_cookie_cipher() is None:
            st.info(
                "Die dauerhafte Anmeldung ist optional. "
                "Für sie muss COOKIE_SECRET in den "
                "Streamlit Secrets hinterlegt werden."
            )

        st.markdown(
            """
            <div class="login-security">
                🔒 Das Passwort wird nur direkt an Kickbase
                übertragen und nicht von diesem Dashboard
                gespeichert.
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
                    with st.spinner("Anmeldung läuft …"):
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
                            "Login erfolgreich, aber es "
                            "wurde keine Liga erkannt."
                        )
                        st.stop()

                    st.session_state["api"] = api
                    st.session_state["leagues"] = leagues
                    st.session_state["logged_in"] = True
                    st.session_state["remember_login"] = (
                        remember_login
                    )
                    st.session_state["view"] = "Manager"

                    if remember_login:
                        cookie_saved = save_login_cookie(
                            cookie_controller,
                            api,
                            leagues,
                        )

                        if not cookie_saved:
                            st.session_state[
                                "cookie_warning"
                            ] = True
                    else:
                        remove_login_cookie(
                            cookie_controller
                        )

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
    help="Zeigt weniger Spalten und Zusatztexte.",
)

league_index = st.sidebar.selectbox(
    "Liga auswählen",
    range(len(leagues)),
    format_func=lambda index: get_league_name(
        leagues[index]
    ),
)

selected_league = leagues[league_index]
league_id = get_league_id(selected_league)
league_name = get_league_name(selected_league)

show_realized = st.sidebar.checkbox(
    "Transferhistorie zusätzlich laden",
    value=not compact,
    help=(
        "Lädt mögliche Verkäufe aus dem Feed. "
        "Das Feld prft wird unabhängig davon geprüft."
    ),
)

kpis_expanded = st.sidebar.checkbox(
    "Kennzahlen aufgeklappt starten",
    value=False,
)


# ---------------------------------------------------------
# Vereine und Spielplan laden
# ---------------------------------------------------------

matches_key = f"team_matches_v2_{league_id}"

if matches_key not in st.session_state:
    with st.spinner("Vereine und Spielplan werden geladen …"):
        st.session_state[matches_key] = (
            load_team_and_match_data(api, league_id)
        )

matches_info = st.session_state[matches_key]
teams = matches_info["teams"]
next_matches = matches_info["next_matches"]


# ---------------------------------------------------------
# Budget-Einstellungen
# ---------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.markdown("### Budget")
st.sidebar.caption(
    f"Grundwert fest: {format_currency(BASE_BUDGET)}"
)

budget_key = f"own_budget_{league_id}"

if budget_key not in st.session_state:
    with st.spinner(
        "Eigener Kontostand wird gelesen …"
    ):
        st.session_state[budget_key] = load_real_budget(
            api,
            league_id,
        )

own_budget, own_budget_source = (
    st.session_state[budget_key]
)

bonus_key = f"own_bonus_{league_id}"

if st.sidebar.button(
    "Bonus neu berechnen",
    use_container_width=True,
):
    st.session_state.pop(bonus_key, None)
    st.session_state.pop(budget_key, None)
    st.session_state.pop(
        f"league_rows_v7_{league_id}",
        None,
    )

    st.rerun()

if bonus_key not in st.session_state:
    with st.spinner("Bonus wird ermittelt …"):
        st.session_state[bonus_key] = compute_own_bonus(
            api,
            league_id,
            own_budget,
        )

own_bonus_info = st.session_state[bonus_key]

if own_bonus_info is not None:
    suggested_bonus = (
        own_bonus_info["bonus"] / 1_000_000
    )
    bonus_hint = "Vorschlag aus der eigenen Differenz."
else:
    suggested_bonus = 0.0
    bonus_hint = (
        "Kein echter eigener Kontostand gefunden. "
        "Bonus bitte selbst schätzen."
    )

bonus_widget_key = f"bonus_mio_{league_id}"

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
        "Dieser Bonus wird nur für die Schätzung "
        "fremder Manager verwendet."
    ),
)

bonus = bonus_mio * 1_000_000

st.sidebar.caption(bonus_hint)

if own_bonus_info is not None:
    st.sidebar.caption(
        "Eigene reine Berechnung: "
        + format_currency(own_bonus_info["plain"])
    )

    st.sidebar.caption(
        "Eigener echter Kontostand: "
        + format_currency(own_bonus_info["real"])
    )

    st.sidebar.caption(
        "Differenz als Bonus: "
        + format_signed_currency(
            own_bonus_info["bonus"]
        )
    )


# ---------------------------------------------------------
# Tage bis zum Spieltag
# ---------------------------------------------------------

matchday_key = f"matchday_days_{league_id}"

if matchday_key not in st.session_state:
    with st.spinner("Spieltag wird gesucht …"):
        found_days, found_path = (
            find_days_to_matchday(
                api,
                league_id,
            )
        )

    st.session_state[matchday_key] = (
        found_days,
        found_path,
    )

found_days, found_path = (
    st.session_state[matchday_key]
)

if found_days is None:
    default_days = 3
    days_hint = (
        "Kein sicherer Endpunkt gefunden. "
        "Bitte manuell einstellen."
    )
else:
    default_days = found_days
    days_hint = f"Gefunden über {found_path}"

days_widget_key = f"days_to_matchday_{league_id}"

if days_widget_key not in st.session_state:
    st.session_state[days_widget_key] = int(
        default_days
    )

days_to_matchday = st.sidebar.number_input(
    "Tage bis zum Spieltag",
    min_value=0,
    max_value=30,
    step=1,
    key=days_widget_key,
    help=days_hint,
)

if (
    found_days is not None
    and days_to_matchday == found_days
):
    days_source = "aus der API"
else:
    days_source = "manuell"

st.sidebar.caption(days_hint)


# ---------------------------------------------------------
# Abmelden
# ---------------------------------------------------------

st.sidebar.markdown("---")

if st.sidebar.button(
    "Abmelden",
    key="logout",
    use_container_width=True,
):
    remove_login_cookie(cookie_controller)
    st.session_state.clear()
    st.rerun()


# ---------------------------------------------------------
# Titel und obere Navigation
# ---------------------------------------------------------

if compact:
    st.markdown(
        f"<div style='font-size:15px;"
        f"font-weight:650;padding-bottom:5px;'>"
        f"⚽ {league_name}</div>",
        unsafe_allow_html=True,
    )
else:
    st.title(f"⚽ {league_name}")

if st.session_state.pop("cookie_warning", False):
    st.warning(
        "Die Anmeldung funktioniert, aber das Cookie "
        "konnte nicht gespeichert werden."
    )

st.markdown(
    "<div class='top-nav-label'>Ansicht</div>",
    unsafe_allow_html=True,
)

manager_nav, league_nav, market_nav = st.columns(3)

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
            if st.session_state["view"] == "Transfermarkt"
            else "secondary"
        ),
        use_container_width=True,
    ):
        st.session_state["view"] = "Transfermarkt"
        st.session_state["came_from_league"] = False
        st.rerun()

view = st.session_state["view"]


# ---------------------------------------------------------
# Transfermarkt-Ansicht
# ---------------------------------------------------------

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

managers = []

with st.spinner("Ranking wird geladen …"):
    ranking_sources, ranking_errors = api.get_ranking(
        league_id
    )

for source in ranking_sources:
    found = find_managers(source["data"])

    if found:
        managers = found
        break

if not managers:
    st.error(
        "Es konnten keine Manager geladen werden. "
        "Möglicherweise ist die Anmeldung abgelaufen."
    )

    if st.button("Neu anmelden"):
        remove_login_cookie(cookie_controller)
        st.session_state.clear()
        st.rerun()

    with st.expander("Fehlerdetails"):
        st.write(ranking_errors)

    st.stop()


# ---------------------------------------------------------
# Liga-Ansicht
# ---------------------------------------------------------

if view == "Liga":
    st.subheader("Liga-Vergleich")

    if not compact:
        st.caption(
            "Ein Klick auf eine Zeile öffnet die "
            "Detailansicht. Eine rote Kaderzahl bedeutet: "
            "keine vollständige Startelf."
        )

    cache_key = f"league_rows_v7_{league_id}"

    if st.button("Daten neu laden"):
        st.session_state.pop(cache_key, None)
        st.rerun()

    if cache_key not in st.session_state:
        rows = []

        progress = st.progress(
            0.0,
            text="Kader werden geladen …",
        )

        for index, manager in enumerate(managers):
            manager_id = get_manager_id(manager)
            manager_name = get_manager_name(manager)

            manager_players, _ = load_manager_players(
                api,
                league_id,
                manager_id,
            )

            manager_stats = compute_stats(
                manager_players
            )

            realized, _ = load_realized_profit(
                api,
                league_id,
                manager_id,
            )

            realized_value = realized or 0.0
            own = is_own_manager(api, manager_id)

            rows.append(
                {
                    "Manager-ID": manager_id,
                    "Manager": manager_name,
                    "Ich": own,
                    "Startelf-Anzahl": (
                        manager_stats["lineup_count"]
                    ),
                    "Kader": (
                        manager_stats["player_count"]
                    ),
                    "Start 11": (
                        manager_stats["lineup_value"]
                    ),
                    "Trading": (
                        manager_stats["trading_value"]
                    ),
                    "Kaderwert": (
                        manager_stats["squad_value"]
                    ),
                    "Gewinn gesamt": (
                        manager_stats["profit_in_club"]
                        + realized_value
                    ),
                    "Trend Start 11": (
                        manager_stats["trend_lineup"]
                    ),
                    "Trend Trading": (
                        manager_stats["trend_trading"]
                    ),
                    "Trend gesamt": (
                        manager_stats["trend_total"]
                    ),
                }
            )

            progress.progress(
                (index + 1) / len(managers),
                text=(
                    "Kader werden geladen … "
                    f"{index + 1} von {len(managers)}"
                ),
            )

        progress.empty()
        st.session_state[cache_key] = rows

    rows = st.session_state[cache_key]
    league_frame = pd.DataFrame(rows)

    league_frame["Kontostand"] = (
        BASE_BUDGET
        + bonus
        + league_frame["Gewinn gesamt"]
        - league_frame["Kaderwert"]
    )

    if (
        own_budget is not None
        and "Ich" in league_frame.columns
    ):
        league_frame.loc[
            league_frame["Ich"],
            "Kontostand",
        ] = own_budget

    league_frame["Nach Verkauf"] = (
        league_frame["Kontostand"]
        + league_frame["Trading"]
    )

    league_frame["Am Spieltag"] = (
        league_frame["Nach Verkauf"]
        + league_frame["Trend Trading"]
        * days_to_matchday
    )

    if "Ich" in league_frame.columns:
        league_frame["Manager"] = [
            f"● {name}" if own else name
            for name, own in zip(
                league_frame["Manager"],
                league_frame["Ich"],
            )
        ]

    if compact:
        visible_columns = [
            "Manager",
            "Kader",
            "Kaderwert",
            "Gewinn gesamt",
            "Trend gesamt",
            "Kontostand",
        ]
    else:
        visible_columns = [
            "Manager",
            "Kader",
            "Start 11",
            "Trading",
            "Kaderwert",
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
            "Kontostand",
            "Nach Verkauf",
            "Am Spieltag",
        ]

    sortable_frame = league_frame[
        [
            "Manager-ID",
            "Startelf-Anzahl",
            *visible_columns,
        ]
    ].copy()

    sortable_frame = sort_controls(
        sortable_frame,
        visible_columns,
        key="liga",
        default_column="Kaderwert",
        compact=compact,
    )

    sorted_manager_ids = sortable_frame[
        "Manager-ID"
    ].tolist()

    lineup_counts = sortable_frame[
        "Startelf-Anzahl"
    ].tolist()

    display_frame = sortable_frame.drop(
        columns=["Manager-ID", "Startelf-Anzahl"]
    )

    display_frame["Kader"] = [
        build_squad_label(total, lineup)
        for total, lineup in zip(
            display_frame["Kader"],
            lineup_counts,
        )
    ]

    dataframe_arguments = {
        "use_container_width": True,
        "hide_index": True,
        "height": table_height(
            len(display_frame),
            compact,
        ),
        "key": "league_table",
    }

    try:
        selection = st.dataframe(
            style_league_table(
                display_frame,
                lineup_counts=lineup_counts,
            ),
            on_select="rerun",
            selection_mode="single-row",
            **dataframe_arguments,
        )
    except TypeError:
        selection = None

        st.dataframe(
            style_league_table(
                display_frame,
                lineup_counts=lineup_counts,
            ),
            **dataframe_arguments,
        )

        st.info(
            "Der Zeilenklick benötigt eine neuere "
            "Streamlit-Version."
        )

    st.caption(
        "Spalte Kader: Gesamtzahl der Spieler. "
        "Die Zahl in Klammern und die rote Farbe "
        "erscheinen nur, wenn die Startelf nicht "
        "11 Spieler hat."
    )

    if own_budget is not None:
        st.caption(
            "Eigener Kontostand echt aus der API. "
            "Alle anderen geschätzt mit "
            f"{format_currency(BASE_BUDGET)} Grundwert, "
            f"{format_currency(bonus)} Bonus und "
            f"{days_to_matchday} Tagen bis zum Spieltag."
        )
    else:
        st.caption(
            "Alle Kontostände geschätzt mit "
            f"{format_currency(BASE_BUDGET)} Grundwert, "
            f"{format_currency(bonus)} Bonus und "
            f"{days_to_matchday} Tagen bis zum Spieltag."
        )

    selected_rows = []

    if selection is not None:
        try:
            selected_rows = selection.selection.rows
        except AttributeError:
            selected_rows = []

    if selected_rows:
        selected_row = selected_rows[0]

        if selected_row < len(sorted_manager_ids):
            chosen_manager_id = str(
                sorted_manager_ids[selected_row]
            )

            for index, manager in enumerate(managers):
                if (
                    get_manager_id(manager)
                    == chosen_manager_id
                ):
                    st.session_state[
                        "selected_manager_index"
                    ] = index
                    break

            st.session_state["view"] = "Manager"
            st.session_state["came_from_league"] = True
            st.rerun()

    st.stop()


# ---------------------------------------------------------
# Manager-Ansicht
# ---------------------------------------------------------

if st.session_state.get("came_from_league"):
    if st.button("← Zurück zur Liga-Übersicht"):
        st.session_state["came_from_league"] = False
        st.session_state["view"] = "Liga"
        st.rerun()

default_index = st.session_state.get(
    "selected_manager_index",
    0,
)

if not isinstance(default_index, int):
    default_index = 0

if default_index >= len(managers):
    default_index = 0

manager_index = st.selectbox(
    "Manager auswählen",
    range(len(managers)),
    index=default_index,
    format_func=lambda index: (
        f"● {get_manager_name(managers[index])}"
        if is_own_manager(
            api,
            get_manager_id(managers[index]),
        )
        else get_manager_name(managers[index])
    ),
)

if manager_index != default_index:
    st.session_state["came_from_league"] = False

st.session_state["selected_manager_index"] = (
    manager_index
)

selected_manager = managers[manager_index]
selected_manager_id = get_manager_id(
    selected_manager
)
selected_manager_name = get_manager_name(
    selected_manager
)

viewing_self = is_own_manager(
    api,
    selected_manager_id,
)


# ---------------------------------------------------------
# Kader und Gewinn laden
# ---------------------------------------------------------

with st.spinner("Kader wird geladen …"):
    players, squad_error = load_manager_players(
        api,
        league_id,
        selected_manager_id,
    )

realized_profit = None
realized_trades = []
feed_samples = []

if show_realized and players:
    with st.spinner(
        "Transferhistorie wird gelesen …"
    ):
        (
            realized_profit,
            realized_trades,
            feed_samples,
        ) = load_feed_transfers(
            api,
            league_id,
            selected_manager_id,
        )

prft_value = None
prft_source = None

if players:
    with st.spinner(
        "Realisierter Gewinn wird gelesen …"
    ):
        prft_value, prft_source = (
            load_realized_profit(
                api,
                league_id,
                selected_manager_id,
            )
        )

if prft_value is not None:
    realized_profit = prft_value
    realized_note = (
        f"aus Feld prft über {prft_source}"
        if prft_source
        else "aus Feld prft"
    )
else:
    realized_note = (
        f"{len(realized_trades)} Verkäufe "
        "aus Feed-Daten erkannt"
    )


# ---------------------------------------------------------
# Manager-Kennzahlen
# ---------------------------------------------------------

stats = compute_stats(players)

total_profit = stats["profit_in_club"]

if realized_profit is not None:
    total_profit += realized_profit

real_balance = own_budget if viewing_self else None

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
        f"Kennzahlen: {selected_manager_name}"
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
                        "Einstand: "
                        f"{format_currency(stats['buy_lineup'])}"
                    ),
                    f"{stats['lineup_count']} Spieler",
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
                        f"{format_currency(stats['buy_trading'])}"
                    ),
                    f"{stats['trading_count']} Spieler",
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
                        f"{format_currency(stats['buy_total'])}"
                    ),
                    f"{stats['player_count']} Spieler",
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
                "realisiert",
                (
                    format_signed_currency(
                        realized_profit
                    )
                    if realized_profit is not None
                    else "—"
                ),
                [realized_note],
                tone_of(realized_profit),
            ),
            (
                "im Verein",
                format_signed_currency(
                    stats["profit_in_club"]
                ),
                ["aus Marktwertsteigerung"],
                tone_of(stats["profit_in_club"]),
            ),
            (
                "Gesamt",
                format_signed_currency(total_profit),
                ["realisiert plus im Verein"],
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
                ["letzte 24 Stunden"],
                tone_of(stats["trend_lineup"]),
            ),
            (
                "Trading",
                format_signed_currency(
                    stats["trend_trading"]
                ),
                ["letzte 24 Stunden"],
                tone_of(stats["trend_trading"]),
            ),
            (
                "Gesamt",
                format_signed_currency(
                    stats["trend_total"]
                ),
                ["letzte 24 Stunden"],
                tone_of(stats["trend_total"]),
            ),
        ],
        compact=compact,
    )

    budget_title = (
        "Budget echt"
        if budget["is_real"]
        else "Budget geschätzt"
    )

    kpi_block(
        budget_title,
        build_budget_kpis(
            budget,
            stats,
            bonus,
            days_to_matchday,
            days_source,
            own_budget_source,
        ),
        compact=compact,
    )

    st.markdown("")


# ---------------------------------------------------------
# Kadertabelle mit Logos
# ---------------------------------------------------------

if compact:
    st.subheader("Kader")
else:
    st.subheader(
        f"Kader von {selected_manager_name}"
    )

if players and stats["lineup_count"] != REQUIRED_LINEUP_SIZE:
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

    for player in players:
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
        club_label = get_club_label(player, teams)
        club_logo = get_player_logo(player, teams)

        if compact:
            player_name = get_short_player_name(player)
        else:
            player_name = get_player_name(player)

        # Logo und Name stehen in derselben Spalte
        player_html = (
            f"{logo_html(club_logo, club_label, 18)}"
            f"<span class='squad-player-name'>"
            f"{escape(player_name)}</span>"
        )

        player_rows.append(
            {
                "Spieler": player_name,
                "_spieler_html": player_html,
                "Position": position_name,
                "Status": status,
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
                    )
                ),
                "Einstandspreis": get_buy_price(
                    player
                ),
                "Marktwert": get_market_value(
                    player
                ),
                "Gewinn gesamt": get_profit(player),
                "Trend 24 Stunden": (
                    get_daily_change(player)
                ),
            }
        )

    player_frame = pd.DataFrame(player_rows)

    if compact:
        player_columns = [
            "Spieler",
            "Status",
            "Nächste Spiele",
            "Marktwert",
            "Gewinn gesamt",
            "Trend 24 Stunden",
        ]
    else:
        player_columns = [
            "Spieler",
            "Position",
            "Status",
            "Nächste Spiele",
            "Einstandspreis",
            "Marktwert",
            "Gewinn gesamt",
            "Trend 24 Stunden",
        ]

    player_frame = sort_controls(
        player_frame,
        player_columns,
        key="kader",
        default_column="Gewinn gesamt",
        compact=compact,
    )

    render_squad_table(player_frame, player_columns)

    st.caption(
        "Das Logo links vom Namen ist der eigene Verein. "
        "H bedeutet Heimspiel, A bedeutet Auswärtsspiel."
    )

else:
    st.info("Keine Spieler gefunden.")


# ---------------------------------------------------------
# Verkaufte Spieler
# ---------------------------------------------------------

if realized_trades:
    st.subheader("Verkaufte Spieler")

    trades_frame = pd.DataFrame(realized_trades)

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
# Spieler-Rohdaten
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

        st.write(
            "Erkannte Vereins-ID: "
            + str(get_team_id(inspect_player))
        )

        st.write(
            "Erkanntes Logo: "
            + str(
                get_player_logo(inspect_player, teams)
                or "nicht gefunden"
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
        st.info("Keine Spielerdaten vorhanden.")


# ---------------------------------------------------------
# Diagnosebereiche
# ---------------------------------------------------------

if not compact:
    with st.expander("Diagnose Vereine und Spielplan"):
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

        if st.button("Vereine und Spielplan neu laden"):
            st.session_state.pop(matches_key, None)
            st.rerun()

        if teams:
            st.write("**Erkannte Vereine:**")
            st.json(teams)
        else:
            st.write(
                "Es wurden keine Vereine erkannt. "
                "Bitte die Rohdaten unten prüfen."
            )

        if next_matches:
            st.write("**Nächste Spiele je Verein:**")
            st.json(next_matches)

        if matches_info["competition_sources"]:
            st.write("**Wettbewerbsdaten:**")

            for source in matches_info[
                "competition_sources"
            ]:
                with st.expander(source["path"]):
                    st.json(source["data"])

        if matches_info["match_sources"]:
            st.write("**Spielplandaten:**")

            for source in matches_info["match_sources"]:
                with st.expander(source["path"]):
                    st.json(source["data"])

        if matches_info["competition_errors"]:
            st.write("**Fehler Wettbewerb:**")
            st.write(matches_info["competition_errors"])

        if matches_info["match_errors"]:
            st.write("**Fehler Spielplan:**")
            st.write(matches_info["match_errors"])

    with st.expander(
        "Alle Daten zu diesem Manager"
    ):
        st.write(
            "Eigene Benutzer-ID: "
            + str(
                getattr(
                    api,
                    "own_user_id",
                    "unbekannt",
                )
            )
        )

        st.write(
            "Ausgewählte Manager-ID: "
            + str(selected_manager_id)
        )

        st.write(
            "Budgetquelle: "
            + str(
                own_budget_source
                or "nicht gefunden"
            )
        )

        st.write(
            "Quelle für prft: "
            + str(prft_source or "nicht gefunden")
        )

        if st.button("Manager-Daten laden"):
            with st.spinner(
                "Endpunkte werden getestet …"
            ):
                (
                    manager_sources,
                    manager_errors,
                ) = api.explore_manager(
                    league_id,
                    selected_manager_id,
                )

            st.session_state[
                "manager_sources"
            ] = manager_sources

            st.session_state[
                "manager_errors"
            ] = manager_errors

        manager_sources = st.session_state.get(
            "manager_sources",
            [],
        )

        manager_errors = st.session_state.get(
            "manager_errors",
            [],
        )

        if manager_sources:
            st.success(
                f"{len(manager_sources)} Endpunkte "
                "haben geantwortet."
            )

            for source in manager_sources:
                with st.expander(source["path"]):
                    fields = flatten_fields(
                        source["data"]
                    )

                    if fields:
                        st.dataframe(
                            pd.DataFrame(fields),
                            use_container_width=True,
                            hide_index=True,
                            height=350,
                        )

                    st.write("**Rohdaten:**")
                    st.json(source["data"])

        if manager_errors:
            with st.expander(
                "Endpunkte ohne Antwort"
            ):
                st.write(manager_errors)

    with st.expander(
        "Diagnose der Transferquellen"
    ):
        if feed_samples:
            for sample in feed_samples:
                with st.expander(
                    sample["Quelle"]
                ):
                    st.json(sample["Daten"])
        else:
            st.write(
                "Keine Transferquelle wurde geladen."
            )
