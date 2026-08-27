"""
Kickbase Liga-Dashboard.

Fokus: Kaderwert und Gewinn je Manager.
"""

import pandas as pd
import streamlit as st

from kickbase_api import KickbaseAPI


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
# Werte für Kaderwert, Kaufpreis und Gewinn
# ---------------------------------------------------------

TEAM_VALUE_KEYS = [
    "teamValue",
    "tv",
    "squadValue",
    "sv",
    "tvl",
]

MARKET_VALUE_KEYS = [
    "marketValue",
    "mv",
    "currentValue",
    "cv",
]

BUY_PRICE_KEYS = [
    "buyPrice",
    "bp",
    "purchasePrice",
    "pp",
    "boughtFor",
    "bf",
    "prc",
    "tp",
]

PROFIT_KEYS = [
    "profit",
    "prof",
    "pf",
    "gain",
    "sp",
]


def get_team_value(manager):
    """Liest den Kaderwert eines Managers."""
    return to_number(
        first_value(manager, TEAM_VALUE_KEYS)
    )


def get_market_value(player):
    """Liest den Marktwert eines Spielers."""
    return to_number(
        first_value(player, MARKET_VALUE_KEYS)
    )


def get_buy_price(player):
    """Liest den Kaufpreis eines Spielers."""
    return to_number(
        first_value(player, BUY_PRICE_KEYS)
    )


def get_player_profit(player):
    """Berechnet den Gewinn eines Spielers."""
    direct_profit = to_number(
        first_value(player, PROFIT_KEYS)
    )

    if direct_profit is not None:
        return direct_profit

    market_value = get_market_value(player)
    buy_price = get_buy_price(player)

    if market_value is None or buy_price is None:
        return None

    return market_value - buy_price


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
        "squadValue",
        "sv",
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
    """Sucht Spieler, die einen Marktwert besitzen."""
    return find_list(
        value,
        looks_like_player_with_value,
        [
            "players",
            "p",
            "it",
            "items",
            "squad",
            "lp",
            "pl",
        ],
    )


def safe_structure(value, depth=0):
    """Zeigt eine sichere Struktur ohne Tokenwerte."""
    if depth > 4:
        return "[weitere Ebene]"

    if isinstance(value, dict):
        result = {}

        for key, nested_value in value.items():
            if key.lower() in {
                "tkn",
                "token",
                "accesstoken",
                "password",
                "pass",
            }:
                result[key] = "[AUSGEBLENDET]"
            else:
                result[key] = safe_structure(
                    nested_value,
                    depth + 1,
                )

        return result

    if isinstance(value, list):
        if not value:
            return []

        return {
            "Typ": "Liste",
            "Anzahl": len(value),
            "Beispiel": safe_structure(
                value[0],
                depth + 1,
            ),
        }

    return f"<{type(value).__name__}>"


# ---------------------------------------------------------
# Seiteneinstellungen
# ---------------------------------------------------------

st.set_page_config(
    page_title="Kickbase Dashboard",
    page_icon="⚽",
    layout="wide",
)

st.sidebar.title("⚽ Kickbase Dashboard")


# ---------------------------------------------------------
# Abmelden
# ---------------------------------------------------------

