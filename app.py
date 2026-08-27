"""
Kickbase Liga-Dashboard.

Ansichten: Manager und Liga.
Optimiert fuer Desktop und Handy.
"""

from datetime import datetime, timezone

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

# Startbudget jedes Managers zu Saisonbeginn
DEFAULT_START_BUDGET = 150_000_000


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
    """
    Berechnet die volle Tabellenhöhe.

    So entsteht kein zusätzliches Scrollfenster.
    """
    row_height = 30 if compact else 35
    header = 34 if compact else 38

    return int(header + row_count * row_height)


def sort_controls(frame, columns, key, default_column,
                  compact=False):
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


def get_short_player_name(player):
    """Gibt einen kurzen Namen für die Handyansicht."""
    last_name = first_value(
        player,
        ["lastName", "ln", "pln"],
    )

    if last_name:
        return str(last_name)

    return get_player_name(player)


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
# Spieltag ermitteln
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
    """Wandelt einen Datumstext in ein Datum um."""
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


def collect_future_dates(data, depth=0):
    """Sammelt alle Datumsangaben, die in der Zukunft liegen."""
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

    if isinstance(data, list):
        for item in data:
            found.extend(
                collect_future_dates(item, depth + 1)
            )

    return found


def find_days_to_matchday(api, league_id):
    """
    Sucht das naechste Spieltagsdatum in der API.

    Rueckgabe: (tage, quelle).
    """
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

        days = (next_date - now).days

        if days < 0:
            days = 0

        return days, path

    return None, None


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


def compute_budget(stats, total_profit, start_budget,
                   days_to_matchday, real_balance=None):
    """
    Ermittelt das Budget eines Managers.

    Wenn real_balance gesetzt ist, wird dieser echte
    Kontostand genutzt. Sonst wird geschaetzt:
    Startbudget plus Gewinn gesamt minus Kaderwert.
    """
    if real_balance is not None:
        balance = real_balance
        is_real = True
    else:
        balance = (
            start_budget
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
    """Formatiert und färbt die Kadertabelle."""

    def color_row(row):
        """Graut Zeilen von Trading Spielern aus."""
        if row.get("Status") == "Trading":
            return [
                "color: #9a9a9a; "
                "background-color: #f7f7f7"
            ] * len(row)

        return [""] * len(row)

    styled = frame.style

    if "Status" in frame.columns:
        styled = styled.apply(color_row, axis=1)

    signed_columns = [
        column for column in [
            "Gewinn gesamt",
            "Trend 24 Stunden",
        ]
        if column in frame.columns
    ]

    if signed_columns:
        styled = styled.map(
            color_by_value,
            subset=signed_columns,
        )

    formats = {}

    for column in ["Einstandspreis", "Marktwert"]:
        if column in frame.columns:
            formats[column] = currency_formatter

    for column in signed_columns:
        formats[column] = signed_formatter

    return styled.format(formats)


def style_league_table(frame):
    """Formatiert und färbt die Liga-Tabelle."""
    signed_columns = [
        column for column in [
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
        column for column in [
            "Start 11",
            "Trading",
            "Kaderwert",
        ]
        if column in frame.columns
    ]

    styled = frame.style

    if signed_columns:
        styled = styled.map(
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

def kpi_block(title, entries, compact=False):
    """Zeigt einen KPI-Block mit Überschrift und Spalten."""
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
        f"letter-spacing:0.08em;text-transform:uppercase;"
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


def build_budget_kpis(budget, stats, start_budget,
                      days_to_matchday, days_source,
                      budget_source):
    """Baut die Einträge für den Budget-Block."""
    if budget["is_real"]:
        balance_notes = [
            "echter Kontostand aus der API",
            str(budget_source),
        ]
    else:
        balance_notes = [
            f"Start: {format_currency(start_budget)}",
            "geschätzt: plus Gewinn, minus Kaderwert",
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
                f"plus Trading: "
                f"{format_currency(stats['trading_value'])}",
                f"{stats['trading_count']} Spieler",
            ],
            tone_of(budget["after_sale"]),
        ),
        (
            "Am Spieltag",
            format_signed_currency(budget["at_matchday"]),
            [
                f"{days_to_matchday} Tage "
                f"({days_source})",
                f"Trend Trading: "
                f"{format_signed_currency(stats['trend_trading'])}"
                f" pro Tag",
            ],
            tone_of(budget["at_matchday"]),
        ),
    ]


# ---------------------------------------------------------
# Seiteneinstellungen
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
    /* Reiter in der Seitenleiste */
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

    /* Handyansicht: schmale Bildschirme */
    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            padding-top: 2.5rem !important;
        }
        h1 {
            font-size: 1.35rem !important;
        }
        h2, h3 {
            font-size: 1.05rem !important;
        }
        .kpi-value {
            font-size: 18px !important;
        }
        .kpi-title {
            margin-top: 14px !important;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.2rem !important;
        }
        div[data-testid="stHorizontalBlock"]
        > div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        div[data-testid="stDataFrame"] {
            font-size: 12px !important;
        }
        .stCaption, div[data-testid="stCaptionContainer"] {
            font-size: 11px !important;
        }
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
# Handy-Ansicht
# ---------------------------------------------------------

