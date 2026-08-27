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
    "trp",
]

TOTAL_PROFIT_KEYS = [
    "profit",
    "prof",
    "totalProfit",
    "tpr",
    "prft",
    "gain",
]

DAILY_CHANGE_KEYS = [
    "tfhmvt",
    "mvt",
    "sdmvt",
    "dmv",
]

# Das Feld "lo" enthält den Platz in der Startelf.
# Werte 0 bis 10 bedeuten aufgestellt.
# Der Wert None bedeutet Bank.
LINEUP_FIELD = "lo"


def get_market_value(player):
    """Liest den aktuellen Marktwert."""
    return to_number(
        first_value(player, MARKET_VALUE_KEYS)
    )


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
# Suche in verschachtelten Antworten
# ---------------------------------------------------------

def search_keys(value, keys, depth=0):
    """Sucht rekursiv nach dem ersten passenden Zahlenfeld."""
    if depth > 5:
        return None

    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] is not None:
                number = to_number(value[key])

                if number is not None:
                    return number

        for nested_value in value.values():
            result = search_keys(
                nested_value,
                keys,
                depth + 1,
            )

            if result is not None:
                return result

    if isinstance(value, list):
        for item in value:
            result = search_keys(
                item,
                keys,
                depth + 1,
            )

            if result is not None:
                return result

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
            "pl",
        ],
    )


def collect_money_fields(value, prefix="", depth=0):
    """Sammelt alle Zahlenfelder mit großen Beträgen."""
    found = {}

    if depth > 4:
        return found

    if isinstance(value, dict):
        for key, nested_value in value.items():
            path = f"{prefix}{key}"

            number = to_number(nested_value)

            if number is not None and abs(number) >= 50_000:
                found[path] = format_signed_currency(
                    number
                )

            found.update(
                collect_money_fields(
                    nested_value,
                    f"{path}.",
                    depth + 1,
                )
            )

    if isinstance(value, list) and value:
        found.update(
            collect_money_fields(
                value[0],
                f"{prefix}0.",
                depth + 1,
            )
        )

    return found


# ---------------------------------------------------------
# Transfers erkennen
# ---------------------------------------------------------

def extract_transfer_events(data, depth=0):
    """
    Sammelt alle Einträge, die wie ein Transfer aussehen.

    Ein Transfer hat eine Spieler-ID und einen Preis.
    """
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
            [
                "trp",
                "price",
                "pr",
                "value",
                "v",
                "tp",
            ],
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
    """
    Berechnet den realisierten Gewinn.

    Gewinn entsteht, wenn ein Spieler gekauft
    und danach wieder verkauft wurde.
    """
    events = []
    raw_samples = []

    # Transferhistorie des Managers versuchen
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

    # Liga-Feed durchgehen
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

    # Käufe und Verkäufe je Spieler sortieren
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

    # Gewinn nur für verkaufte Spieler
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
                    "Kaufpreis": format_currency(
                        buy_price
                    )
                    if known_price
                    else "Zulosung",
                    "Verkaufspreis": format_currency(
                        sale_price
                    ),
                    "Gewinn": format_signed_currency(
                        profit
                    ),
                }
            )

    return realized, trades, purchases, raw_samples


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

load_details = st.sidebar.checkbox(
    "Spielerdetails laden",
    value=True,
)

show_realized = st.sidebar.checkbox(
    "Realisierten Gewinn laden",
    value=True,
)

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

try:
    with st.spinner("Kader wird geladen …"):
        squad_result = api.get_manager_squad(
            league_id,
            selected_manager_id,
        )

    players = find_players_with_value(squad_result)

except Exception as error:
    squad_error = str(error)


# ---------------------------------------------------------
# Transfers lesen
# ---------------------------------------------------------

realized_profit = None
realized_trades = []
feed_purchases = {}
feed_samples = []

if show_realized and players:
    with st.spinner("Transferhistorie wird gelesen …"):
        (
            realized_profit,
            realized_trades,
            feed_purchases,
            feed_samples,
        ) = load_feed_transfers(
            api,
            league_id,
            selected_manager_id,
        )


# ---------------------------------------------------------
# Spielerdetails laden
# ---------------------------------------------------------

price_by_player = {}
profit_by_player = {}
detail_samples = {}

if load_details and players:
    with st.spinner(
        f"Details für {len(players)} Spieler …"
    ):
        for player in players:
            player_id = get_player_id(player)

            if player_id is None:
                continue

            try:
                detail = api.get_player_detail(
                    league_id,
                    player_id,
                )
            except Exception:
                continue

            profit = search_keys(
                detail,
                TOTAL_PROFIT_KEYS,
            )

            if profit is not None:
                profit_by_player[player_id] = profit

            price = search_keys(
                detail,
                BUY_PRICE_KEYS,
            )

            if price is not None:
                price_by_player[player_id] = price

            if len(detail_samples) < 2:
                detail_samples[
                    get_player_name(player)
                ] = detail


# Kaufpreise aus dem Feed ergänzen
for player in players:
    player_id = get_player_id(player)

    if player_id is None:
        continue

    if player_id in price_by_player:
        continue

    feed_prices = feed_purchases.get(player_id)

    if feed_prices:
        price_by_player[player_id] = feed_prices[-1]