if st.session_state.get("logged_in"):
    if st.sidebar.button("Abmelden"):
        st.session_state.clear()
        st.rerun()


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
                    st.json(
                        safe_structure(login_result)
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

st.title(f"⚽ {league_name}")


# ---------------------------------------------------------
# Ranking laden
# ---------------------------------------------------------

managers = []
ranking_errors = []

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
# Ranking-Tabelle
# ---------------------------------------------------------

st.subheader("🏆 Kaderwerte der Liga")

ranking_rows = []

for manager in managers:
    team_value = get_team_value(manager)

    ranking_rows.append(
        {
            "Manager": get_manager_name(manager),
            "Kaderwert": format_currency(team_value),
            "_sort": team_value or 0,
        }
    )

ranking_frame = pd.DataFrame(ranking_rows)
ranking_frame = ranking_frame.sort_values(
    "_sort",
    ascending=False,
)
ranking_frame = ranking_frame.drop(columns=["_sort"])

st.dataframe(
    ranking_frame,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# Manager auswählen
# ---------------------------------------------------------

st.markdown("---")

manager_index = st.selectbox(
    "👤 Manager auswählen",
    range(len(managers)),
    format_func=lambda index: get_manager_name(
        managers[index]
    ),
)

selected_manager = managers[manager_index]
selected_manager_id = get_manager_id(selected_manager)
selected_manager_name = get_manager_name(
    selected_manager
)


# ---------------------------------------------------------
# Kader des gewählten Managers laden
# ---------------------------------------------------------

players = []
squad_error = None
squad_result = None

try:
    with st.spinner(
        f"Kader von {selected_manager_name} "
        "wird geladen …"
    ):
        squad_result = api.get_manager_squad(
            league_id,
            selected_manager_id,
        )

    players = find_players_with_value(squad_result)

except Exception as error:
    squad_error = str(error)


# ---------------------------------------------------------
# Kennzahlen
# ---------------------------------------------------------

st.subheader(
    f"📊 Übersicht: {selected_manager_name}"
)

team_value = get_team_value(selected_manager)

calculated_value = None

if players:
    values = [
        get_market_value(player)
        for player in players
    ]

    values = [
        value for value in values
        if value is not None
    ]

    if values:
        calculated_value = sum(values)

total_profit = None
profit_count = 0
total_buy = None

if players:
    profits = []
    buy_prices = []

    for player in players:
        profit = get_player_profit(player)

        if profit is not None:
            profits.append(profit)
            profit_count += 1

        buy_price = get_buy_price(player)

        if buy_price is not None:
            buy_prices.append(buy_price)

    if profits:
        total_profit = sum(profits)

    if buy_prices:
        total_buy = sum(buy_prices)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Kaderwert",
    format_currency(team_value),
)

col2.metric(
    "Summe Marktwerte",
    format_currency(calculated_value),
)

col3.metric(
    "Summe Kaufpreise",
    format_currency(total_buy),
)

col4.metric(
    "Gewinn gesamt",
    format_signed_currency(total_profit),
)

st.caption(
    f"Manager-ID: {selected_manager_id} · "
    f"Spieler geladen: {len(players)}"
)


# ---------------------------------------------------------
# Kadertabelle
# ---------------------------------------------------------

st.subheader(
    f"📋 Kader von {selected_manager_name}"
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

        market_value = get_market_value(player)
        buy_price = get_buy_price(player)
        profit = get_player_profit(player)

        player_rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": position_name,
                "Kaufpreis": format_currency(
                    buy_price
                ),
                "Marktwert": format_currency(
                    market_value
                ),
                "Gewinn": format_signed_currency(
                    profit
                ),
                "_sort": profit
                if profit is not None
                else -999_999_999,
            }
        )

    player_frame = pd.DataFrame(player_rows)
    player_frame = player_frame.sort_values(
        "_sort",
        ascending=False,
    )
    player_frame = player_frame.drop(
        columns=["_sort"]
    )

    st.dataframe(
        player_frame,
        use_container_width=True,
        hide_index=True,
    )

    if profit_count == 0:
        st.warning(
            "Marktwerte sind da, aber kein Kaufpreis. "
            "Unten stehen die echten Feldnamen."
        )

        with st.expander(
            "Alle Felder eines Spielers"
        ):
            st.write(sorted(players[0].keys()))
            st.json(players[0])

else:
    st.info(
        "Für diesen Manager wurden keine Spieler "
        "mit Marktwert gefunden."
    )

    if squad_result is not None:
        with st.expander(
            "Sichere Struktur anzeigen"
        ):
            st.json(
                safe_structure(squad_result)
            )