compact = st.sidebar.toggle(
    "📱 Handy-Ansicht",
    value=False,
    help="Zeigt weniger Spalten und weniger Zusatztexte.",
)

st.sidebar.markdown("---")


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
    value=not compact,
    help="Liest die Transferhistorie. Dauert länger.",
)

kpis_expanded = st.sidebar.checkbox(
    "Kennzahlen aufgeklappt starten",
    value=False,
    help="Aus bedeutet: Mannschaft steht sofort im Fokus.",
)


# ---------------------------------------------------------
# Budget-Einstellungen
# ---------------------------------------------------------

st.sidebar.markdown("---")

st.sidebar.markdown(
    f"<div style='font-size:12px;font-weight:500;"
    f"letter-spacing:0.08em;text-transform:uppercase;"
    f"color:{COLOR_LABEL};margin-bottom:8px;'>"
    f"Budget</div>",
    unsafe_allow_html=True,
)

start_budget_mio = st.sidebar.number_input(
    "Startbudget in Mio. €",
    min_value=0.0,
    max_value=500.0,
    value=DEFAULT_START_BUDGET / 1_000_000,
    step=5.0,
    help="Nur für die Schätzung fremder Manager.",
)

start_budget = start_budget_mio * 1_000_000

# Echter Kontostand des eigenen Accounts
budget_key = f"own_budget_{league_id}"

if budget_key not in st.session_state:
    with st.spinner("Eigener Kontostand wird gelesen …"):
        st.session_state[budget_key] = load_real_budget(
            api,
            league_id,
        )

own_budget, own_budget_source = st.session_state[budget_key]

if own_budget is not None:
    st.sidebar.caption(
        f"Eigener Kontostand: "
        f"{format_currency(own_budget)}"
    )
else:
    st.sidebar.caption(
        "Eigener Kontostand nicht gefunden, "
        "es wird geschätzt."
    )

# Tage bis zum Spieltag aus der API suchen
matchday_key = f"matchday_days_{league_id}"

if matchday_key not in st.session_state:
    with st.spinner("Spieltag wird gesucht …"):
        found_days, found_path = find_days_to_matchday(
            api,
            league_id,
        )

    st.session_state[matchday_key] = (
        found_days,
        found_path,
    )

found_days, found_path = st.session_state[matchday_key]

if found_days is None:
    default_days = 3
    days_hint = "kein Endpunkt gefunden, bitte selbst setzen"
else:
    default_days = found_days
    days_hint = f"gefunden über {found_path}"

days_to_matchday = st.sidebar.number_input(
    "Tage bis zum Spieltag",
    min_value=0,
    max_value=30,
    value=int(default_days),
    step=1,
    help=days_hint,
)

if found_days is not None and days_to_matchday == found_days:
    days_source = "aus der API"
else:
    days_source = "manuell"

st.sidebar.caption(days_hint)

st.sidebar.markdown("---")

if st.sidebar.button("Abmelden", key="logout"):
    st.session_state.clear()
    st.rerun()

if compact:
    st.markdown(
        f"<div style='font-size:15px;font-weight:600;"
        f"padding-bottom:6px;'>⚽ {league_name}</div>",
        unsafe_allow_html=True,
    )
