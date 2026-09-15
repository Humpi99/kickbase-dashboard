"""
Development-Bereich für das Kickbase-Dashboard.

Untersucht die Kickbase-API, um für jeden Manager
automatisch die Bonuskriterien ableiten zu können.

Untersuchte Bereiche:
- Spieltagsergebnisse je Manager (Punkte pro Spieltag)
- Einzelspieler-Punkte je Spieltag
- MVP-Daten
- Transferhistorie
"""

import json
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# Seiteneinstellungen
# ---------------------------------------------------------

st.set_page_config(
    page_title="Kickbase Development",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------
# Bonusregeln als Referenz
# ---------------------------------------------------------

BONUS_RULES = [
    {
        "id": "daily_login",
        "category": "Allgemein",
        "description": "Tägliche Anmeldung",
        "bonus": 100_000,
        "needed_data": "Anzahl Tage seit 10.08.2026",
        "api_hint": "Unklar, ob die API das liefert",
    },
    {
        "id": "mvp",
        "category": "Spieltag",
        "description": "MVP des Spieltags",
        "bonus": 1_000_000,
        "needed_data": (
            "Welcher Spieler war MVP an welchem "
            "Spieltag und bei welchem Manager "
            "war er aufgestellt?"
        ),
        "api_hint": (
            "Möglicherweise in matchday- oder "
            "competition-Endpunkten"
        ),
    },
    {
        "id": "matchday_winner",
        "category": "Spieltag",
        "description": "Spieltagssieger",
        "bonus": 1_000_000,
        "needed_data": (
            "Welcher Manager hatte die meisten "
            "Punkte an welchem Spieltag?"
        ),
        "api_hint": (
            "Manager-Saisondaten mit Spieltag-"
            "Einzelergebnissen (mdp-Feld)"
        ),
    },
    {
        "id": "player_200",
        "category": "Spieler-Punkte",
        "description": "200+ Punkte für einen Spieler",
        "bonus": 100_000,
        "needed_data": (
            "Punkte je Spieler je Spieltag, "
            "aufgestellt bei welchem Manager"
        ),
        "api_hint": (
            "Möglicherweise in matchday-Detail- "
            "oder Lineup-Endpunkten"
        ),
    },
    {
        "id": "player_300",
        "category": "Spieler-Punkte",
        "description": "300+ Punkte für einen Spieler",
        "bonus": 500_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "player_400",
        "category": "Spieler-Punkte",
        "description": "400+ Punkte für einen Spieler",
        "bonus": 1_000_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "player_500",
        "category": "Spieler-Punkte",
        "description": "500+ Punkte für einen Spieler",
        "bonus": 2_000_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "team_1000",
        "category": "Team-Punkte",
        "description": "1.000+ Punkte ganzes Team",
        "bonus": 250_000,
        "needed_data": (
            "Gesamtpunkte des Managers je Spieltag"
        ),
        "api_hint": (
            "mdp-Feld in den Spieltag-Einträgen "
            "der Manager-Saisondaten"
        ),
    },
    {
        "id": "team_1500",
        "category": "Team-Punkte",
        "description": "1.500+ Punkte ganzes Team",
        "bonus": 1_000_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "team_2000",
        "category": "Team-Punkte",
        "description": "2.000+ Punkte ganzes Team",
        "bonus": 2_000_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "transfer_3m",
        "category": "Transfergewinn",
        "description": "3 Mio. Transfergewinn",
        "bonus": 250_000,
        "needed_data": (
            "Transferhistorie: Kauf- und "
            "Verkaufspreis je Spieler"
        ),
        "api_hint": (
            "Manager-Transfer- oder "
            "Activities-Endpunkte"
        ),
    },
    {
        "id": "transfer_5m",
        "category": "Transfergewinn",
        "description": "5 Mio. Transfergewinn",
        "bonus": 500_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "transfer_10m",
        "category": "Transfergewinn",
        "description": "10 Mio. Transfergewinn",
        "bonus": 1_000_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
    {
        "id": "transfer_25m",
        "category": "Transfergewinn",
        "description": "25 Mio. Transfergewinn",
        "bonus": 2_000_000,
        "needed_data": "Wie oben",
        "api_hint": "Wie oben",
    },
]


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

DEV_STYLE = """
<style>
:root {
    --dev-text: #1c1c1c;
    --dev-muted: #686e74;
    --dev-border: #e0e3e6;
    --dev-background: #ffffff;
    --dev-header-bg: #f2f4f7;
    --dev-header-text: #30363d;
    --dev-success: #08783a;
    --dev-warning: #b35c00;
    --dev-error: #c62828;
    --dev-code-bg: #f6f7f8;
    --dev-highlight: #eaf6ef;
}

.dev-status-found {
    color: var(--dev-success);
    font-weight: 700;
}

.dev-status-missing {
    color: var(--dev-error);
    font-weight: 700;
}

.dev-status-partial {
    color: var(--dev-warning);
    font-weight: 700;
}

.dev-endpoint-path {
    padding: 0.5rem 0.7rem;
    margin: 0.3rem 0;
    border: 1px solid var(--dev-border);
    border-radius: 6px;
    background: var(--dev-code-bg);
    font-family: monospace;
    font-size: 0.78rem;
    overflow-wrap: anywhere;
}

.dev-data-table {
    width: 100%;
    border-collapse: collapse;
    color: var(--dev-text);
    background: var(--dev-background);
    font-size: 0.8rem;
    margin: 0.5rem 0;
}

.dev-data-table th {
    padding: 0.55rem;
    border: 1px solid var(--dev-border);
    background: var(--dev-header-bg);
    color: var(--dev-header-text);
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    text-align: left;
}

.dev-data-table td {
    padding: 0.5rem 0.55rem;
    border: 1px solid var(--dev-border);
    vertical-align: top;
}

.dev-highlight-row td {
    background: var(--dev-highlight);
}

html[data-theme="dark"],
body[data-theme="dark"],
[data-theme="dark"] {
    --dev-text: #ffffff;
    --dev-muted: #c5cad0;
    --dev-border: #464c54;
    --dev-background: #171b20;
    --dev-header-bg: #3b434d;
    --dev-header-text: #ffffff;
    --dev-success: #52d889;
    --dev-warning: #f0a830;
    --dev-error: #ff7474;
    --dev-code-bg: #22272e;
    --dev-highlight: #1e3028;
}
</style>
"""

st.markdown(
    DEV_STYLE,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

def first_value(data, keys, default=None):
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def to_number(value):
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_league_id(league):
    value = first_value(
        league,
        ["id", "i", "leagueId", "li"],
        "",
    )

    return str(value) if value else ""


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

    return str(value) if value else ""


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


def find_manager_list(value, depth=0):
    if depth > 8:
        return []

    if isinstance(value, list):
        managers = [
            item
            for item in value
            if looks_like_manager(item)
        ]

        if managers:
            return managers

        for item in value:
            result = find_manager_list(
                item,
                depth + 1,
            )

            if result:
                return result

    elif isinstance(value, dict):
        for key in [
            "us",
            "users",
            "managers",
            "ranking",
            "items",
            "it",
        ]:
            if key in value:
                result = find_manager_list(
                    value[key],
                    depth + 1,
                )

                if result:
                    return result

        for key, nested in value.items():
            if key in {
                "tkn",
                "token",
                "accessToken",
            }:
                continue

            result = find_manager_list(
                nested,
                depth + 1,
            )

            if result:
                return result

    return []


def collect_dictionaries(data, depth=0):
    found = []

    if depth > 10:
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


def safe_json(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception:
        return str(value)


def format_bonus(value):
    if value >= 1_000_000:
        amount = value / 1_000_000
        text = f"{amount:,.2f}"
        text = text.replace(",", "X")
        text = text.replace(".", ",")
        text = text.replace("X", ".")

        return f"{text} Mio. €"

    amount = value / 1_000
    text = f"{amount:,.0f}"
    text = text.replace(",", ".")

    return f"{text} k €"


# ---------------------------------------------------------
# API-Endpunkte laden
# ---------------------------------------------------------

def try_endpoint(api, path):
    """Ruft einen Endpunkt auf und gibt Ergebnis zurück."""
    try:
        data = api.get(path)

        return {
            "path": path,
            "success": True,
            "data": data,
            "error": None,
        }

    except Exception as error:
        return {
            "path": path,
            "success": False,
            "data": None,
            "error": str(error),
        }


def load_manager_bonus_data(
    api,
    league_id,
    manager_id,
):
    """Lädt alle bonusrelevanten Endpunkte eines Managers."""
    base = (
        f"/v4/leagues/{league_id}"
        f"/managers/{manager_id}"
    )

    user_base = (
        f"/v4/leagues/{league_id}"
        f"/users/{manager_id}"
    )

    # Gruppe 1: Spieltagsergebnisse
    matchday_paths = [
        f"{base}/performance",
        f"{base}/dashboard",
        f"{base}/points",
        f"{base}/history",
        base,
        f"{user_base}/stats",
        f"{user_base}/profile",
    ]

    # Gruppe 2: Transfers
    transfer_paths = [
        f"{base}/transfers",
        f"{base}/activities",
        f"{base}/activitiesFeed",
        f"{base}/feed",
    ]

    # Gruppe 3: Spieltag-Details
    matchday_detail_paths = [
        f"/v4/leagues/{league_id}/matchdays",
        f"/v4/leagues/{league_id}/matchday",
        f"/v4/competitions/1/matchdays",
        f"/v4/competitions/1/matchday",
    ]

    # Gruppe 4: Liga-Feed für MVP
    league_feed_paths = [
        f"/v4/leagues/{league_id}/activitiesFeed",
        f"/v4/leagues/{league_id}/activities",
        f"/v4/leagues/{league_id}/feed",
    ]

    results = {
        "matchday": [],
        "transfers": [],
        "matchday_details": [],
        "league_feed": [],
    }

    for path in matchday_paths:
        result = try_endpoint(api, path)

        if result["success"]:
            results["matchday"].append(result)

    for path in transfer_paths:
        result = try_endpoint(api, path)

        if result["success"]:
            results["transfers"].append(result)

    for path in matchday_detail_paths:
        result = try_endpoint(api, path)

        if result["success"]:
            results["matchday_details"].append(
                result
            )

    for path in league_feed_paths:
        result = try_endpoint(api, path)

        if result["success"]:
            results["league_feed"].append(result)

    return results


# ---------------------------------------------------------
# Spieltagsdaten auswerten
# ---------------------------------------------------------

def extract_current_season_matchdays(data, depth=0):
    """
    Sucht den aktuellen Saisonblock und gibt
    nur dessen Spieltage zurück.
    """
    if depth > 10:
        return []

    if isinstance(data, dict):
        season_name = data.get("sn")
        season_id = data.get("sid")

        if season_name is not None or season_id is not None:
            now = datetime.now()

            start_year = (
                now.year
                if now.month >= 7
                else now.year - 1
            )

            expected_name = (
                f"{start_year}/{start_year + 1}"
            )

            is_current = (
                str(season_name) == expected_name
            )

            if not is_current:
                return []

            inner_list = data.get("it", [])

            if isinstance(inner_list, list):
                matchdays = []

                for entry in inner_list:
                    if not isinstance(entry, dict):
                        continue

                    day = entry.get("day")
                    mdp = to_number(entry.get("mdp"))

                    if day is None:
                        continue

                    matchdays.append(
                        {
                            "day": day,
                            "points": mdp,
                            "current": entry.get("cur"),
                            "date": entry.get("md"),
                            "tw": entry.get("tw"),
                        }
                    )

                if matchdays:
                    return matchdays

        for value in data.values():
            result = extract_current_season_matchdays(
                value,
                depth + 1,
            )

            if result:
                return result

    elif isinstance(data, list):
        for item in data:
            result = extract_current_season_matchdays(
                item,
                depth + 1,
            )

            if result:
                return result

    return []


def deduplicate_matchdays(matchdays):
    """Entfernt doppelte Spieltage."""
    by_day = {}

    for entry in matchdays:
        day = entry["day"]
        points = entry["points"]

        if day not in by_day or (
            points is not None
            and points != 0
        ):
            by_day[day] = entry

    return sorted(
        by_day.values(),
        key=lambda entry: (
            to_number(entry["day"]) or 0
        ),
    )


def extract_transfer_entries(data, depth=0):
    """Sucht Transfereinträge in den Daten."""
    transfers = []

    if depth > 10:
        return transfers

    if isinstance(data, dict):
        has_transfer_marker = any(
            key in data
            for key in [
                "buyPrice",
                "sellPrice",
                "profit",
                "transferType",
                "type",
                "trp",
                "sp",
                "bp",
                "prft",
            ]
        )

        if has_transfer_marker:
            transfers.append(data)

        for value in data.values():
            transfers.extend(
                extract_transfer_entries(
                    value,
                    depth + 1,
                )
            )

    elif isinstance(data, list):
        for item in data:
            transfers.extend(
                extract_transfer_entries(
                    item,
                    depth + 1,
                )
            )

    return transfers


def search_for_mvp(data, depth=0):
    """Sucht nach MVP-Hinweisen in den Daten."""
    hints = []

    if depth > 10:
        return hints

    if isinstance(data, dict):
        for key in data.keys():
            lower_key = str(key).lower()

            if "mvp" in lower_key:
                hints.append(
                    {
                        "key": key,
                        "value": data[key],
                        "path": key,
                    }
                )

        for key, value in data.items():
            nested = search_for_mvp(
                value,
                depth + 1,
            )

            for hint in nested:
                hint["path"] = (
                    f"{key}.{hint['path']}"
                )

            hints.extend(nested)

    elif isinstance(data, list):
        for index, item in enumerate(data):
            nested = search_for_mvp(
                item,
                depth + 1,
            )

            for hint in nested:
                hint["path"] = (
                    f"[{index}].{hint['path']}"
                )

            hints.extend(nested)

    return hints


# ---------------------------------------------------------
# Anmeldung prüfen
# ---------------------------------------------------------

st.title("🛠️ Development")

st.markdown(
    "Diese Seite untersucht die Kickbase-API, um "
    "herauszufinden, welche Bonuskriterien automatisch "
    "abgeleitet werden können."
)

if not st.session_state.get("logged_in"):
    st.warning(
        "Du bist noch nicht angemeldet. "
        "Öffne zuerst die Hauptseite und melde dich an."
    )

    st.stop()

api = st.session_state.get("api")
leagues = st.session_state.get("leagues", [])

if api is None or not leagues:
    st.error(
        "Anmeldedaten nicht gefunden. "
        "Bitte auf der Hauptseite neu anmelden."
    )

    st.stop()


# ---------------------------------------------------------
# Liga und Manager auswählen
# ---------------------------------------------------------

st.subheader("1. Liga und Manager auswählen")

league_index = st.selectbox(
    "Liga auswählen",
    range(len(leagues)),
    format_func=lambda index: (
        get_league_name(leagues[index])
    ),
    key="dev_league_index",
)

selected_league = leagues[league_index]
league_id = get_league_id(selected_league)

manager_cache_key = (
    f"dev_managers_{league_id}"
)

if manager_cache_key not in st.session_state:
    with st.spinner(
        "Manager werden geladen …"
    ):
        try:
            sources, _ = api.get_ranking(
                league_id
            )

        except Exception:
            sources = []

        managers = []

        for source in sources:
            managers = find_manager_list(
                source.get("data")
            )

            if managers:
                break

        st.session_state[manager_cache_key] = (
            managers
        )

managers = st.session_state[manager_cache_key]

if not managers:
    st.error(
        "Es konnten keine Manager geladen werden."
    )

    st.stop()

manager_lookup = {
    get_manager_id(manager): manager
    for manager in managers
}

manager_ids = list(manager_lookup.keys())

selected_manager_id = st.selectbox(
    "Manager auswählen",
    manager_ids,
    format_func=lambda manager_id: (
        get_manager_name(
            manager_lookup[manager_id]
        )
    ),
    key="dev_manager_id",
)

selected_manager_name = get_manager_name(
    manager_lookup[selected_manager_id]
)


# ---------------------------------------------------------
# Bonusregeln anzeigen
# ---------------------------------------------------------

st.subheader("2. Bonusregeln")

rules_rows = []
current_category = None

for rule in BONUS_RULES:
    if rule["category"] != current_category:
        current_category = rule["category"]

        rules_rows.append(
            "<tr style='background:var(--dev-header-bg);'>"
            f"<td colspan='4'>"
            f"<strong>{escape(current_category)}</strong>"
            "</td>"
            "</tr>"
        )

    rules_rows.append(
        "<tr>"
        f"<td>{escape(rule['description'])}</td>"
        f"<td>{escape(format_bonus(rule['bonus']))}</td>"
        f"<td style='font-size:0.75rem;"
        f"color:var(--dev-muted);'>"
        f"{escape(rule['needed_data'])}</td>"
        f"<td style='font-size:0.75rem;"
        f"color:var(--dev-muted);'>"
        f"{escape(rule['api_hint'])}</td>"
        "</tr>"
    )

st.markdown(
    "<table class='dev-data-table'>"
    "<thead><tr>"
    "<th>Erfolg</th>"
    "<th>Bonus</th>"
    "<th>Benötigte Daten</th>"
    "<th>API-Vermutung</th>"
    "</tr></thead>"
    f"<tbody>{''.join(rules_rows)}</tbody>"
    "</table>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# API-Daten laden
# ---------------------------------------------------------

st.subheader(
    f"3. API-Daten für "
    f"{escape(selected_manager_name)}"
)

data_cache_key = (
    f"dev_bonus_data_v1_"
    f"{league_id}_{selected_manager_id}"
)

if st.button(
    f"Bonusdaten für "
    f"{selected_manager_name} laden",
    key="load_bonus_data",
    type="primary",
    use_container_width=True,
):
    st.session_state.pop(
        data_cache_key,
        None,
    )

if data_cache_key not in st.session_state:
    with st.spinner(
        "Bonusrelevante API-Endpunkte werden "
        "untersucht …"
    ):
        results = load_manager_bonus_data(
            api,
            league_id,
            selected_manager_id,
        )

    st.session_state[data_cache_key] = results

else:
    results = st.session_state[data_cache_key]


# ---------------------------------------------------------
# Spieltag-Punkte auswerten
# ---------------------------------------------------------

st.markdown("### Spieltag-Punkte (Team-Punkte-Boni)")

all_matchdays = []

for result in results["matchday"]:
    found = extract_current_season_matchdays(
        result["data"]
    )

    if found:
        all_matchdays = found
        break

unique_matchdays = deduplicate_matchdays(
    all_matchdays
)

if unique_matchdays:
    played_matchdays = [
        entry
        for entry in unique_matchdays
        if entry["points"] is not None
        and entry["points"] != 0
    ]

    st.success(
        f"{len(played_matchdays)} Spieltage der "
        f"aktuellen Saison mit Punkten gefunden"
    )

    matchday_rows = []

    team_1000_count = 0
    team_1500_count = 0
    team_2000_count = 0
    matchday_wins = 0

    for entry in unique_matchdays:
        points = entry["points"]

        if points is None:
            continue

        badges = []

        if points >= 2000:
            badges.append("🏆 2.000+")
            team_2000_count += 1

        if points >= 1500:
            if "🏆 2.000+" not in badges:
                badges.append("🥇 1.500+")

            team_1500_count += 1

        if points >= 1000:
            if not badges:
                badges.append("✅ 1.000+")

            team_1000_count += 1

        is_winner = entry.get("tw") is True

        if is_winner:
            badges.append("⭐ Spieltagssieger")
            matchday_wins += 1

        highlight = (
            "dev-highlight-row"
            if badges
            else ""
        )

        matchday_rows.append(
            f"<tr class='{highlight}'>"
            f"<td>Spieltag {entry['day']}</td>"
            f"<td>{points:.0f}</td>"
            f"<td>{'Ja' if is_winner else '—'}</td>"
            f"<td>{' '.join(badges)}</td>"
            f"<td style='font-size:0.72rem;"
            f"color:var(--dev-muted);'>"
            f"{entry.get('date', '—')}</td>"
            "</tr>"
        )

    st.markdown(
        "<table class='dev-data-table'>"
        "<thead><tr>"
        "<th>Spieltag</th>"
        "<th>Punkte</th>"
        "<th>Sieger</th>"
        "<th>Bonus-Schwellen</th>"
        "<th>Datum</th>"
        "</tr></thead>"
        f"<tbody>{''.join(matchday_rows)}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )

    st.markdown("**Automatisch ermittelte Boni:**")

    auto_rows = [
        f"- 1.000+ Team-Punkte: **{team_1000_count}×** → "
        f"**{format_bonus(team_1000_count * 250_000)}**",
        f"- 1.500+ Team-Punkte: **{team_1500_count}×** → "
        f"**{format_bonus(team_1500_count * 1_000_000)}**",
        f"- 2.000+ Team-Punkte: **{team_2000_count}×** → "
        f"**{format_bonus(team_2000_count * 2_000_000)}**",
        f"- Spieltagssieger (tw=true): **{matchday_wins}×** → "
        f"**{format_bonus(matchday_wins * 1_000_000)}**",
    ]

    st.markdown("\n".join(auto_rows))

else:
    st.warning(
        "Keine Spieltage der aktuellen Saison gefunden. "
        "Klicke oben auf den Lade-Button."
    )

# ---------------------------------------------------------
# Spieltagssieger ermitteln
# ---------------------------------------------------------

st.markdown("### Spieltagssieger aller Manager")

st.info(
    "Die Spieltagssieger werden direkt aus dem Feld "
    "tw=true der aktuellen Saison abgeleitet. Klicke "
    "auf den Button, um alle Manager zu laden."
)

if st.button(
    "Spieltagssieger aller Manager laden",
    key="load_all_matchdays",
    use_container_width=True,
):
    progress = st.progress(
        0.0,
        text="Spieltage aller Manager werden geladen …",
    )

    all_manager_results = {}

    for index, manager_id in enumerate(
        manager_ids
    ):
        manager_name = get_manager_name(
            manager_lookup[manager_id]
        )

        base = (
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}"
        )

        paths = [
            f"{base}/performance",
            f"{base}/dashboard",
            base,
        ]

        matchdays = []

        for path in paths:
            result = try_endpoint(api, path)

            if result["success"]:
                found = extract_current_season_matchdays(
                    result["data"]
                )

                if found:
                    matchdays = found
                    break

        wins = sum(
            1
            for entry in matchdays
            if entry.get("tw") is True
        )

        all_manager_results[manager_id] = {
            "name": manager_name,
            "matchdays": matchdays,
            "wins": wins,
        }

        progress.progress(
            (index + 1) / len(manager_ids),
            text=(
                f"Manager werden geladen … "
                f"{index + 1} von {len(manager_ids)}"
            ),
        )

    progress.empty()

    winner_rows = []

    for manager_id in manager_ids:
        info = all_manager_results[manager_id]

        is_selected = (
            manager_id == selected_manager_id
        )

        highlight = (
            "dev-highlight-row"
            if is_selected
            else ""
        )

        bonus = format_bonus(
            info["wins"] * 1_000_000
        )

        winner_rows.append(
            f"<tr class='{highlight}'>"
            f"<td><strong>"
            f"{escape(info['name'])}"
            f"</strong></td>"
            f"<td>{info['wins']}</td>"
            f"<td>{escape(bonus)}</td>"
            "</tr>"
        )

    st.markdown(
        "<table class='dev-data-table'>"
        "<thead><tr>"
        "<th>Manager</th>"
        "<th>Spieltage gewonnen</th>"
        "<th>Bonus</th>"
        "</tr></thead>"
        f"<tbody>{''.join(winner_rows)}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Transferhistorie
# ---------------------------------------------------------

st.markdown("### Transferhistorie")

all_transfers = []

for result in results["transfers"]:
    found = extract_transfer_entries(
        result["data"]
    )

    all_transfers.extend(found)

if all_transfers:
    st.success(
        f"{len(all_transfers)} mögliche "
        f"Transfereinträge gefunden"
    )

    with st.expander(
        f"Alle {len(all_transfers)} Transfereinträge "
        "anzeigen"
    ):
        for index, transfer in enumerate(
            all_transfers[:50],
            start=1,
        ):
            st.write(f"**Transfer {index}:**")
            st.json(transfer)

else:
    st.warning(
        "Keine Transfereinträge gefunden."
    )

    st.caption(
        "Klicke oben auf den Lade-Button, "
        "falls noch nicht geschehen."
    )


# ---------------------------------------------------------
# MVP-Suche
# ---------------------------------------------------------

st.markdown("### MVP-Daten")

all_mvp_hints = []

for result in results["matchday_details"]:
    found = search_for_mvp(
        result["data"]
    )

    for hint in found:
        hint["source"] = result["path"]

    all_mvp_hints.extend(found)

for result in results["league_feed"]:
    found = search_for_mvp(
        result["data"]
    )

    for hint in found:
        hint["source"] = result["path"]

    all_mvp_hints.extend(found)

if all_mvp_hints:
    st.success(
        f"{len(all_mvp_hints)} MVP-Hinweise gefunden"
    )

    for hint in all_mvp_hints[:20]:
        st.markdown(
            f"<div class='dev-endpoint-path'>"
            f"<strong>{escape(hint['source'])}</strong>"
            f" → {escape(hint['path'])}"
            "</div>",
            unsafe_allow_html=True,
        )

        st.json(hint["value"])

else:
    st.warning(
        "Keine MVP-Felder in den untersuchten "
        "Endpunkten gefunden."
    )


# ---------------------------------------------------------
# Rohdaten aller Endpunkte
# ---------------------------------------------------------

st.markdown("### Alle geladenen Endpunkte")

for group_name, group_results in results.items():
    group_labels = {
        "matchday": "Spieltag-Endpunkte",
        "transfers": "Transfer-Endpunkte",
        "matchday_details": "Spieltag-Details",
        "league_feed": "Liga-Feed",
    }

    label = group_labels.get(
        group_name,
        group_name,
    )

    with st.expander(
        f"{label} ({len(group_results)} erfolgreich)"
    ):
        if not group_results:
            st.info(
                "Kein Endpunkt in dieser Gruppe "
                "hat Daten geliefert."
            )

        for result in group_results:
            st.markdown(
                f"<div class='dev-endpoint-path'>"
                f"{escape(result['path'])}"
                "</div>",
                unsafe_allow_html=True,
            )

            st.json(
                result["data"],
                expanded=False,
            )

            st.download_button(
                label=(
                    f"JSON herunterladen: "
                    f"{result['path']}"
                ),
                data=safe_json(
                    result["data"]
                ),
                file_name=(
                    f"dev_{group_name}_"
                    f"{abs(hash(result['path']))}"
                    ".json"
                ),
                mime="application/json",
                key=(
                    f"dev_download_"
                    f"{group_name}_"
                    f"{abs(hash(result['path']))}"
                ),
                use_container_width=True,
            )
