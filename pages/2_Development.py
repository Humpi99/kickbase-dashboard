"""
Development-Bereich für das Kickbase-Dashboard.

Untersucht die Kickbase-API, um für jeden Manager
automatisch die Bonuskriterien ableiten zu können.
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
        "needed_data": "Gesamtpunkte des Managers je Spieltag",
        "api_hint": "mdp-Feld in den Spieltag-Einträgen der Manager-Saisondaten",
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
        "needed_data": "Transferhistorie: Kauf- und Verkaufspreis je Spieler",
        "api_hint": "Manager-Transfer- oder Activities-Endpunkte",
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

.dev-status-found { color: var(--dev-success); font-weight: 700; }
.dev-status-missing { color: var(--dev-error); font-weight: 700; }
.dev-status-partial { color: var(--dev-warning); font-weight: 700; }

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

.dev-data-table td.right {
    text-align: right;
}

.dev-highlight-row td {
    background: var(--dev-highlight);
}

.dev-total-row td {
    background: var(--dev-header-bg);
    font-weight: 700;
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

st.markdown(DEV_STYLE, unsafe_allow_html=True)


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
    value = first_value(league, ["id", "i", "leagueId", "li"], "")
    return str(value) if value else ""


def get_league_name(league):
    return str(first_value(league, ["name", "n", "leagueName", "ln"], "Unbekannte Liga"))


def get_manager_id(manager):
    value = first_value(manager, ["id", "i", "u", "userId", "uid", "ui"], "")
    return str(value) if value else ""


def get_manager_name(manager):
    return str(first_value(
        manager,
        ["name", "unm", "n", "username", "un", "teamName", "tn"],
        "Unbekannter Manager",
    ))


def looks_like_manager(item):
    if not isinstance(item, dict):
        return False
    if not get_manager_id(item):
        return False
    if get_manager_name(item) == "Unbekannter Manager":
        return False
    markers = {"unm", "u", "userId", "uid", "ui", "tv", "teamValue", "placement", "rank", "shp", "uim"}
    return bool(markers.intersection(item.keys()))


def find_manager_list(value, depth=0):
    if depth > 8:
        return []
    if isinstance(value, list):
        managers = [item for item in value if looks_like_manager(item)]
        if managers:
            return managers
        for item in value:
            result = find_manager_list(item, depth + 1)
            if result:
                return result
    elif isinstance(value, dict):
        for key in ["us", "users", "managers", "ranking", "items", "it"]:
            if key in value:
                result = find_manager_list(value[key], depth + 1)
                if result:
                    return result
        for key, nested in value.items():
            if key in {"tkn", "token", "accessToken"}:
                continue
            result = find_manager_list(nested, depth + 1)
            if result:
                return result
    return []


def safe_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(value)


def format_bonus(value):
    if value >= 1_000_000:
        amount = value / 1_000_000
        text = f"{amount:,.2f}"
        text = text.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{text} Mio. €"
    amount = value / 1_000
    text = f"{amount:,.0f}"
    text = text.replace(",", ".")
    return f"{text} k €"


def format_compact(value):
    """Kompakte Darstellung für die Tabelle."""
    if value == 0:
        return "—"
    if value >= 1_000_000:
        amount = value / 1_000_000
        if amount == int(amount):
            return f"{int(amount)}M"
        return f"{amount:.1f}M"
    if value >= 1_000:
        amount = value / 1_000
        if amount == int(amount):
            return f"{int(amount)}k"
        return f"{amount:.0f}k"
    return str(int(value))


# ---------------------------------------------------------
# API-Endpunkte laden
# ---------------------------------------------------------

def try_endpoint(api, path):
    try:
        data = api.get(path)
        return {"path": path, "success": True, "data": data, "error": None}
    except Exception as error:
        return {"path": path, "success": False, "data": None, "error": str(error)}


# ---------------------------------------------------------
# Spieltagsdaten auswerten
# ---------------------------------------------------------

def extract_current_season_matchdays(data, depth=0):
    if depth > 10:
        return []

    if isinstance(data, dict):
        season_name = data.get("sn")
        season_id = data.get("sid")

        if season_name is not None or season_id is not None:
            now = datetime.now()
            start_year = now.year if now.month >= 7 else now.year - 1
            expected_name = f"{start_year}/{start_year + 1}"

            if str(season_name) != expected_name:
                return []

            inner_list = data.get("it", [])
            if isinstance(inner_list, list):
                matchdays = []
                for entry in inner_list:
                    if not isinstance(entry, dict):
                        continue
                    day = entry.get("day")
                    if day is None:
                        continue
                    matchdays.append({
                        "day": day,
                        "points": to_number(entry.get("mdp")),
                        "current": entry.get("cur"),
                        "date": entry.get("md"),
                        "tw": entry.get("tw"),
                    })
                if matchdays:
                    return matchdays

        for value in data.values():
            result = extract_current_season_matchdays(value, depth + 1)
            if result:
                return result

    elif isinstance(data, list):
        for item in data:
            result = extract_current_season_matchdays(item, depth + 1)
            if result:
                return result

    return []


def deduplicate_matchdays(matchdays):
    by_day = {}
    for entry in matchdays:
        day = entry["day"]
        points = entry["points"]
        if day not in by_day or (points is not None and points != 0):
            by_day[day] = entry
    return sorted(by_day.values(), key=lambda e: (to_number(e["day"]) or 0))


def load_manager_matchdays(api, league_id, manager_id):
    """Lädt die Spieltage eines Managers."""
    base = f"/v4/leagues/{league_id}/managers/{manager_id}"
    paths = [f"{base}/performance", f"{base}/dashboard", base]

    for path in paths:
        result = try_endpoint(api, path)
        if result["success"]:
            found = extract_current_season_matchdays(result["data"])
            if found:
                return deduplicate_matchdays(found)

    return []


def calculate_manager_bonus(matchdays):
    """Berechnet alle Boni eines Managers aus seinen Spieltagen."""
    total_points = 0
    team_1000 = 0
    team_1500 = 0
    team_2000 = 0
    wins = 0

    for entry in matchdays:
        points = entry["points"]
        if points is None:
            continue

        total_points += points

        if points >= 1000:
            team_1000 += 1
        if points >= 1500:
            team_1500 += 1
        if points >= 2000:
            team_2000 += 1

        if entry.get("tw") is True:
            wins += 1

    # Tägliche Anmeldung: Tage seit 10.08.2026
    season_start = datetime(2026, 8, 10)
    days_since = max(0, (datetime.now() - season_start).days)
    daily_bonus = days_since * 100_000

    # Punkte-Bonus: Gesamtpunkte × 1.000
    points_bonus = total_points * 1_000

    # Team-Punkte-Boni
    bonus_1000 = team_1000 * 250_000
    bonus_1500 = team_1500 * 1_000_000
    bonus_2000 = team_2000 * 2_000_000

    # Spieltagssieger
    wins_bonus = wins * 1_000_000

    total_bonus = daily_bonus + points_bonus + bonus_1000 + bonus_1500 + bonus_2000 + wins_bonus

    return {
        "total_points": total_points,
        "days": days_since,
        "daily_bonus": daily_bonus,
        "points_bonus": points_bonus,
        "team_1000": team_1000,
        "bonus_1000": bonus_1000,
        "team_1500": team_1500,
        "bonus_1500": bonus_1500,
        "team_2000": team_2000,
        "bonus_2000": bonus_2000,
        "wins": wins,
        "wins_bonus": wins_bonus,
        "total_bonus": total_bonus,
    }


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
    st.warning("Du bist noch nicht angemeldet. Öffne zuerst die Hauptseite und melde dich an.")
    st.stop()

api = st.session_state.get("api")
leagues = st.session_state.get("leagues", [])

if api is None or not leagues:
    st.error("Anmeldedaten nicht gefunden. Bitte auf der Hauptseite neu anmelden.")
    st.stop()


# ---------------------------------------------------------
# Liga und Manager auswählen
# ---------------------------------------------------------

st.subheader("1. Liga auswählen")

league_index = st.selectbox(
    "Liga auswählen",
    range(len(leagues)),
    format_func=lambda index: get_league_name(leagues[index]),
    key="dev_league_index",
)

selected_league = leagues[league_index]
league_id = get_league_id(selected_league)

manager_cache_key = f"dev_managers_{league_id}"

if manager_cache_key not in st.session_state:
    with st.spinner("Manager werden geladen …"):
        try:
            sources, _ = api.get_ranking(league_id)
        except Exception:
            sources = []

        managers = []
        for source in sources:
            managers = find_manager_list(source.get("data"))
            if managers:
                break

        st.session_state[manager_cache_key] = managers

managers = st.session_state[manager_cache_key]

if not managers:
    st.error("Es konnten keine Manager geladen werden.")
    st.stop()

manager_lookup = {get_manager_id(m): m for m in managers}
manager_ids = list(manager_lookup.keys())


# ---------------------------------------------------------
# Bonus-Übersicht aller Manager
# ---------------------------------------------------------

st.subheader("2. Bonus-Übersicht aller Manager")

st.info(
    "Berechnet für jeden Manager: Tägliche Anmeldung, "
    "Punkte-Bonus, Team-Punkte-Schwellen (1.000 / 1.500 / 2.000) "
    "und Spieltagssieger. MVP und Transfers sind nicht enthalten."
)

if st.button(
    "📊 Bonus-Übersicht laden",
    key="load_bonus_overview",
    type="primary",
    use_container_width=True,
):
    progress = st.progress(0.0, text="Bonus-Daten werden geladen …")

    all_bonus_data = {}

    for index, mid in enumerate(manager_ids):
        name = get_manager_name(manager_lookup[mid])
        matchdays = load_manager_matchdays(api, league_id, mid)
        bonus = calculate_manager_bonus(matchdays)
        bonus["name"] = name

        all_bonus_data[mid] = bonus

        progress.progress(
            (index + 1) / len(manager_ids),
            text=f"Manager werden geladen … {index + 1} von {len(manager_ids)}",
        )

    progress.empty()

    st.session_state["dev_bonus_overview"] = all_bonus_data

if "dev_bonus_overview" in st.session_state:
    all_bonus_data = st.session_state["dev_bonus_overview"]

    # Tabelle bauen
    rows_html = []

    # Nach Gesamt-Bonus sortieren (höchster zuerst)
    sorted_managers = sorted(
        all_bonus_data.items(),
        key=lambda item: item[1]["total_bonus"],
        reverse=True,
    )

    for rank, (mid, b) in enumerate(sorted_managers, start=1):
        rows_html.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<td><strong>{escape(b['name'])}</strong></td>"
            f"<td class='right'>{b['total_points']:,.0f}</td>"
            f"<td class='right'>{format_compact(b['daily_bonus'])}</td>"
            f"<td class='right'>{format_compact(b['points_bonus'])}</td>"
            f"<td class='right'>{b['team_1000']}× → {format_compact(b['bonus_1000'])}</td>"
            f"<td class='right'>{b['team_1500']}× → {format_compact(b['bonus_1500'])}</td>"
            f"<td class='right'>{b['team_2000']}× → {format_compact(b['bonus_2000'])}</td>"
            f"<td class='right'>{b['wins']}× → {format_compact(b['wins_bonus'])}</td>"
            f"<td class='right'><strong>{format_bonus(b['total_bonus'])}</strong></td>"
            f"</tr>"
        )

    st.markdown(
        "<table class='dev-data-table'>"
        "<thead><tr>"
        "<th>#</th>"
        "<th>Manager</th>"
        "<th>Punkte</th>"
        "<th>Login</th>"
        "<th>Pkt-Bonus</th>"
        "<th>1.000+</th>"
        "<th>1.500+</th>"
        "<th>2.000+</th>"
        "<th>Sieger</th>"
        "<th>Gesamt</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )

    # Legende
    st.caption(
        "Login = Tägliche Anmeldung (100k/Tag) · "
        "Pkt-Bonus = Gesamtpunkte × 1.000 · "
        "1.000+ / 1.500+ / 2.000+ = Team-Punkte-Schwellen · "
        "Sieger = Spieltagssieger (1M/Sieg) · "
        "Ohne MVP und Transfers"
    )


# ---------------------------------------------------------
# Bonusregeln-Referenz
# ---------------------------------------------------------

with st.expander("📋 Alle 14 Bonusregeln anzeigen"):
    rules_rows = []
    current_category = None

    for rule in BONUS_RULES:
        if rule["category"] != current_category:
            current_category = rule["category"]
            rules_rows.append(
                "<tr style='background:var(--dev-header-bg);'>"
                f"<td colspan='3'><strong>{escape(current_category)}</strong></td>"
                "</tr>"
            )

        rules_rows.append(
            "<tr>"
            f"<td>{escape(rule['description'])}</td>"
            f"<td>{escape(format_bonus(rule['bonus']))}</td>"
            f"<td style='font-size:0.75rem;color:var(--dev-muted);'>"
            f"{escape(rule['needed_data'])}</td>"
            "</tr>"
        )

    st.markdown(
        "<table class='dev-data-table'>"
        "<thead><tr>"
        "<th>Erfolg</th><th>Bonus</th><th>Benötigte Daten</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rules_rows)}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Diagnose: Endpunkt-Suche (Runde 2)
# ---------------------------------------------------------

with st.expander("🔍 Diagnose: Endpunkt-Suche Runde 2"):
    if st.button("🧪 Runde 2: Neue Endpunkte testen", key="btn_diagnose_runde2"):
        import requests as req2

        token = st.session_state.get("token", "")
        lid = league_id
        mid = manager_ids[0] if manager_ids else ""
        base_url = "https://api.kickbase.com"
        diag_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        st.write(f"**Liga:** `{lid}` | **Manager:** `{mid}`")

        st.markdown("### Block A: Liga-Ebene (ohne Spieltag)")
        endpoints_a = [
            f"/v4/leagues/{lid}/matchdays",
            f"/v4/leagues/{lid}/matchday",
            f"/v4/leagues/{lid}/live",
            f"/v4/leagues/{lid}/ranking",
            f"/v4/leagues/{lid}/feed",
            f"/v4/leagues/{lid}/stats",
            f"/v4/leagues/{lid}/lineup",
            f"/v4/leagues/{lid}/results",
        ]
        for ep in endpoints_a:
            try:
                r = req2.get(f"{base_url}{ep}", headers=diag_headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    keys = list(data.keys()) if isinstance(data, dict) else f"Liste mit {len(data)} Einträgen"
                    st.success(f"✅ `{ep}`: **Status 200** → Keys: `{keys}`")
                    with st.expander(f"Rohdaten: {ep}"):
                        st.json(data)
                else:
                    st.error(f"❌ `{ep}`: Status {r.status_code}")
            except Exception as e:
                st.error(f"❌ `{ep}`: Fehler → {e}")

        st.markdown("### Block B: Wettbewerb-Ebene (competitions)")
        endpoints_b = [
            "/v4/competitions/1/matchdays",
            "/v4/competitions/1/matchday",
            "/v4/competitions/1/table",
            "/v4/competitions/1/ranking",
            "/v4/competitions/1/live",
            "/v4/competitions/1/results",
        ]
        for ep in endpoints_b:
            try:
                r = req2.get(f"{base_url}{ep}", headers=diag_headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    keys = list(data.keys()) if isinstance(data, dict) else f"Liste mit {len(data)} Einträgen"
                    st.success(f"✅ `{ep}`: **Status 200** → Keys: `{keys}`")
                    with st.expander(f"Rohdaten: {ep}"):
                        st.json(data)
                else:
                    st.error(f"❌ `{ep}`: Status {r.status_code}")
            except Exception as e:
                st.error(f"❌ `{ep}`: Fehler → {e}")

        st.markdown("### Block C: Liga + Spieltag 1 (ohne Manager)")
        endpoints_c = [
            f"/v4/leagues/{lid}/matchdays/1",
            f"/v4/leagues/{lid}/matchday/1",
            f"/v4/leagues/{lid}/live/1",
            f"/v4/leagues/{lid}/ranking/1",
            f"/v4/leagues/{lid}/feed/1",
            f"/v4/leagues/{lid}/results/1",
        ]
        for ep in endpoints_c:
            try:
                r = req2.get(f"{base_url}{ep}", headers=diag_headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    keys = list(data.keys()) if isinstance(data, dict) else f"Liste mit {len(data)} Einträgen"
                    st.success(f"✅ `{ep}`: **Status 200** → Keys: `{keys}`")
                    with st.expander(f"Rohdaten: {ep}"):
                        st.json(data)
                else:
                    st.error(f"❌ `{ep}`: Status {r.status_code}")
            except Exception as e:
                st.error(f"❌ `{ep}`: Fehler → {e}")

        st.markdown("### Block D: Manager ohne Spieltag")
        endpoints_d = [
            f"/v4/leagues/{lid}/managers/{mid}/lineup",
            f"/v4/leagues/{lid}/managers/{mid}/feed",
            f"/v4/leagues/{lid}/managers/{mid}/stats",
            f"/v4/leagues/{lid}/managers/{mid}/squad",
            f"/v4/leagues/{lid}/managers/{mid}/performance",
        ]
        for ep in endpoints_d:
            try:
                r = req2.get(f"{base_url}{ep}", headers=diag_headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    keys = list(data.keys()) if isinstance(data, dict) else f"Liste mit {len(data)} Einträgen"
                    st.success(f"✅ `{ep}`: **Status 200** → Keys: `{keys}`")
                    with st.expander(f"Rohdaten: {ep}"):
                        st.json(data)
                else:
                    st.error(f"❌ `{ep}`: Status {r.status_code}")
            except Exception as e:
                st.error(f"❌ `{ep}`: Fehler → {e}")

        st.info("💡 Schick mir einen Screenshot der Ergebnisse – besonders von den grünen ✅ Treffern!")