else:
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
    st.subheader("Liga-Vergleich")

    st.caption(
        "Ein Klick auf eine Zeile öffnet die "
        "Detailansicht des Managers. "
        "Der eigene Account ist mit einem Punkt markiert."
    )

    cache_key = f"league_rows_v4_{league_id}"

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

            own = is_own_manager(api, manager_id)

            rows.append(
                {
                    "Manager": manager_name,
                    "Ich": own,
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

    if "_sort" in league_frame.columns:
        league_frame = league_frame.drop(
            columns=["_sort"]
        )

    # Geschaetzter Kontostand
    league_frame["Kontostand"] = (
        start_budget
        + league_frame["Gewinn gesamt"]
        - league_frame["Kaderwert"]
    )

    # Fuer den eigenen Account den echten Wert einsetzen
    if own_budget is not None and "Ich" in league_frame.columns:
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

    # Eigenen Namen markieren
    if "Ich" in league_frame.columns:
        league_frame["Manager"] = [
            f"● {name}" if own else name
            for name, own in zip(
                league_frame["Manager"],
                league_frame["Ich"],
            )
        ]

        league_frame = league_frame.drop(columns=["Ich"])

    if compact:
        visible_columns = [
            "Manager",
            "Kaderwert",
            "Gewinn gesamt",
            "Trend gesamt",
            "Kontostand",
        ]
    else:
        visible_columns = [
            "Manager",
            "Start 11",
            "Trading",
            "Kaderwert",
            "Spieler",
            "Gewinn gesamt",
            "Trend Start 11",
            "Trend Trading",
            "Trend gesamt",
            "Kontostand",
            "Nach Verkauf",
            "Am Spieltag",
        ]

    league_frame = league_frame[
        [
            column for column in visible_columns
            if column in league_frame.columns
        ]
    ]

    league_frame = sort_controls(
        league_frame,
        visible_columns,
        key="liga",
        default_column="Kaderwert",
        compact=compact,
    )

    sorted_names = [
        name.replace("● ", "")
        for name in league_frame["Manager"].tolist()
    ]

    selection = st.dataframe(
        style_league_table(league_frame),
        use_container_width=True,
        hide_index=True,
        height=table_height(len(league_frame), compact),
        on_select="rerun",
        selection_mode="single-row",
        key="league_table",
    )

    if own_budget is not None:
        st.caption(
            f"Eigener Kontostand echt aus der API, "
            f"alle anderen geschätzt mit "
            f"{format_currency(start_budget)} Startbudget "
            f"und {days_to_matchday} Tagen bis zum Spieltag."
        )
    else:
        st.caption(
            f"Alle Kontostände geschätzt mit "
            f"{format_currency(start_budget)} Startbudget "
            f"und {days_to_matchday} Tagen bis zum Spieltag."
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

st.session_state["selected_manager_index"] = manager_index

selected_manager = managers[manager_index]
selected_manager_id = get_manager_id(selected_manager)
selected_manager_name = get_manager_name(
    selected_manager
)

viewing_self = is_own_manager(api, selected_manager_id)


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

# Beim eigenen Account den echten Kontostand nutzen
real_balance = own_budget if viewing_self else None

budget = compute_budget(
    stats,
    total_profit,
    start_budget,
    days_to_matchday,
    real_balance=real_balance,
)


# ---------------------------------------------------------
# KPI-Anzeige, einklappbar
# ---------------------------------------------------------

open_kpis = kpis_expanded or st.session_state.get(
    "came_from_league",
    False,
)

title_marker = " ●" if viewing_self else ""

with st.expander(
    f"Kennzahlen: {selected_manager_name}{title_marker}",
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
        compact=compact,
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
            start_budget,
            days_to_matchday,
            days_source,
            own_budget_source,
        ),
        compact=compact,
    )

    st.markdown("")


# ---------------------------------------------------------
# Kadertabelle, immer vollständig sichtbar
# ---------------------------------------------------------

if compact:
    st.subheader("Kader")
else:
    st.subheader(f"Kader von {selected_manager_name}")

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

        name = (
            get_short_player_name(player)
            if compact
            else get_player_name(player)
        )

        player_rows.append(
            {
                "Spieler": name,
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

    if compact:
        visible_columns = [
            "Spieler",
            "Status",
            "Marktwert",
            "Gewinn gesamt",
            "Trend 24 Stunden",
        ]
    else:
        visible_columns = [
            "Spieler",
            "Position",
            "Status",
            "Einstandspreis",
            "Marktwert",
            "Gewinn gesamt",
            "Trend 24 Stunden",
        ]

    player_frame = player_frame[visible_columns]

    player_frame = sort_controls(
        player_frame,
        visible_columns,
        key="kader",
        default_column="Gewinn gesamt",
        compact=compact,
    )

    st.dataframe(
        style_player_table(player_frame),
        use_container_width=True,
        hide_index=True,
        height=table_height(len(player_frame), compact),
    )

    st.caption("Trading Spieler sind ausgegraut.")

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
        height=table_height(len(trades_frame), compact),
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
# Diagnosebereiche, am Handy ausgeblendet
# ---------------------------------------------------------

if not compact:
    with st.expander("Alle Daten zu diesem Manager"):
        st.write(
            "Eigene Benutzer-ID: "
            + str(getattr(api, "own_user_id", "unbekannt"))
        )

        if st.button("Manager-Daten laden"):
            with st.spinner(
                "Endpunkte werden getestet …"
            ):
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
                    content = ", ".join(
                        sorted(data.keys())
                    )
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

            st.write(
                "**Inhalt der einzelnen Endpunkte:**"
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
            with st.expander("Endpunkte ohne Antwort"):
                st.write(manager_errors)

    with st.expander("Diagnose der Transferquellen"):
        if feed_samples:
            for sample in feed_samples:
                with st.expander(sample["Quelle"]):
                    st.json(sample["Daten"])
        else:
            st.write("Keine Quelle hat geantwortet.")
