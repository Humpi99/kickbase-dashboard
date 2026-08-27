"""
Kickbase Liga-Dashboard.

Ansichten: Manager und Liga.
"""

import pandas as pd
import streamlit as st

from kickbase_api import KickbaseAPI


# ---------------------------------------------------------
# Farben
# ---------------------------------------------------------

COLOR_POSITIVE = "#12a150"
COLOR_NEGATIVE = "#e03131"
COLOR_NEUTRAL = "#1c1c1c"
COLOR_LABEL = "#8a8a8a"
COLOR_LINE = "#e6e6e6"


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


def table_height(row_count):
    """
    Berechnet die volle Tabellenhöhe.

    So entsteht kein zusätzliches Scrollfenster.
    """
    return int(38 + row_count * 35)


def sort_controls(frame, columns, key, default_column):
    """
    Zeigt deutsche Sortierfelder über einer Tabelle.

    Gibt die sortierte Tabelle zurück.
    """
    available = [
        column for column in columns
        if column in frame.columns
    ]

    if not available:
        return frame.reset_index(drop=True)

    left, right = st.columns([3, 2])

    if default_column in available:
        default_index = available.index(default_column)
    else:
        default_index = 0

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

    ascending = direction == "Aufsteigend"

    return frame.sort_values(
        sort_column,
        ascending=ascending,
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


# ---------------------------------------------------------
# Feldnamen
# ---------------------------------------------------------

# mv ist der aktuelle Marktwert
MARKET_VALUE_KEYS = [
    "mv",
    "marketValue",
    "currentValue",
    "cv",
]

# mvgl ist der Marktwertgewinn seit dem Kauf
PROFIT_KEYS = [
    "mvgl",
    "profit",
    "prof",
]

# tfhmvt ist die Änderung der letzten 24 Stunden
DAILY_CHANGE_KEYS = [
    "tfhmvt",
    "mvt",
    "sdmvt",
    "dmv",
]

# lo enthält den Platz in der Startelf
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
    """
    Berechnet den Einstandspreis.

    Einstandspreis = Marktwert minus Gewinn.
    """
    market_value = get_market_value(player)
    profit = get_profit(player)

    if market_value is None or profit is None:
        return None

    return market_value - profit


def get_daily_change(player):
    """Liest die Marktwertänderung der letzten 24 Stunden."""
    return to_number(
        first_value(player, DAILY_CHANGE_KEYS)
    )


def get_lineup_slot(player):
    """
    Ermittelt den Platz in der Startelf.

    Zahl von 0 bis 10 bedeutet aufgestellt.
    None bedeutet Bank.
    """
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
# Datenansicht
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

    if isinstance(value, list):
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


# ---------------------------------------------------------
# Erkennung von Listen
# ---------------------------------------------------------

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
    """Prüft, ob ein Objekt ein Spieler mit Marktwert ist."""
    if not isinstance(item, dict):
        return False

    return get_market_value(item) is not None


def find_list(value, check_function, keys, depth=0):
    """Sucht rekursiv eine passende Liste."""
    if depth > 8:
        return []

    if isinstance(value, list):
        matches = [
            item for item in value
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

    if isinstance(value, dict):
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
# Transfers erkennen
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
                "buyer": str(buyer)
                if buyer is not None
                else None,
                "seller": str(seller)
                if seller is not None
                else None,
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
    """Berechnet den realisierten Gewinn aus dem Feed."""
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
                player_id, []
            ).append(event["amount"])

        if event["seller"] == str(manager_id):
            sales.setdefault(
                player_id, []
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
                    "Kaufpreis": buy_price
                    if known_price
                    else None,
                    "Verkaufspreis": sale_price,
                    "Gewinn": profit,
                }
            )

    return realized, trades, raw_samples


# ---------------------------------------------------------
# Kennzahlen eines Managers berechnen
# ---------------------------------------------------------

