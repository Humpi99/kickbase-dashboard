"""
Diagnoseseite für ligaunabhängige Kickbase-Spielerdaten.

Die Seite untersucht verschiedene Spieler-Endpunkte und sucht
automatisch nach möglichen Feldern zur Startelfwahrscheinlichkeit.
"""

import json
from html import escape

import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# Seiteneinstellungen
# ---------------------------------------------------------

st.set_page_config(
    page_title="Kickbase Spielerdiagnose",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

APP_STYLE = """
<style>
:root {
    --diag-text: #1c1c1c;
    --diag-muted: #666d74;
    --diag-border: #dfe3e6;
    --diag-background: #ffffff;
    --diag-highlight: #fff4cc;
    --diag-highlight-border: #d99b00;
    --diag-success: #08783a;
    --diag-error: #c62828;
    --diag-code-background: #f6f7f8;
}

.diag-info {
    padding: 0.9rem 1rem;
    margin: 0.7rem 0 1rem;
    border: 1px solid var(--diag-border);
    border-radius: 8px;
    background: var(--diag-background);
    color: var(--diag-text);
}

.diag-warning {
    padding: 0.9rem 1rem;
    margin: 0.7rem 0 1rem;
    border-left: 4px solid var(--diag-highlight-border);
    border-radius: 6px;
    background: var(--diag-highlight);
    color: #3d3000;
}

.diag-success {
    color: var(--diag-success);
    font-weight: 700;
}

.diag-error {
    color: var(--diag-error);
    font-weight: 700;
}

.diag-path {
    padding: 0.65rem 0.8rem;
    margin: 0.4rem 0;
    border: 1px solid var(--diag-border);
    border-radius: 6px;
    background: var(--diag-code-background);
    color: var(--diag-text);
    font-family: monospace;
    overflow-wrap: anywhere;
}

html[data-theme="dark"],
body[data-theme="dark"],
[data-theme="dark"] {
    --diag-text: #ffffff;
    --diag-muted: #c4c9ce;
    --diag-border: #444b53;
    --diag-background: #191d22;
    --diag-highlight: #4b3b12;
    --diag-highlight-border: #e3ad31;
    --diag-success: #57d68d;
    --diag-error: #ff7777;
    --diag-code-background: #22272e;
}

html[data-theme="dark"] .diag-warning,
body[data-theme="dark"] .diag-warning,
[data-theme="dark"] .diag-warning {
    color: #fff0bd;
}

@media (max-width: 640px) {
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 2rem !important;
    }
}
</style>
"""

st.markdown(
    APP_STYLE,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Grundeinstellungen
# ---------------------------------------------------------

MAX_DEPTH = 12

SEARCH_TERMS = [
    "lineup",
    "line_up",
    "starting",
    "starter",
    "startelf",
    "probability",
    "prob",
    "prediction",
    "predict",
    "forecast",
    "expected",
    "expectation",
    "likelihood",
    "chance",
    "formation",
    "status",
    "s11",
    "start11",
    "starting11",
    "startingeleven",
    "aufstellung",
    "wahrscheinlichkeit",
    "prognose",
    "sicher",
    "erwartet",
    "unsicher",
    "unwahrscheinlich",
    "ausgeschlossen",
]

KNOWN_CATEGORY_TERMS = [
    "sicher",
    "erwartet",
    "unsicher",
    "unwahrscheinlich",
    "ausgeschlossen",
]


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


def normalize_text(value):
    """Bereitet einen Wert für die Suche auf."""
    if value is None:
        return ""

    try:
        return str(value).strip().lower()
    except Exception:
        return ""


def safe_json_text(value):
    """Wandelt Daten sicher in formatierten JSON-Text um."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception:
        return str(value)


def clear_diagnosis_results():
    """Entfernt alte Diagnoseergebnisse."""
    st.session_state.pop(
        "player_diagnosis_results",
        None,
    )

    st.session_state.pop(
        "player_diagnosis_player_id",
        None,
    )

    st.session_state.pop(
        "player_diagnosis_player_name",
        None,
    )


# ---------------------------------------------------------
# Liga erkennen
# ---------------------------------------------------------

def get_league_id(league):
    value = first_value(
        league,
        [
            "id",
            "i",
            "leagueId",
            "li",
        ],
        "",
    )

    return str(value) if value is not None else ""


def get_league_name(league):
    return str(
        first_value(
            league,
            [
                "name",
                "n",
                "leagueName",
                "ln",
            ],
            "Unbekannte Liga",
        )
    )


# ---------------------------------------------------------
# Manager erkennen
# ---------------------------------------------------------

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


def looks_like_manager(item):
    """Prüft, ob ein Dictionary wahrscheinlich ein Manager ist."""
    if not isinstance(item, dict):
        return False

    manager_id = get_manager_id(item)
    manager_name = get_manager_name(item)

    if not manager_id:
        return False

    if manager_name == "Unbekannter Manager":
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
    """Sucht rekursiv nach einer Managerliste."""
    if depth > MAX_DEPTH:
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
        preferred_keys = [
            "us",
            "users",
            "managers",
            "ranking",
            "items",
            "it",
        ]

        for key in preferred_keys:
            if key not in value:
                continue

            result = find_manager_list(
                value[key],
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

            result = find_manager_list(
                nested_value,
                depth + 1,
            )

            if result:
                return result

    return []


def has_own_manager_marker(manager):
    """Prüft, ob ein Manager als eigener Manager markiert ist."""
    if not isinstance(manager, dict):
        return False

    marker_keys = [
        "me",
        "isMe",
        "isOwn",
        "own",
        "currentUser",
        "isCurrentUser",
    ]

    for key in marker_keys:
        value = manager.get(key)

        if value is True or value == 1 or value == "1":
            return True

    return False


def resolve_own_manager_id(api, managers):
    """Ermittelt den eigenen Manager."""
    own_user_id = getattr(
        api,
        "own_user_id",
        None,
    )

    if own_user_id is not None:
        own_user_id = str(own_user_id)

        for manager in managers:
            if get_manager_id(manager) == own_user_id:
                return own_user_id

    for manager in managers:
        if has_own_manager_marker(manager):
            return get_manager_id(manager)

    return None


def order_managers(managers, own_manager_id):
    """Zeigt den eigenen Manager zuerst."""
    if not own_manager_id:
        return managers

    return sorted(
        managers,
        key=lambda manager: (
            0
            if get_manager_id(manager)
            == str(own_manager_id)
            else 1,
            get_manager_name(manager).lower(),
        ),
    )


# ---------------------------------------------------------
# Spieler erkennen
# ---------------------------------------------------------

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
        [
            "firstName",
            "fn",
            "pfn",
        ],
        "",
    )

    last_name = first_value(
        player,
        [
            "lastName",
            "ln",
            "pln",
        ],
        "",
    )

    full_name = (
        f"{first_name} {last_name}".strip()
    )

    if full_name:
        return full_name

    name = first_value(
        player,
        [
            "name",
            "n",
            "playerName",
            "pn",
        ],
    )

    return str(name) if name else "Unbekannter Spieler"


def get_market_value(player):
    return to_number(
        first_value(
            player,
            [
                "mv",
                "marketValue",
                "currentValue",
                "cv",
            ],
        )
    )


def get_lineup_slot(player):
    """Liest den Kaderplatz der aktuellen Kickbase-Aufstellung."""
    if not isinstance(player, dict):
        return None

    number = to_number(
        player.get("lo")
    )

    if number is None:
        return None

    if 0 <= number <= 10:
        return int(number)

    return None


def is_in_lineup(player):
    return get_lineup_slot(player) is not None


def collect_dictionaries(value, depth=0):
    """Sammelt alle verschachtelten Dictionaries."""
    dictionaries = []

    if depth > MAX_DEPTH:
        return dictionaries

    if isinstance(value, dict):
        dictionaries.append(value)

        for nested_value in value.values():
            dictionaries.extend(
                collect_dictionaries(
                    nested_value,
                    depth + 1,
                )
            )

    elif isinstance(value, list):
        for item in value:
            dictionaries.extend(
                collect_dictionaries(
                    item,
                    depth + 1,
                )
            )

    return dictionaries


def find_players(data):
    """Erkennt Spieler in den Kaderdaten."""
    candidates = []

    for item in collect_dictionaries(data):
        player_id = get_player_id(item)
        market_value = get_market_value(item)

        if player_id and market_value is not None:
            candidates.append(item)

    players_by_id = {}

    for player in candidates:
        player_id = get_player_id(player)
        current = players_by_id.get(player_id)

        if current is None or len(player) > len(current):
            players_by_id[player_id] = player

    return sorted(
        players_by_id.values(),
        key=lambda player: (
            0 if is_in_lineup(player) else 1,
            (
                get_lineup_slot(player)
                if get_lineup_slot(player) is not None
                else 99
            ),
            get_player_name(player).lower(),
        ),
    )


# ---------------------------------------------------------
# API-Daten laden
# ---------------------------------------------------------

def load_managers(api, league_id):
    """Lädt die Manager der ausgewählten Liga."""
    try:
        sources, errors = api.get_ranking(
            league_id
        )
    except Exception as error:
        return [], [str(error)]

    managers = []

    for source in sources:
        data = (
            source.get("data")
            if isinstance(source, dict)
            else source
        )

        managers = find_manager_list(data)

        if managers:
            break

    return managers, errors


def load_manager_players(
    api,
    league_id,
    manager_id,
):
    """Lädt den Kader eines Managers."""
    try:
        data = api.get_manager_squad(
            league_id,
            manager_id,
        )

        return find_players(data), None

    except Exception as error:
        return [], str(error)


def request_endpoint(api, path):
    """Ruft einen einzelnen API-Endpunkt auf."""
    try:
        response = api.get(path)

        return {
            "path": path,
            "success": True,
            "data": response,
            "error": None,
        }

    except Exception as error:
        return {
            "path": path,
            "success": False,
            "data": None,
            "error": str(error),
        }


def build_player_paths(
    league_id,
    player_id,
):
    """
    Erstellt die Endpunkte für die Diagnose.

    Die ersten Endpunkte sind ligaunabhängig.
    Der letzte Endpunkt dient als Vergleich.
    """
    return [
        {
            "name": "Spieler allgemein",
            "scope": "Ligaunabhängig",
            "path": (
                f"/v4/players/{player_id}"
            ),
        },
        {
            "name": "Bundesliga-Spieler",
            "scope": "Wettbewerbsbezogen",
            "path": (
                f"/v4/competitions/1"
                f"/players/{player_id}"
            ),
        },
        {
            "name": "Spieler in ausgewählter Liga",
            "scope": "Ligaabhängig",
            "path": (
                f"/v4/leagues/{league_id}"
                f"/players/{player_id}"
            ),
        },
    ]


def diagnose_player(
    api,
    league_id,
    player_id,
):
    """Ruft alle vorgesehenen Spieler-Endpunkte ab."""
    results = []

    for endpoint in build_player_paths(
        league_id,
        player_id,
    ):
        result = request_endpoint(
            api,
            endpoint["path"],
        )

        result["name"] = endpoint["name"]
        result["scope"] = endpoint["scope"]

        results.append(result)

    return results


# ---------------------------------------------------------
# Rohdaten durchsuchen
# ---------------------------------------------------------

def is_simple_value(value):
    return not isinstance(
        value,
        (
            dict,
            list,
            tuple,
            set,
        ),
    )


def flatten_api_data(
    value,
    path="$",
    depth=0,
):
    """Wandelt eine API-Antwort in durchsuchbare Zeilen um."""
    rows = []

    if depth > MAX_DEPTH:
        rows.append(
            {
                "Pfad": path,
                "Feld": "",
                "Wert": "[Maximale Suchtiefe erreicht]",
                "Datentyp": "Grenze",
            }
        )

        return rows

    if isinstance(value, dict):
        if not value:
            rows.append(
                {
                    "Pfad": path,
                    "Feld": "",
                    "Wert": "{}",
                    "Datentyp": "Dictionary",
                }
            )

        for key, nested_value in value.items():
            key_text = str(key)
            nested_path = (
                f"{path}.{key_text}"
            )

            if is_simple_value(nested_value):
                rows.append(
                    {
                        "Pfad": nested_path,
                        "Feld": key_text,
                        "Wert": nested_value,
                        "Datentyp": type(
                            nested_value
                        ).__name__,
                    }
                )
            else:
                rows.extend(
                    flatten_api_data(
                        nested_value,
                        nested_path,
                        depth + 1,
                    )
                )

    elif isinstance(value, list):
        if not value:
            rows.append(
                {
                    "Pfad": path,
                    "Feld": "",
                    "Wert": "[]",
                    "Datentyp": "Liste",
                }
            )

        for index, item in enumerate(value):
            nested_path = (
                f"{path}[{index}]"
            )

            if is_simple_value(item):
                rows.append(
                    {
                        "Pfad": nested_path,
                        "Feld": str(index),
                        "Wert": item,
                        "Datentyp": type(
                            item
                        ).__name__,
                    }
                )
            else:
                rows.extend(
                    flatten_api_data(
                        item,
                        nested_path,
                        depth + 1,
                    )
                )

    else:
        rows.append(
            {
                "Pfad": path,
                "Feld": "",
                "Wert": value,
                "Datentyp": type(
                    value
                ).__name__,
            }
        )

    return rows


def row_search_text(row):
    """Fasst eine Diagnosezeile für die Suche zusammen."""
    return " ".join(
        [
            normalize_text(row.get("Pfad")),
            normalize_text(row.get("Feld")),
            normalize_text(row.get("Wert")),
        ]
    )


def find_keyword_matches(
    rows,
    search_terms=None,
):
    """Sucht nach möglichen Startelffeldern."""
    if search_terms is None:
        search_terms = SEARCH_TERMS

    matches = []

    for row in rows:
        searchable = row_search_text(row)

        matched_terms = [
            term
            for term in search_terms
            if term in searchable
        ]

        if not matched_terms:
            continue

        result = dict(row)
        result["Treffer"] = ", ".join(
            sorted(set(matched_terms))
        )

        matches.append(result)

    return matches


def find_short_code_candidates(rows):
    """
    Zeigt zusätzlich kurze technische Felder.

    Die Kickbase-API verwendet häufig kurze Feldnamen.
    Deshalb können auch unbekannte Kürzel wichtig sein.
    """
    candidates = []

    ignored_fields = {
        "id",
        "i",
        "pi",
        "pid",
        "tid",
        "teamid",
        "mv",
        "mvgl",
        "tfhmvt",
        "fn",
        "ln",
        "pn",
        "pim",
        "tim",
        "pos",
        "position",
        "lo",
    }

    for row in rows:
        field = normalize_text(
            row.get("Feld")
        )

        if not field:
            continue

        if field in ignored_fields:
            continue

        if len(field) > 5:
            continue

        value = row.get("Wert")

        if isinstance(
            value,
            (
                bool,
                int,
                float,
                str,
            ),
        ) or value is None:
            candidates.append(dict(row))

    return candidates


def find_category_matches(rows):
    """Sucht direkt nach den sichtbaren Kategorien."""
    matches = []

    for row in rows:
        value_text = normalize_text(
            row.get("Wert")
        )

        category_hits = [
            category
            for category in KNOWN_CATEGORY_TERMS
            if category in value_text
        ]

        if not category_hits:
            continue

        result = dict(row)
        result["Kategorie"] = ", ".join(
            category_hits
        )

        matches.append(result)

    return matches


def create_result_overview(results):
    """Erstellt eine Übersicht über alle Endpunkte."""
    overview = []

    for result in results:
        rows = []

        if result["success"]:
            rows = flatten_api_data(
                result["data"]
            )

        matches = find_keyword_matches(rows)
        categories = find_category_matches(rows)

        overview.append(
            {
                "Endpunkt": result["name"],
                "Bereich": result["scope"],
                "Erreichbar": (
                    "Ja"
                    if result["success"]
                    else "Nein"
                ),
                "Felder": len(rows),
                "Mögliche Treffer": len(matches),
                "Kategorietreffer": len(categories),
                "Fehler": result["error"] or "",
            }
        )

    return overview


# ---------------------------------------------------------
# Anmeldung prüfen
# ---------------------------------------------------------

st.title("🔍 Spielerdiagnose")

st.markdown(
    """
    <div class="diag-info">
        Diese Seite sucht in verschiedenen Kickbase-Endpunkten
        nach möglichen Feldern für die Startelfwahrscheinlichkeit.
        Deine bestehende Dashboard-Datei wird dadurch nicht verändert.
    </div>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.get("logged_in"):
    st.warning(
        "Du bist noch nicht angemeldet. "
        "Öffne zuerst die Hauptseite des Dashboards, "
        "melde dich dort an und öffne danach wieder "
        "die Spielerdiagnose."
    )

    st.stop()

api = st.session_state.get("api")
leagues = st.session_state.get("leagues", [])

if api is None:
    st.error(
        "Die angemeldete Kickbase-Verbindung wurde "
        "nicht gefunden. Melde dich auf der Hauptseite "
        "bitte erneut an."
    )

    st.stop()

if not leagues:
    st.error(
        "Es wurden keine Ligen in der Anmeldung gefunden."
    )

    st.stop()


# ---------------------------------------------------------
# Liga auswählen
# ---------------------------------------------------------

st.subheader("1. Liga und Spieler auswählen")

league_index = st.selectbox(
    "Liga auswählen",
    range(len(leagues)),
    format_func=lambda index: (
        get_league_name(leagues[index])
    ),
    key="diagnosis_league_index",
    on_change=clear_diagnosis_results,
)

selected_league = leagues[league_index]
league_id = get_league_id(selected_league)

if not league_id:
    st.error(
        "Für diese Liga wurde keine Liga-ID gefunden."
    )

    st.stop()


# ---------------------------------------------------------
# Manager laden
# ---------------------------------------------------------

manager_cache_key = (
    f"diagnosis_managers_{league_id}"
)

if manager_cache_key not in st.session_state:
    with st.spinner(
        "Manager werden geladen …"
    ):
        managers, manager_errors = (
            load_managers(
                api,
                league_id,
            )
        )

        st.session_state[manager_cache_key] = {
            "managers": managers,
            "errors": manager_errors,
        }

manager_information = st.session_state[
    manager_cache_key
]

managers = manager_information["managers"]
manager_errors = manager_information["errors"]

if not managers:
    st.error(
        "Die Manager konnten nicht geladen werden."
    )

    if manager_errors:
        with st.expander("Fehlerdetails"):
            st.write(manager_errors)

    st.stop()

own_manager_id = resolve_own_manager_id(
    api,
    managers,
)

managers = order_managers(
    managers,
    own_manager_id,
)

manager_lookup = {
    get_manager_id(manager): manager
    for manager in managers
}

manager_ids = list(manager_lookup.keys())

default_manager_index = 0

if own_manager_id in manager_ids:
    default_manager_index = manager_ids.index(
        own_manager_id
    )

selected_manager_id = st.selectbox(
    "Manager auswählen",
    manager_ids,
    index=default_manager_index,
    format_func=lambda manager_id: (
        (
            "● "
            if manager_id == own_manager_id
            else ""
        )
        + get_manager_name(
            manager_lookup[manager_id]
        )
    ),
    key="diagnosis_manager_id",
    on_change=clear_diagnosis_results,
)


# ---------------------------------------------------------
# Kader laden
# ---------------------------------------------------------

squad_cache_key = (
    f"diagnosis_squad_"
    f"{league_id}_{selected_manager_id}"
)

if squad_cache_key not in st.session_state:
    with st.spinner(
        "Kader wird geladen …"
    ):
        players, squad_error = (
            load_manager_players(
                api,
                league_id,
                selected_manager_id,
            )
        )

        st.session_state[squad_cache_key] = {
            "players": players,
            "error": squad_error,
        }

squad_information = st.session_state[
    squad_cache_key
]

players = squad_information["players"]
squad_error = squad_information["error"]

if squad_error:
    st.error(
        "Der Kader konnte nicht geladen werden: "
        f"{squad_error}"
    )

    st.stop()

if not players:
    st.info(
        "Für diesen Manager wurden keine Spieler gefunden."
    )

    st.stop()

player_lookup = {
    get_player_id(player): player
    for player in players
}

player_ids = list(player_lookup.keys())

selected_player_id = st.selectbox(
    "Spieler auswählen",
    player_ids,
    format_func=lambda player_id: (
        (
            "S11 | "
            if is_in_lineup(
                player_lookup[player_id]
            )
            else "Trading | "
        )
        + get_player_name(
            player_lookup[player_id]
        )
    ),
    key="diagnosis_player_id",
    on_change=clear_diagnosis_results,
)

selected_player = player_lookup[
    selected_player_id
]

selected_player_name = get_player_name(
    selected_player
)

lineup_slot = get_lineup_slot(
    selected_player
)

left, middle, right = st.columns(3)

left.metric(
    "Spieler",
    selected_player_name,
)

middle.metric(
    "Spieler-ID",
    selected_player_id,
)

right.metric(
    "Aktueller Kaderstatus",
    (
        f"Start 11, Platz {lineup_slot}"
        if lineup_slot is not None
        else "Trading"
    ),
)


# ---------------------------------------------------------
# Diagnose starten
# ---------------------------------------------------------

st.subheader("2. API-Diagnose starten")

st.markdown(
    """
    <div class="diag-warning">
        Die Diagnose zeigt ausschließlich Daten an, die dein
        angemeldeter Kickbase-Zugang über die getesteten
        Spieler-Endpunkte zurückliefert. Die Daten werden nicht
        dauerhaft gespeichert.
    </div>
    """,
    unsafe_allow_html=True,
)

if st.button(
    "Spielerdaten untersuchen",
    type="primary",
    use_container_width=True,
    key="run_player_diagnosis",
):
    with st.spinner(
        "Spieler-Endpunkte werden untersucht …"
    ):
        results = diagnose_player(
            api,
            league_id,
            selected_player_id,
        )

    st.session_state[
        "player_diagnosis_results"
    ] = results

    st.session_state[
        "player_diagnosis_player_id"
    ] = selected_player_id

    st.session_state[
        "player_diagnosis_player_name"
    ] = selected_player_name


# ---------------------------------------------------------
# Ergebnisse anzeigen
# ---------------------------------------------------------

results = st.session_state.get(
    "player_diagnosis_results"
)

result_player_id = st.session_state.get(
    "player_diagnosis_player_id"
)

result_player_name = st.session_state.get(
    "player_diagnosis_player_name"
)

if not results:
    st.info(
        "Wähle einen Spieler aus und klicke auf "
        "„Spielerdaten untersuchen“."
    )

    st.stop()

if result_player_id != selected_player_id:
    st.info(
        "Die angezeigten Ergebnisse gehören noch zum "
        "vorher ausgewählten Spieler. Starte die Diagnose "
        "für den aktuellen Spieler erneut."
    )

    st.stop()

st.subheader(
    f"3. Ergebnisse für {result_player_name}"
)

overview = create_result_overview(
    results
)

st.dataframe(
    pd.DataFrame(overview),
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# Automatische Trefferübersicht
# ---------------------------------------------------------

all_matches = []
all_category_matches = []

for result in results:
    if not result["success"]:
        continue

    flattened_rows = flatten_api_data(
        result["data"]
    )

    keyword_matches = find_keyword_matches(
        flattened_rows
    )

    category_matches = find_category_matches(
        flattened_rows
    )

    for match in keyword_matches:
        match["Endpunkt"] = result["name"]
        match["Bereich"] = result["scope"]
        all_matches.append(match)

    for match in category_matches:
        match["Endpunkt"] = result["name"]
        match["Bereich"] = result["scope"]
        all_category_matches.append(match)

st.markdown("### Automatisch gefundene mögliche Felder")

if all_matches:
    match_columns = [
        "Endpunkt",
        "Bereich",
        "Pfad",
        "Feld",
        "Wert",
        "Datentyp",
        "Treffer",
    ]

    st.success(
        f"Es wurden {len(all_matches)} mögliche "
        "Treffer gefunden."
    )

    st.dataframe(
        pd.DataFrame(all_matches)[match_columns],
        use_container_width=True,
        hide_index=True,
        height=420,
    )
else:
    st.warning(
        "Über die bekannten Suchbegriffe wurde noch "
        "kein eindeutiges Feld gefunden. Prüfe deshalb "
        "weiter unten auch die kurzen technischen Felder "
        "und die vollständigen Rohdaten."
    )

st.markdown("### Direkte Treffer auf die fünf Kategorien")

if all_category_matches:
    category_columns = [
        "Endpunkt",
        "Bereich",
        "Pfad",
        "Feld",
        "Wert",
        "Datentyp",
        "Kategorie",
    ]

    st.success(
        "Mindestens eine der bekannten Kategorien wurde "
        "direkt in den API-Daten gefunden."
    )

    st.dataframe(
        pd.DataFrame(
            all_category_matches
        )[category_columns],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "Die Wörter „Sicher“, „Erwartet“, „Unsicher“, "
        "„Unwahrscheinlich“ und „Ausgeschlossen“ wurden "
        "nicht direkt gefunden. Kickbase verwendet dafür "
        "möglicherweise Zahlen oder kurze technische Kürzel."
    )


# ---------------------------------------------------------
# Einzelne Endpunkte anzeigen
# ---------------------------------------------------------

st.subheader("4. Endpunkte einzeln prüfen")

for endpoint_index, result in enumerate(
    results,
    start=1,
):
    title = (
        f"{endpoint_index}. {result['name']} "
        f"– {result['scope']}"
    )

    with st.expander(
        title,
        expanded=result["success"],
    ):
        st.markdown(
            "<div class='diag-path'>"
            f"{escape(result['path'])}"
            "</div>",
            unsafe_allow_html=True,
        )

        if not result["success"]:
            st.error(
                "Dieser Endpunkt konnte nicht geladen werden."
            )

            st.code(
                result["error"] or "Unbekannter Fehler",
                language="text",
            )

            continue

        st.markdown(
            "<span class='diag-success'>"
            "Endpunkt erfolgreich geladen"
            "</span>",
            unsafe_allow_html=True,
        )

        flattened_rows = flatten_api_data(
            result["data"]
        )

        keyword_matches = find_keyword_matches(
            flattened_rows
        )

        category_matches = find_category_matches(
            flattened_rows
        )

        short_code_candidates = (
            find_short_code_candidates(
                flattened_rows
            )
        )

        st.markdown("#### Mögliche Startelffelder")

        if keyword_matches:
            st.dataframe(
                pd.DataFrame(
                    keyword_matches
                )[
                    [
                        "Pfad",
                        "Feld",
                        "Wert",
                        "Datentyp",
                        "Treffer",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Keine Treffer mit den bekannten "
                "Suchbegriffen."
            )

        st.markdown("#### Direkte Kategorietreffer")

        if category_matches:
            st.dataframe(
                pd.DataFrame(
                    category_matches
                )[
                    [
                        "Pfad",
                        "Feld",
                        "Wert",
                        "Datentyp",
                        "Kategorie",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption(
                "Keine ausgeschriebenen Kategorien gefunden."
            )

        st.markdown("#### Kurze technische Felder")

        st.caption(
            "Dieser Bereich ist wichtig, weil Kickbase "
            "häufig sehr kurze Feldnamen verwendet."
        )

        if short_code_candidates:
            st.dataframe(
                pd.DataFrame(
                    short_code_candidates
                )[
                    [
                        "Pfad",
                        "Feld",
                        "Wert",
                        "Datentyp",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=350,
            )
        else:
            st.info(
                "Keine zusätzlichen kurzen Felder gefunden."
            )

        st.markdown("#### Alle flachen Felder")

        if flattened_rows:
            all_fields_frame = pd.DataFrame(
                flattened_rows
            )

            filter_text = st.text_input(
                "Felder und Werte durchsuchen",
                key=(
                    f"diagnosis_filter_"
                    f"{endpoint_index}"
                ),
                placeholder=(
                    "Zum Beispiel status, lineup, 1 oder 4"
                ),
            )

            if filter_text.strip():
                search_text = normalize_text(
                    filter_text
                )

                mask = all_fields_frame.apply(
                    lambda row: search_text
                    in " ".join(
                        normalize_text(value)
                        for value in row.values
                    ),
                    axis=1,
                )

                all_fields_frame = (
                    all_fields_frame[mask]
                )

            st.dataframe(
                all_fields_frame,
                use_container_width=True,
                hide_index=True,
                height=450,
            )
        else:
            st.info(
                "Der Endpunkt enthält keine auswertbaren "
                "Felder."
            )

        st.markdown("#### Vollständige Rohdaten")

        st.json(
            result["data"],
            expanded=False,
        )

        st.download_button(
            label=(
                "Rohdaten dieses Endpunkts "
                "als JSON herunterladen"
            ),
            data=safe_json_text(
                result["data"]
            ),
            file_name=(
                f"kickbase_spieler_"
                f"{selected_player_id}_"
                f"endpunkt_{endpoint_index}.json"
            ),
            mime="application/json",
            key=(
                f"download_endpoint_"
                f"{endpoint_index}"
            ),
            use_container_width=True,
        )


# ---------------------------------------------------------
# Gemeinsamer Download
# ---------------------------------------------------------

st.subheader("5. Ergebnisse weitergeben")

export_data = {
    "player": {
        "id": selected_player_id,
        "name": selected_player_name,
        "current_lineup_slot": lineup_slot,
        "current_squad_status": (
            "Start 11"
            if lineup_slot is not None
            else "Trading"
        ),
    },
    "league": {
        "id": league_id,
        "name": get_league_name(
            selected_league
        ),
    },
    "results": results,
}

st.download_button(
    label="Alle Diagnoseergebnisse herunterladen",
    data=safe_json_text(export_data),
    file_name=(
        f"kickbase_spielerdiagnose_"
        f"{selected_player_id}.json"
    ),
    mime="application/json",
    key="download_all_diagnosis_results",
    type="primary",
    use_container_width=True,
)

st.caption(
    "Lade am besten die gemeinsame Diagnose-Datei "
    "herunter. Prüfe vor dem Teilen, ob darin persönliche "
    "Daten, Tokens oder andere vertrauliche Angaben "
    "enthalten sind."
)


# ---------------------------------------------------------
# Cache leeren
# ---------------------------------------------------------

st.markdown("### Diagnose neu laden")

if st.button(
    "Diagnosedaten und Kader neu laden",
    key="reload_diagnosis_data",
    use_container_width=True,
):
    keys_to_remove = []

    for state_key in st.session_state.keys():
        if (
            state_key.startswith(
                "diagnosis_managers_"
            )
            or state_key.startswith(
                "diagnosis_squad_"
            )
            or state_key.startswith(
                "diagnosis_filter_"
            )
            or state_key.startswith(
                "player_diagnosis_"
            )
        ):
            keys_to_remove.append(state_key)

    for state_key in keys_to_remove:
        st.session_state.pop(
            state_key,
            None,
        )

    st.rerun()