def player_buy_price(player):
    """
    Gibt den Einstandspreis zurück.

    1. Aus der Detailansicht oder dem Feed
    2. Aus dem Kaderobjekt
    3. Marktwert minus bekannter Gewinn
    """
    player_id = get_player_id(player)

    if player_id in price_by_player:
        return price_by_player[player_id]

    direct = to_number(
        first_value(player, BUY_PRICE_KEYS)
    )

    if direct is not None:
        return direct

    profit = profit_by_player.get(player_id)
    market_value = get_market_value(player)

    if profit is not None and market_value is not None:
        return market_value - profit

    return None


def player_total_profit(player):
    """
    Gibt den Gesamtgewinn zurück.

    1. Direkt aus der API
    2. Marktwert minus Einstandspreis
    3. Ohne Preisangabe: 0
    """
    player_id = get_player_id(player)

    if player_id in profit_by_player:
        return profit_by_player[player_id]

    market_value = get_market_value(player)
    buy_price = player_buy_price(player)

    if market_value is None:
        return None

    if buy_price is not None:
        return market_value - buy_price

    return 0.0


# ---------------------------------------------------------
# Kennzahlen berechnen
# ---------------------------------------------------------

squad_value = 0.0
lineup_value = 0.0
trading_value = 0.0
profit_in_club = 0.0
daily_change_total = 0.0

lineup_count = 0
trading_count = 0

for player in players:
    market_value = get_market_value(player) or 0.0
    squad_value += market_value

    daily_change_total += get_daily_change(player) or 0.0

    profit = player_total_profit(player)

    if profit is not None:
        profit_in_club += profit

    if is_in_lineup(player):
        lineup_value += market_value
        lineup_count += 1
    else:
        trading_value += market_value
        trading_count += 1


# ---------------------------------------------------------
# KPI-Anzeige
# ---------------------------------------------------------

st.subheader(
    f"📊 Kennzahlen: {selected_manager_name}"
)

row1_col1, row1_col2, row1_col3, row1_col4 = (
    st.columns(4)
)

row1_col1.metric(
    "Kaderwert",
    format_currency(squad_value),
    help=f"{len(players)} Spieler",
)

row1_col2.metric(
    "Start 11",
    format_currency(lineup_value),
    help=f"{lineup_count} Spieler aufgestellt",
)

row1_col3.metric(
    "Trading Spieler",
    format_currency(trading_value),
    help=f"{trading_count} Spieler auf der Bank",
)

row1_col4.metric(
    "Spieler im Verein",
    len(players),
    help=(
        f"{lineup_count} in der Startelf, "
        f"{trading_count} auf der Bank"
    ),
)

row2_col1, row2_col2, row2_col3, row2_col4 = (
    st.columns(4)
)

row2_col1.metric(
    "Gewinn im Verein",
    format_signed_currency(profit_in_club),
)

row2_col2.metric(
    "Gewinn realisiert",
    format_signed_currency(realized_profit)
    if realized_profit is not None
    else "—",
    help=f"{len(realized_trades)} Verkäufe erkannt",
)

total_profit = profit_in_club

if realized_profit is not None:
    total_profit = profit_in_club + realized_profit

row2_col3.metric(
    "Gewinn gesamt",
    format_signed_currency(total_profit),
)

row2_col4.metric(
    "Änderung 24 Stunden",
    format_signed_currency(daily_change_total),
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

        slot = get_lineup_slot(player)

        if slot is None:
            status = "Trading"
        else:
            status = "Start 11"

        profit = player_total_profit(player)

        player_rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": position_name,
                "Status": status,
                "Einstandspreis": format_currency(
                    player_buy_price(player)
                ),
                "Marktwert": format_currency(
                    get_market_value(player)
                ),
                "Gewinn gesamt": format_signed_currency(
                    profit
                ),
                "Änderung 24 Stunden": (
                    format_signed_currency(
                        get_daily_change(player)
                    )
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
    st.info("Keine Spieler gefunden.")


# ---------------------------------------------------------
# Verkaufte Spieler
# ---------------------------------------------------------

if realized_trades:
    st.subheader("💸 Verkaufte Spieler")

    st.dataframe(
        pd.DataFrame(realized_trades),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# Diagnose
# ---------------------------------------------------------

st.markdown("---")

with st.expander("🔎 Diagnose"):
    st.write("**Geldbeträge aus der Detailansicht:**")

    for name, detail in detail_samples.items():
        st.write(f"**{name}**")

        money_fields = collect_money_fields(detail)

        if money_fields:
            money_rows = [
                {"Feld": key, "Wert": value}
                for key, value in sorted(
                    money_fields.items()
                )
            ]

            st.dataframe(
                pd.DataFrame(money_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.write("Keine Beträge gefunden.")

    st.write("**Erkannte Transfers:**")

    if realized_trades:
        st.dataframe(
            pd.DataFrame(realized_trades),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("Keine Transfers erkannt.")

    st.write("**Rohdaten der Transferquellen:**")

    if feed_samples:
        for sample in feed_samples:
            with st.expander(sample["Quelle"]):
                st.json(sample["Daten"])
    else:
        st.write("Keine Quelle hat geantwortet.")
Voraussetzung in kickbase_api.py
Falls noch nicht geschehen, muss dort diese Methode vorhanden sein:

    def get_manager_transfers(self, league_id, manager_id):
        """Lädt die Transferhistorie eines Managers."""
        paths = [
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/transfers",
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/activities",
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/performance",
        ]

        return self.try_paths(paths)