def compute_stats(players):
    """Rechnet alle Kennzahlen aus einer Spielerliste."""
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

        stats["squad_value"] += market_value
        stats["buy_total"] += buy_price
        stats["profit_in_club"] += get_profit(player) or 0.0
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


def load_manager_players(api, league_id, manager_id):
    """Lädt die Spieler eines Managers ohne Fehlerabbruch."""
    try:
        squad_result = api.get_manager_squad(
            league_id,
            manager_id,
        )

        return find_players_with_value(squad_result), None

    except Exception as error:
        return [], str(error)


def load_realized_profit(api, league_id, manager_id):
    """Liest den realisierten Gewinn aus dem Feld prft."""
    try:
        return api.get_realized_profit(
            league_id,
            manager_id,
        )

    except Exception:
        return None, None


# ---------------------------------------------------------
# Formatierung und Farben für Tabellen
# ---------------------------------------------------------

def currency_formatter(value):
    """Formatiert Zahlen ohne Vorzeichen für Tabellen."""
    return format_currency(value)


def signed_formatter(value):
    """Formatiert Zahlen mit Vorzeichen für Tabellen."""
    return format_signed_currency(value)


def color_by_value(value):
    """Färbt eine Zahl grün oder rot."""
    number = to_number(value)

    if number is None or number == 0:
        return ""

    if number > 0:
        return (
            f"color: {COLOR_POSITIVE}; font-weight: 600"
        )

    return f"color: {COLOR_NEGATIVE}; font-weight: 600"


def style_player_table(frame):
    """
    Formatiert und färbt die Kadertabelle.

    Die Zahlen bleiben Zahlen, damit korrekt
    sortiert werden kann.
    """

    def color_row(row):
        """Graut Zeilen von Trading Spielern aus."""
        if row["Status"] == "Trading":
            return [
                "color: #9a9a9a; "
                "background-color: #f7f7f7"
            ] * len(row)

        return [""] * len(row)

    styled = frame.style.apply(color_row, axis=1)

    styled = styled.map(
        color_by_value,
        subset=["Gewinn gesamt", "Trend 24 Stunden"],
    )

    styled = styled.format(
        {
            "Einstandspreis": currency_formatter,
            "Marktwert": currency_formatter,
            "Gewinn gesamt": signed_formatter,
            "Trend 24 Stunden": signed_formatter,
        }
    )

    return styled


def style_league_table(frame):
    """Formatiert und färbt die Liga-Tabelle."""
    signed_columns = [
        column for column in [
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
        ]
        if column in frame.columns
    ]

    currency_columns = [
        column for column in [
            "Start 11",
            "Trading",
            "Kaderwert",
        ]
        if column in frame.columns
    ]

    styled = frame.style.map(
        color_by_value,
        subset=signed_columns,
    )

    formats = {}

    for column in currency_columns:
        formats[column] = currency_formatter

    for column in signed_columns:
        formats[column] = signed_formatter

    return styled.format(formats)


