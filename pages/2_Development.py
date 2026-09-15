"""
Development-Bereich für das Kickbase-Dashboard.

Zeigt eine Bonus-Tabelle, in der für jeden Manager
die erreichten Erfolge eingetragen werden können.
Der Gesamtbonus wird automatisch berechnet.
"""

from html import escape

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
# Bonusregeln
# ---------------------------------------------------------

BONUS_RULES = [
    {
        "id": "daily_login",
        "category": "Allgemein",
        "description": "Tägliche Anmeldung",
        "bonus": 100_000,
        "note": "Ab dem 10.08.2026 täglich für jeden",
        "input_type": "number",
        "input_label": "Tage angemeldet",
    },
    {
        "id": "mvp",
        "category": "Spieltag",
        "description": "MVP des Spieltags",
        "bonus": 1_000_000,
        "note": (
            "Welcher Spieler war MVP und "
            "bei wem war er aufgestellt?"
        ),
        "input_type": "number",
        "input_label": "Anzahl MVP-Spieltage",
    },
    {
        "id": "matchday_winner",
        "category": "Spieltag",
        "description": "Spieltagssieger",
        "bonus": 1_000_000,
        "note": "Beim Manager selbst nachschauen",
        "input_type": "number",
        "input_label": "Anzahl gewonnene Spieltage",
    },
    {
        "id": "player_200",
        "category": "Spieler-Punkte",
        "description": "200 Punkte für einen Spieler",
        "bonus": 100_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "player_300",
        "category": "Spieler-Punkte",
        "description": "300 Punkte für einen Spieler",
        "bonus": 500_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "player_400",
        "category": "Spieler-Punkte",
        "description": "400 Punkte für einen Spieler",
        "bonus": 1_000_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "player_500",
        "category": "Spieler-Punkte",
        "description": "500 Punkte für einen Spieler",
        "bonus": 2_000_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "team_1000",
        "category": "Team-Punkte",
        "description": "1.000 Punkte ganzes Team",
        "bonus": 250_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "team_1500",
        "category": "Team-Punkte",
        "description": "1.500 Punkte ganzes Team",
        "bonus": 1_000_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "team_2000",
        "category": "Team-Punkte",
        "description": "2.000 Punkte ganzes Team",
        "bonus": 2_000_000,
        "note": "Einmalig pro Spieltag, wenn erfüllt",
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "transfer_3m",
        "category": "Transfergewinn",
        "description": "3 Mio. Transfergewinn mit einem Spieler",
        "bonus": 250_000,
        "note": (
            "Spieler muss gekauft worden sein, "
            "nicht zugelost. Verkauf nur an den Markt."
        ),
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "transfer_5m",
        "category": "Transfergewinn",
        "description": "5 Mio. Transfergewinn mit einem Spieler",
        "bonus": 500_000,
        "note": (
            "Spieler muss gekauft worden sein, "
            "nicht zugelost. Verkauf nur an den Markt."
        ),
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "transfer_10m",
        "category": "Transfergewinn",
        "description": "10 Mio. Transfergewinn mit einem Spieler",
        "bonus": 1_000_000,
        "note": (
            "Spieler muss gekauft worden sein, "
            "nicht zugelost. Verkauf nur an den Markt."
        ),
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
    {
        "id": "transfer_25m",
        "category": "Transfergewinn",
        "description": "25 Mio. Transfergewinn mit einem Spieler",
        "bonus": 2_000_000,
        "note": (
            "Spieler muss gekauft worden sein, "
            "nicht zugelost. Verkauf nur an den Markt."
        ),
        "input_type": "number",
        "input_label": "Wie oft erreicht?",
    },
]


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

def first_value(data, keys, default=None):
    """Gibt den ersten vorhandenen Wert zurück."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def get_manager_id(manager):
    """Ermittelt die Manager-ID."""
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


def get_league_id(league):
    """Ermittelt die Liga-ID."""
    value = first_value(
        league,
        ["id", "i", "leagueId", "li"],
        "",
    )

    return str(value) if value is not None else ""


def get_league_name(league):
    """Ermittelt den Liganamen."""
    return str(
        first_value(
            league,
            ["name", "n", "leagueName", "ln"],
            "Unbekannte Liga",
        )
    )


def looks_like_manager(item):
    """Prüft, ob ein Dictionary ein Manager ist."""
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
    """Sucht nach einer Managerliste."""
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


def format_bonus(value):
    """Formatiert einen Bonusbetrag."""
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
    --dev-category-bg: #eef1f5;
    --dev-positive: #0b8f43;
    --dev-highlight: #fff8e6;
}

.dev-info {
    padding: 0.8rem 1rem;
    margin: 0.5rem 0 1rem;
    border: 1px solid var(--dev-border);
    border-radius: 8px;
    background: var(--dev-background);
    color: var(--dev-text);
    font-size: 0.85rem;
}

.dev-summary {
    margin: 1rem 0;
    padding: 1rem;
    border: 2px solid var(--dev-positive);
    border-radius: 10px;
    background: var(--dev-highlight);
}

.dev-summary-title {
    color: var(--dev-text);
    font-weight: 750;
    font-size: 1rem;
    margin-bottom: 0.5rem;
}

.dev-summary-amount {
    color: var(--dev-positive);
    font-weight: 800;
    font-size: 1.6rem;
}

.dev-rules-table {
    width: 100%;
    border-collapse: collapse;
    color: var(--dev-text);
    background: var(--dev-background);
    font-size: 0.82rem;
    margin: 0.5rem 0;
}

.dev-rules-table th {
    padding: 0.6rem 0.55rem;
    border: 1px solid var(--dev-border);
    background: var(--dev-header-bg);
    color: var(--dev-header-text);
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    text-align: left;
    white-space: nowrap;
}

.dev-rules-table td {
    padding: 0.5rem 0.55rem;
    border: 1px solid var(--dev-border);
    vertical-align: middle;
}

.dev-category-row td {
    background: var(--dev-category-bg);
    font-weight: 700;
    font-size: 0.78rem;
    color: var(--dev-header-text);
}

.dev-note {
    color: var(--dev-muted);
    font-size: 0.75rem;
}

.dev-subtotal {
    font-weight: 750;
    color: var(--dev-positive);
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
    --dev-category-bg: #2a3038;
    --dev-positive: #52d889;
    --dev-highlight: #2a3520;
}
</style>
"""

st.markdown(
    DEV_STYLE,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Anmeldung prüfen
# ---------------------------------------------------------

st.title("🛠️ Development")

if not st.session_state.get("logged_in"):
    st.warning(
        "Du bist noch nicht angemeldet. "
        "Öffne zuerst die Hauptseite des Dashboards "
        "und melde dich dort an."
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
# Liga und Manager laden
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Manager auswählen
# ---------------------------------------------------------

st.subheader("Bonus-Berechnung")

st.markdown(
    """
    <div class="dev-info">
        Trage für den ausgewählten Manager ein, wie oft
        jeder Erfolg erreicht wurde. Der Gesamtbonus wird
        automatisch berechnet. Die Werte werden während
        der Sitzung gespeichert.
    </div>
    """,
    unsafe_allow_html=True,
)

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

st.markdown(
    f"#### Erfolge von {escape(selected_manager_name)}"
)


# ---------------------------------------------------------
# Eingabefelder und Berechnung
# ---------------------------------------------------------

bonus_state_key = (
    f"dev_bonus_{league_id}_"
    f"{selected_manager_id}"
)

if bonus_state_key not in st.session_state:
    st.session_state[bonus_state_key] = {
        rule["id"]: 0
        for rule in BONUS_RULES
    }

current_values = st.session_state[
    bonus_state_key
]

current_category = None
total_bonus = 0

for rule in BONUS_RULES:
    if rule["category"] != current_category:
        current_category = rule["category"]

        st.markdown(
            f"##### {escape(current_category)}"
        )

    columns = st.columns([4, 2, 2])

    with columns[0]:
        st.markdown(
            f"**{escape(rule['description'])}**"
        )

        st.caption(rule["note"])

    with columns[1]:
        st.caption(
            f"Bonus je Erfolg: "
            f"{format_bonus(rule['bonus'])}"
        )

    with columns[2]:
        new_value = st.number_input(
            rule["input_label"],
            min_value=0,
            max_value=999,
            step=1,
            value=current_values.get(
                rule["id"],
                0,
            ),
            key=(
                f"dev_input_{league_id}_"
                f"{selected_manager_id}_"
                f"{rule['id']}"
            ),
        )

        current_values[rule["id"]] = new_value

    rule_bonus = new_value * rule["bonus"]
    total_bonus += rule_bonus

st.session_state[bonus_state_key] = (
    current_values
)


# ---------------------------------------------------------
# Zusammenfassung
# ---------------------------------------------------------

st.markdown(
    "<div class='dev-summary'>"
    "<div class='dev-summary-title'>"
    f"Gesamtbonus für "
    f"{escape(selected_manager_name)}"
    "</div>"
    "<div class='dev-summary-amount'>"
    f"{format_bonus(total_bonus)}"
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Detailübersicht als Tabelle
# ---------------------------------------------------------

with st.expander(
    "Detailübersicht aller Erfolge",
    expanded=False,
):
    current_category = None
    table_rows = []

    for rule in BONUS_RULES:
        if rule["category"] != current_category:
            current_category = rule["category"]

            table_rows.append(
                "<tr class='dev-category-row'>"
                f"<td colspan='4'>"
                f"{escape(current_category)}"
                "</td>"
                "</tr>"
            )

        count = current_values.get(
            rule["id"],
            0,
        )

        rule_total = count * rule["bonus"]

        total_class = (
            "dev-subtotal"
            if rule_total > 0
            else ""
        )

        table_rows.append(
            "<tr>"
            f"<td>"
            f"{escape(rule['description'])}"
            "<br />"
            f"<span class='dev-note'>"
            f"{escape(rule['note'])}"
            "</span>"
            "</td>"
            f"<td>{escape(format_bonus(rule['bonus']))}</td>"
            f"<td>{count}</td>"
            f"<td class='{total_class}'>"
            f"{escape(format_bonus(rule_total))}"
            "</td>"
            "</tr>"
        )

    st.markdown(
        "<table class='dev-rules-table'>"
        "<thead><tr>"
        "<th>Erfolg</th>"
        "<th>Bonus je Erfolg</th>"
        "<th>Anzahl</th>"
        "<th>Bonus gesamt</th>"
        "</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        "<tfoot><tr>"
        "<td colspan='3'>"
        "<strong>Gesamtbonus</strong>"
        "</td>"
        "<td class='dev-subtotal'>"
        f"<strong>"
        f"{escape(format_bonus(total_bonus))}"
        "</strong>"
        "</td>"
        "</tr></tfoot>"
        "</table>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Alle Manager vergleichen
# ---------------------------------------------------------

st.markdown("---")
st.subheader("Alle Manager vergleichen")

comparison_rows = []

for manager_id in manager_ids:
    manager_name = get_manager_name(
        manager_lookup[manager_id]
    )

    state_key = (
        f"dev_bonus_{league_id}_{manager_id}"
    )

    values = st.session_state.get(
        state_key,
        {},
    )

    manager_total = sum(
        values.get(rule["id"], 0)
        * rule["bonus"]
        for rule in BONUS_RULES
    )

    comparison_rows.append(
        "<tr>"
        f"<td><strong>"
        f"{escape(manager_name)}"
        "</strong></td>"
        f"<td class='dev-subtotal'>"
        f"{escape(format_bonus(manager_total))}"
        "</td>"
        "</tr>"
    )

st.markdown(
    "<table class='dev-rules-table'>"
    "<thead><tr>"
    "<th>Manager</th>"
    "<th>Gesamtbonus</th>"
    "</tr></thead>"
    f"<tbody>{''.join(comparison_rows)}</tbody>"
    "</table>",
    unsafe_allow_html=True,
)

st.caption(
    "Die Werte werden während der Sitzung gespeichert. "
    "Nach dem Abmelden gehen eingetragene Zahlen verloren."
)


# ---------------------------------------------------------
# Bonusregeln anzeigen
# ---------------------------------------------------------

with st.expander(
    "Alle Bonusregeln anzeigen"
):
    rules_rows = []
    current_category = None

    for rule in BONUS_RULES:
        if rule["category"] != current_category:
            current_category = rule["category"]

            rules_rows.append(
                "<tr class='dev-category-row'>"
                f"<td colspan='3'>"
                f"{escape(current_category)}"
                "</td>"
                "</tr>"
            )

        rules_rows.append(
            "<tr>"
            f"<td>{escape(rule['description'])}</td>"
            f"<td>{escape(format_bonus(rule['bonus']))}</td>"
            f"<td class='dev-note'>"
            f"{escape(rule['note'])}"
            "</td>"
            "</tr>"
        )

    st.markdown(
        "<table class='dev-rules-table'>"
        "<thead><tr>"
        "<th>Erfolg</th>"
        "<th>Bonus</th>"
        "<th>Anmerkung</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rules_rows)}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )
