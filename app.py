"""
Kickbase Liga-Dashboard.

KPIs: Kaderwert, Start 11, Trading, Gewinne.
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
# Feldnamen
# ---------------------------------------------------------

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
]

PROFIT_KEYS = [
    "profit",
    "prof",
    "pf",
    "gain",
    "sp",
]

# Felder, die auf einen Startelf-Platz hindeuten
LINEUP_KEYS = [
    "lineupPosition",
    "lp",
    "lo",
    "lineup",
    "inLineup",
    "isLineup",
    "lpo",
    "lst",
]


def get_market_value(player):
    """Liest den Marktwert eines Spielers."""
    return to_number(
        first_value(player, MARKET_VALUE_KEYS)
    )


def get_raw_buy_price(player):
    """Liest den echten Kaufpreis aus der API."""
    return to_number(
        first_value(player, BUY_PRICE_KEYS)
    )


def get_raw_profit(player):
    """Liest einen vorhandenen Gewinnwert."""
    return to_number(
        first_value(player, PROFIT_KEYS)
    )


def get_buy_price(player):
    """
    Ermittelt den Einstandspreis.

    1. Kaufpreis aus der API
    2. Marktwert minus Gewinn
    3. Sonst 0 (zugeloster Spieler)
    """
    raw_price = get_raw_buy_price(player)

    if raw_price is not None:
        return raw_price

    market_value = get_market_value(player)
    profit = get_raw_profit(player)

    if market_value is not None and profit is not None:
        return market_value - profit

    # Zugeloste Spieler haben keinen Einstandspreis.
    return 0.0


def get_player_profit(player):
    """
    Ermittelt den Gewinn eines Spielers.

    1. Gewinn aus der API
    2. Marktwert minus Einstandspreis
    """
    direct_profit = get_raw_profit(player)

    if direct_profit is not None:
        return direct_profit

    market_value = get_market_value(player)

    if market_value is None:
        return None

    return market_value - get_buy_price(player)


def get_price_source(player):
    """Gibt an, woher der Einstandspreis stammt."""
    if get_raw_buy_price(player) is not None:
        return "Kaufpreis"

    if get_raw_profit(player) is not None:
        return "Berechnet"

    return "Zulosung"


def is_in_lineup(player):
    """
    Prüft, ob ein Spieler aufgestellt ist.

    Gibt None zurück, wenn es kein Feld dazu gibt.
    """
    for key in LINEUP_KEYS:
        if key not in player:
            continue

        value = player[key]

        if isinstance(value, bool):
            return value

        number = to_number(value)

        if number is not None:
            # 0 bedeutet meist Bank
            return number > 0

    return None


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
# Realisierter Gewinn aus dem Feed
# ---------------------------------------------------------

def load_realized_profit(api, league_id, manager_id):
    """
    Berechnet den realisierten Gewinn aus dem Liga-Feed.

    Sammelt Käufe und Verkäufe eines Managers.
    """
    all_items = []

    for start in range(0, 200, 25):
        try:
            sources, _ = api.get_league_feed(
                league_id,
                start,
            )
        except Exception:
            break

        page_items = []

        for source in sources:
            data = source["data"]

            if isinstance(data, dict):
                items = (
                    data.get("af")
                    or data.get("items")
                    or data.get("it")
                    or []
                )

                if isinstance(items, list):
                    page_items.extend(items)

        if not page_items:
            break

        all_items.extend(page_items)

    # Käufe und Verkäufe je Spieler sammeln
    purchases = {}
    sales = {}

    for item in all_items:
        if not isinstance(item, dict):
            continue

        meta = first_value(item, ["meta", "m", "data"], {})

        if not isinstance(meta, dict):
            meta = {}

        # Manager-ID prüfen
        item_manager = first_value(
            meta,
            ["byr", "slr", "uid", "ui", "userId"],
        )

        if item_manager is None:
            item_manager = first_value(
                item,
                ["byr", "slr", "uid", "ui", "userId"],
            )

        buyer = first_value(meta, ["byr", "buyerId"])
        seller = first_value(meta, ["slr", "sellerId"])

        player_id = first_value(
            meta,
            ["pi", "playerId", "pid"],
        )

        amount = to_number(
            first_value(
                meta,
                ["trp", "price", "pr", "v", "value"],
            )
        )

        if amount is None or player_id is None:
            continue

        if str(buyer) == str(manager_id):
            purchases.setdefault(
                str(player_id), []
            ).append(amount)

        if str(seller) == str(manager_id):
            sales.setdefault(
                str(player_id), []
            ).append(amount)

    # Gewinn nur für Spieler, die gekauft UND verkauft wurden
    realized = 0.0
    trades = []

    for player_id, sale_prices in sales.items():
        buy_prices = purchases.get(player_id, [])

        for index, sale_price in enumerate(sale_prices):
            if index < len(buy_prices):
                buy_price = buy_prices[index]
            else:
                buy_price = 0.0

            profit = sale_price - buy_price
            realized += profit

            trades.append(
                {
                    "Spieler-ID": player_id,
                    "Kaufpreis": format_currency(
                        buy_price
                    ),
                    "Verkaufspreis": format_currency(
                        sale_price
                    ),
                    "Gewinn": format_signed_currency(
                        profit
                    ),
                }
            )

    return realized, trades, len(all_items)


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

show_realized = st.sidebar.checkbox(
    "Realisierten Gewinn laden",
    value=True,
    help="Lädt den Liga-Feed. Dauert etwas länger.",
)

st.title(f"⚽ {league_name}")


# ---------------------------------------------------------
# Manager laden
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
# Manager auswählen
# ---------------------------------------------------------

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
# Kader laden
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
# Kennzahlen berechnen
# ---------------------------------------------------------

squad_value = 0.0
lineup_value = 0.0
trading_value = 0.0
profit_in_club = 0.0

lineup_count = 0
trading_count = 0
lineup_detected = False

for player in players:
    market_value = get_market_value(player) or 0.0
    profit = get_player_profit(player) or 0.0

    squad_value += market_value
    profit_in_club += profit

    in_lineup = is_in_lineup(player)

    if in_lineup is None:
        continue

    lineup_detected = True

    if in_lineup:
        lineup_value += market_value
        lineup_count += 1
    else:
        trading_value += market_value
        trading_count += 1


# ---------------------------------------------------------
# Realisierter Gewinn
# ---------------------------------------------------------

realized_profit = None
realized_trades = []
feed_count = 0

if show_realized and players:
    with st.spinner(
        "Realisierter Gewinn wird berechnet …"
    ):
        (
            realized_profit,
            realized_trades,
            feed_count,
        ) = load_realized_profit(
            api,
            league_id,
            selected_manager_id,
        )


# ---------------------------------------------------------
# KPI-Anzeige
# ---------------------------------------------------------

st.subheader(
    f"📊 Kennzahlen: {selected_manager_name}"
)

row1_col1, row1_col2, row1_col3 = st.columns(3)

row1_col1.metric(
    "Kaderwert",
    format_currency(squad_value),
    help=f"{len(players)} Spieler",
)

row1_col2.metric(
    "Start 11",
    format_currency(lineup_value)
    if lineup_detected
    else "—",
    help=f"{lineup_count} Spieler aufgestellt",
)

row1_col3.metric(
    "Trading Spieler",
    format_currency(trading_value)
    if lineup_detected
    else "—",
    help=f"{trading_count} Spieler nicht aufgestellt",
)

row2_col1, row2_col2, row2_col3 = st.columns(3)

row2_col1.metric(
    "Gewinn im Verein",
    format_signed_currency(profit_in_club),
)

row2_col2.metric(
    "Gewinn realisiert",
    format_signed_currency(realized_profit)
    if realized_profit is not None
    else "—",
)

total_profit = profit_in_club

if realized_profit is not None:
    total_profit = profit_in_club + realized_profit

row2_col3.metric(
    "Gewinn gesamt",
    format_signed_currency(total_profit),
)

if not lineup_detected and players:
    st.info(
        "Die Aufstellung konnte nicht erkannt werden. "
        "Start 11 und Trading bleiben leer."
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

        in_lineup = is_in_lineup(player)

        if in_lineup is True:
            status = "Start 11"
        elif in_lineup is False:
            status = "Trading"
        else:
            status = "—"

        profit = get_player_profit(player)

        player_rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": position_name,
                "Status": status,
                "Einstandspreis": format_currency(
                    get_buy_price(player)
                ),
                "Quelle": get_price_source(player),
                "Marktwert": format_currency(
                    get_market_value(player)
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

else:
    st.info(
        "Für diesen Manager wurden keine Spieler "
        "gefunden."
    )


# ---------------------------------------------------------
# Diagnose
# ---------------------------------------------------------

st.markdown("---")

with st.expander("🔎 Diagnose"):
    st.write(
        f"Feed-Einträge geladen: {feed_count}"
    )

    if realized_trades:
        st.write("**Abgeschlossene Trades:**")
        st.dataframe(
            pd.DataFrame(realized_trades),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("Keine Trades erkannt.")

    if players:
        st.write("**Felder eines Spielers:**")
        st.write(sorted(players[0].keys()))
        st.json(players[0])