def style_trades_table(frame):
    """Formatiert und färbt die Tabelle verkaufter Spieler."""
    styled = frame.style.map(
        color_by_value,
        subset=["Gewinn"],
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
# KPI-Blöcke
# ---------------------------------------------------------

def kpi_block(title, entries):
    """
    Zeigt einen KPI-Block mit Überschrift und Spalten.

    entries ist eine Liste aus Einträgen:
    (Beschriftung, Hauptwert, Zusatzzeilen, Farbe)
    """
    colors = {
        "neutral": COLOR_NEUTRAL,
        "plus": COLOR_POSITIVE,
        "minus": COLOR_NEGATIVE,
    }

    st.markdown(
        f"<div style='border-top:1px solid {COLOR_LINE};"
        f"padding-top:10px;margin-top:22px;"
        f"font-size:12px;font-weight:500;"
        f"letter-spacing:0.08em;text-transform:uppercase;"
        f"color:{COLOR_LABEL};'>{title}</div>",
        unsafe_allow_html=True,
    )

    columns = st.columns(len(entries))

    for column, entry in zip(columns, entries):
        label, value, notes, tone = entry

        color = colors.get(tone, COLOR_NEUTRAL)

        notes_html = ""

        for note in notes:
            if note:
                notes_html += (
                    f"<div style='font-size:12px;"
                    f"color:{COLOR_LABEL};"
                    f"line-height:1.5;'>{note}</div>"
                )

        column.markdown(
            f"<div style='padding:8px 0 2px 0;'>"
            f"<div style='font-size:12px;"
            f"color:{COLOR_LABEL};'>{label}</div>"
            f"<div style='font-size:24px;font-weight:700;"
            f"color:{color};padding:2px 0 4px 0;'>"
            f"{value}</div>"
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


# ---------------------------------------------------------
# Platzhalter für den vierten KPI-Block
# ---------------------------------------------------------

# Hier tragen wir spaeter die echten Berechnungen ein.
# Aufbau je Eintrag: (Beschriftung, Hinweistext)

EXTRA_KPI_PLACEHOLDERS = [
    ("KPI 1", "Berechnung folgt"),
    ("KPI 2", "Berechnung folgt"),
    ("KPI 3", "Berechnung folgt"),
]


def build_extra_kpis():
    """Baut die Einträge für den vierten KPI-Block."""
    entries = []

    for label, note in EXTRA_KPI_PLACEHOLDERS:
        entries.append(
            (
                label,
                "—",
                [note],
                "neutral",
            )
        )

    return entries


# ---------------------------------------------------------
# Seiteneinstellungen
# ---------------------------------------------------------

st.set_page_config(
    page_title="Kickbase Dashboard",
    page_icon="⚽",
    layout="wide",
)


# Gestaltung der Reiter in der Seitenleiste
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        text-align: left;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        background-color: #ffffff;
        color: #333333;
        font-weight: 500;
        padding: 10px 14px;
        margin-bottom: 6px;
    }
    section[data-testid="stSidebar"]
    div.stButton > button:hover {
        border-color: #bdbdbd;
        background-color: #f5f5f5;
        color: #111111;
    }
    section[data-testid="stSidebar"]
    div.stButton > button[kind="primary"] {
        background-color: #1c1c1c;
        border-color: #1c1c1c;
        color: #ffffff;
    }
    section[data-testid="stSidebar"]
    div.stButton > button[kind="primary"]:hover {
        background-color: #000000;
        border-color: #000000;
        color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("⚽ Kickbase Dashboard")


# ---------------------------------------------------------
# Login
# ---------------------------------------------------------

if not st.session_state.get("logged_in"):
    email = st.sidebar.text_input(
        "Kickbase-E-Mail-Adresse"
    )

    password = st.sidebar.text_input(
        "Kickbase-Passwort",
        type="password",
    )

    if st.sidebar.button("Einloggen", type="primary"):
        if not email or not password:
            st.sidebar.warning(
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

                leagues = find_leagues(login_result)

                if not leagues:
                    st.error(
                        "Login erfolgreich, aber keine "
                        "Liga erkannt."
                    )
                    st.stop()

                st.session_state["api"] = api
                st.session_state["leagues"] = leagues
                st.session_state["logged_in"] = True

                st.rerun()

            except Exception as error:
                st.sidebar.error(str(error))

    st.title("⚽ Kickbase Liga-Dashboard")
    st.info("Bitte links anmelden.")
    st.stop()


# ---------------------------------------------------------
# Reiter in der Seitenleiste
# ---------------------------------------------------------

if "view" not in st.session_state:
    st.session_state["view"] = "Manager"

st.sidebar.markdown(
    f"<div style='font-size:12px;font-weight:500;"
    f"letter-spacing:0.08em;text-transform:uppercase;"
    f"color:{COLOR_LABEL};margin-bottom:8px;'>"
    f"Ansicht</div>",
    unsafe_allow_html=True,
)

if st.sidebar.button(
    "👤  Manager",
    key="nav_manager",
    type=(
        "primary"
        if st.session_state["view"] == "Manager"
        else "secondary"
    ),
):
    st.session_state["view"] = "Manager"
    st.rerun()

if st.sidebar.button(
    "🏆  Liga",
    key="nav_liga",
    type=(
        "primary"
        if st.session_state["view"] == "Liga"
        else "secondary"
    ),
):
    st.session_state["view"] = "Liga"
    st.rerun()

view = st.session_state["view"]

st.sidebar.markdown("---")


# ---------------------------------------------------------
# Liga auswählen
# ---------------------------------------------------------

api = st.session_state["api"]
leagues = st.session_state["leagues"]

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
    "Realisierten Gewinn laden",
    value=True,
    help="Liest die Transferhistorie. Dauert länger.",
)

kpis_expanded = st.sidebar.checkbox(
    "Kennzahlen aufgeklappt starten",
    value=False,
    help="Aus bedeutet: Mannschaft steht sofort im Fokus.",
)

st.sidebar.markdown("---")

if st.sidebar.button("Abmelden", key="logout"):
    st.session_state.clear()
    st.rerun()

st.title(f"⚽ {league_name}")


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
    st.error("Es konnten keine Manager geladen werden.")

    with st.expander("Fehlerdetails"):
        st.write(ranking_errors)

    st.stop()


# ---------------------------------------------------------
# Ansicht Liga
# ---------------------------------------------------------

if view == "Liga":
    st.subheader("Liga-Vergleich aller Manager")

    st.caption(
        "Ein Klick auf eine Zeile öffnet die "
        "Detailansicht des Managers."
    )

    # Neuer Schluessel, damit alte Textwerte
    # aus frueheren Versionen verworfen werden.
    cache_key = f"league_rows_v2_{league_id}"

    if st.button("Daten neu laden"):
        st.session_state.pop(cache_key, None)

    if cache_key not in st.session_state:
        rows = []

        progress = st.progress(
            0.0,
            text="Kader werden geladen …",
        )

        for index, manager in enumerate(managers):
            manager_id = get_manager_id(manager)
            manager_name = get_manager_name(manager)

            players, _ = load_manager_players(
                api,
                league_id,
                manager_id,
            )

            stats = compute_stats(players)

            realized, _ = load_realized_profit(
                api,
                league_id,
                manager_id,
            )

            realized_value = realized or 0.0

            rows.append(
                {
                    "Manager": manager_name,
                    "Start 11": stats["lineup_value"],
                    "Trading": stats["trading_value"],
                    "Kaderwert": stats["squad_value"],
                    "Spieler": stats["player_count"],
                    "Gewinn gesamt": (
                        stats["profit_in_club"]
                        + realized_value
                    ),
                    "Trend Start 11": (
                        stats["trend_lineup"]
                    ),
                    "Trend Trading": (
                        stats["trend_trading"]
                    ),
                    "Trend gesamt": stats["trend_total"],
                }
            )

            progress.progress(
                (index + 1) / len(managers),
                text=f"Kader werden geladen … "
                     f"{index + 1} von {len(managers)}",
            )

        progress.empty()

        st.session_state[cache_key] = rows

    rows = st.session_state[cache_key]

    league_frame = pd.DataFrame(rows)

    # Alte Hilfsspalte aus frueheren Versionen entfernen
    if "_sort" in league_frame.columns:
        league_frame = league_frame.drop(
            columns=["_sort"]
        )

    league_frame = sort_controls(
        league_frame,
        [
            "Manager",
            "Start 11",
            "Trading",
            "Kaderwert",
            "Spieler",
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
        ],
        key="liga",
        default_column="Kaderwert",
    )

    sorted_names = league_frame["Manager"].tolist()

    selection = st.dataframe(
        style_league_table(league_frame),
        use_container_width=True,
        hide_index=True,
        height=table_height(len(league_frame)),
        on_select="rerun",
        selection_mode="single-row",
        key="league_table",
    )

    selected_rows = []

    if selection is not None:
        selected_rows = selection.selection.rows

    if selected_rows:
        chosen_name = sorted_names[selected_rows[0]]

        for index, manager in enumerate(managers):
            if get_manager_name(manager) == chosen_name:
                st.session_state[
                    "selected_manager_index"
                ] = index
                break

        st.session_state["view"] = "Manager"
        st.session_state["came_from_league"] = True
        st.rerun()

    st.stop()


# ---------------------------------------------------------
# Ansicht Manager
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

if default_index >= len(managers):
    default_index = 0

manager_index = st.selectbox(
    "Manager auswählen",
    range(len(managers)),
    index=default_index,
    format_func=lambda index: get_manager_name(
        managers[index]
    ),
)

if manager_index != default_index:
    st.session_state["came_from_league"] = False

st.session_state["selected_manager_index"] = manager_index

selected_manager = managers[manager_index]
selected_manager_id = get_manager_id(selected_manager)
selected_manager_name = get_manager_name(
    selected_manager
)


# ---------------------------------------------------------
# Kader laden
# ---------------------------------------------------------

with st.spinner("Kader wird geladen …"):
    players, squad_error = load_manager_players(
        api,
        league_id,
        selected_manager_id,
    )


# ---------------------------------------------------------
# Transfers lesen
# ---------------------------------------------------------

realized_profit = None
realized_trades = []
feed_samples = []

if show_realized and players:
    with st.spinner("Transferhistorie wird gelesen …"):
        (
            realized_profit,
            realized_trades,
            feed_samples,
        ) = load_feed_transfers(
            api,
            league_id,
            selected_manager_id,
        )

# Realisierter Gewinn direkt aus dem Feld prft.
# Wenn prft gefunden wird, hat es Vorrang vor dem Feed.

prft_value = None
prft_source = None

if players:
    with st.spinner("Realisierter Gewinn wird gelesen …"):
        prft_value, prft_source = load_realized_profit(
            api,
            league_id,
            selected_manager_id,
        )

if prft_value is not None:
    realized_profit = prft_value
    realized_note = "aus Feld prft"
else:
    realized_note = (
        f"{len(realized_trades)} Verkäufe erkannt"
    )


# ---------------------------------------------------------
# Kennzahlen berechnen
# ---------------------------------------------------------

stats = compute_stats(players)

total_profit = stats["profit_in_club"]

if realized_profit is not None:
    total_profit = (
        stats["profit_in_club"] + realized_profit
    )


# ---------------------------------------------------------
# KPI-Anzeige, einklappbar
# ---------------------------------------------------------

open_kpis = kpis_expanded or st.session_state.get(
    "came_from_league",
    False,
)

with st.expander(
    f"Kennzahlen: {selected_manager_name}",
    expanded=open_kpis,
):
    kpi_block(
        "Mannschaft",
        [
            (
                "Start 11",
                format_currency(stats["lineup_value"]),
                [
                    f"Einstand: "
                    f"{format_currency(stats['buy_lineup'])}",
                    f"{stats['lineup_count']} Spieler",
                ],
                "neutral",
            ),
            (
                "Trading",
                format_currency(stats["trading_value"]),
                [
                    f"Einstand: "
                    f"{format_currency(stats['buy_trading'])}",
                    f"{stats['trading_count']} Spieler",
                ],
                "neutral",
            ),
            (
                "Gesamt",
                format_currency(stats["squad_value"]),
                [
                    f"Einstand: "
                    f"{format_currency(stats['buy_total'])}",
                    f"{stats['player_count']} Spieler",
                ],
                "neutral",
            ),
        ],
    )

    kpi_block(
        "Gewinn",
        [
            (
                "realisiert",
                format_signed_currency(realized_profit)
                if realized_profit is not None
                else "—",
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
    )

    kpi_block(
        "Weitere KPIs",
        build_extra_kpis(),
    )

    st.markdown("")


# ---------------------------------------------------------
# Kadertabelle, immer vollständig sichtbar
# ---------------------------------------------------------

st.subheader(
    f"Kader von {selected_manager_name}"
)

if squad_error:
    st.error(
        f"Kader konnte nicht geladen werden: "
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

        player_rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": position_name,
                "Status": status,
                "Einstandspreis": get_buy_price(player),
                "Marktwert": get_market_value(player),
                "Gewinn gesamt": get_profit(player),
                "Trend 24 Stunden": get_daily_change(
                    player
                ),
            }
        )

    player_frame = pd.DataFrame(player_rows)

    player_frame = sort_controls(
        player_frame,
        [
            "Spieler",
            "Position",
            "Status",
            "Einstandspreis",
            "Marktwert",
            "Gewinn gesamt",
            "Trend 24 Stunden",
        ],
        key="kader",
        default_column="Gewinn gesamt",
    )

    st.dataframe(
        style_player_table(player_frame),
        use_container_width=True,
        hide_index=True,
        height=table_height(len(player_frame)),
    )

    st.caption(
        "Trading Spieler sind ausgegraut."
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
    )

    st.dataframe(
        style_trades_table(trades_frame),
        use_container_width=True,
        hide_index=True,
        height=table_height(len(trades_frame)),
    )


# ---------------------------------------------------------
# Alle Daten zu einem Spieler
# ---------------------------------------------------------

with st.expander("Alle Daten zu einem Spieler"):
    if players:
        inspect_index = st.selectbox(
            "Spieler auswählen",
            range(len(players)),
            format_func=lambda index: get_player_name(
                players[index]
            ),
        )

        inspect_player = players[inspect_index]

        squad_fields = flatten_fields(inspect_player)

        if squad_fields:
            st.dataframe(
                pd.DataFrame(squad_fields),
                use_container_width=True,
                hide_index=True,
                height=400,
            )

        st.write("**Rohdaten:**")
        st.json(inspect_player)


# ---------------------------------------------------------
# Alle Daten zu einem Manager
# ---------------------------------------------------------

with st.expander("Alle Daten zu diesem Manager"):
    st.write(
        "Hier werden alle bekannten Manager-Endpunkte "
        "getestet und ihr Inhalt angezeigt."
    )

    if st.button("Manager-Daten laden"):
        with st.spinner("Endpunkte werden getestet …"):
            manager_sources, manager_errors = (
                api.explore_manager(
                    league_id,
                    selected_manager_id,
                )
            )

        st.session_state["manager_sources"] = (
            manager_sources
        )
        st.session_state["manager_errors"] = (
            manager_errors
        )

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
            f"{len(manager_sources)} Endpunkte haben "
            "geantwortet."
        )

        overview_rows = []

        for source in manager_sources:
            data = source["data"]

            if isinstance(data, dict):
                content = ", ".join(sorted(data.keys()))
            elif isinstance(data, list):
                content = (
                    f"Liste mit {len(data)} Einträgen"
                )
            else:
                content = str(type(data).__name__)

            overview_rows.append(
                {
                    "Endpunkt": source["path"],
                    "Enthaltene Felder": content,
                }
            )

        overview_frame = pd.DataFrame(overview_rows)

        st.dataframe(
            overview_frame,
            use_container_width=True,
            hide_index=True,
            height=table_height(len(overview_frame)),
        )

        st.write("**Inhalt der einzelnen Endpunkte:**")

        for source in manager_sources:
            with st.expander(source["path"]):
                fields = flatten_fields(source["data"])

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
        with st.expander("Endpunkte ohne Antwort"):
            st.write(manager_errors)


# ---------------------------------------------------------
# Diagnose der Transferquellen
# ---------------------------------------------------------

with st.expander("Diagnose der Transferquellen"):
    if feed_samples:
        for sample in feed_samples:
            with st.expander(sample["Quelle"]):
                st.json(sample["Daten"])
    else:
        st.write("Keine Quelle hat geantwortet.")
