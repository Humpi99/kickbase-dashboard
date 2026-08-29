"""
Transfermarkt-Ansicht für das Kickbase-Dashboard.

Die Feldnamen der inoffiziellen Kickbase-API können abweichen.
Deshalb werden mehrere mögliche Bezeichnungen geprüft.
"""

from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st


COLOR_POSITIVE = "#12a150"
COLOR_NEGATIVE = "#e03131"
COLOR_NEUTRAL = "#1c1c1c"

POSITION_NAMES = {
    1: "Torwart",
    2: "Abwehr",
    3: "Mittelfeld",
    4: "Sturm",
}

MARKET_VALUE_KEYS = [
    "mv",
    "marketValue",
    "currentValue",
    "cv",
]

PLAYER_ID_KEYS = [
    "id",
    "i",
    "playerId",
    "pi",
    "pid",
]

FIRST_NAME_KEYS = [
    "firstName",
    "fn",
    "pfn",
]

LAST_NAME_KEYS = [
    "lastName",
    "ln",
    "pln",
]

FULL_NAME_KEYS = [
    "name",
    "n",
    "playerName",
    "pn",
]

POSITION_KEYS = [
    "position",
    "pos",
]

CLUB_NAME_KEYS = [
    "teamName",
    "clubName",
    "club",
    "team",
    "tn",
    "cn",
]

DAILY_CHANGE_KEYS = [
    "tfhmvt",
    "mvt",
    "sdmvt",
    "dmv",
    "dailyChange",
    "marketValueChange",
]

PRICE_KEYS = [
    "prc",
    "price",
    "buyPrice",
    "purchasePrice",
    "marketPrice",
    "bid",
    "trp",
]

POINTS_KEYS = [
    "points",
    "pts",
    "totalPoints",
    "tp",
    "p",
]

AVERAGE_POINTS_KEYS = [
    "averagePoints",
    "avgPoints",
    "average",
    "avg",
    "ap",
    "ppg",
]

STATUS_KEYS = [
    "status",
    "playerStatus",
    "st",
]

PROBABILITY_KEYS = [
    "probability",
    "lineupProbability",
    "appearanceProbability",
    "prob",
    "lp",
]

EXPIRY_KEYS = [
    "expires",
    "expiresAt",
    "expiration",
    "expirationDate",
    "expiry",
    "expiryDate",
    "endDate",
    "deadline",
    "exs",
    "tm",
]

SELLER_CONTAINER_KEYS = [
    "seller",
    "sellerUser",
    "owner",
    "user",
    "manager",
    "usr",
    "u",
]

PLAYER_CONTAINER_KEYS = [
    "player",
    "playerData",
    "footballer",
    "pl",
]


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

    if isinstance(value, str):
        cleaned = value.strip()
        cleaned = cleaned.replace("€", "")
        cleaned = cleaned.replace(" ", "")

        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

        value = cleaned

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


def format_points(value):
    """Formatiert Punkte lesbar."""
    number = to_number(value)

    if number is None:
        return "—"

    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")

    return (
        f"{number:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def get_nested_dictionary(data, keys):
    """Sucht ein direkt enthaltenes Dictionary."""
    if not isinstance(data, dict):
        return None

    for key in keys:
        value = data.get(key)

        if isinstance(value, dict):
            return value

    return None


def merge_market_item(item):
    """Verbindet Angebotsdaten mit verschachtelten Spielerdaten."""
    if not isinstance(item, dict):
        return {}

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    if not player_data:
        return dict(item)

    merged = dict(player_data)
    merged.update(item)

    return merged


def get_player_id(item):
    """Ermittelt eine stabile Spieler-ID."""
    value = first_value(item, PLAYER_ID_KEYS)

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = first_value(player_data, PLAYER_ID_KEYS)

    if value is None:
        return None

    return str(value)


def get_player_name(item):
    """Ermittelt den Spielernamen."""
    first_name = first_value(item, FIRST_NAME_KEYS, "")
    last_name = first_value(item, LAST_NAME_KEYS, "")

    combined = f"{first_name} {last_name}".strip()

    if combined:
        return str(combined)

    full_name = first_value(item, FULL_NAME_KEYS)

    if full_name:
        return str(full_name)

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    if player_data:
        return get_player_name(player_data)

    return "Unbekannter Spieler"


def get_market_value(item):
    """Ermittelt den aktuellen Marktwert."""
    value = to_number(first_value(item, MARKET_VALUE_KEYS))

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(player_data, MARKET_VALUE_KEYS)
    )


def get_position(item):
    """Ermittelt die Spielerposition."""
    value = first_value(item, POSITION_KEYS)

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = first_value(player_data, POSITION_KEYS)

    number = to_number(value)

    if number is not None:
        return POSITION_NAMES.get(int(number), str(value))

    if value:
        return str(value)

    return "Unbekannt"


def get_club_name(item):
    """Ermittelt den Verein."""
    value = first_value(item, CLUB_NAME_KEYS)

    if isinstance(value, dict):
        value = first_value(
            value,
            ["name", "n", "teamName", "clubName"],
        )

    if value:
        return str(value)

    for container_key in [
        "team",
        "club",
        "teamData",
        "clubData",
    ]:
        container = item.get(container_key)

        if isinstance(container, dict):
            nested_value = first_value(
                container,
                ["name", "n", "teamName", "clubName"],
            )

            if nested_value:
                return str(nested_value)

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    if player_data:
        return get_club_name(player_data)

    return "Verein unbekannt"


def get_daily_change(item):
    """Ermittelt die Änderung der letzten 24 Stunden."""
    value = to_number(first_value(item, DAILY_CHANGE_KEYS))

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(player_data, DAILY_CHANGE_KEYS)
    )


def get_purchase_price(item):
    """Ermittelt den Kauf- oder Angebotspreis."""
    return to_number(first_value(item, PRICE_KEYS))


def get_points(item):
    """Ermittelt die Gesamtpunkte."""
    value = to_number(first_value(item, POINTS_KEYS))

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(first_value(player_data, POINTS_KEYS))


def get_average_points(item):
    """Ermittelt die Durchschnittspunkte."""
    value = to_number(
        first_value(item, AVERAGE_POINTS_KEYS)
    )

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(player_data, AVERAGE_POINTS_KEYS)
    )


def get_player_status(item):
    """Ermittelt den Spielerstatus."""
    value = first_value(item, STATUS_KEYS)

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = first_value(player_data, STATUS_KEYS)

    if value is None or value == "":
        return "—"

    return str(value)


def get_probability(item):
    """Ermittelt die Einsatzwahrscheinlichkeit."""
    value = to_number(first_value(item, PROBABILITY_KEYS))

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = to_number(
            first_value(player_data, PROBABILITY_KEYS)
        )

    if value is None:
        return "—"

    if 0 <= value <= 1:
        value *= 100

    return f"{value:.0f} %"


def get_seller_name(item):
    """Ermittelt den Anbieter eines Marktangebots."""
    for key in SELLER_CONTAINER_KEYS:
        value = item.get(key)

        if isinstance(value, dict):
            name = first_value(
                value,
                [
                    "name",
                    "unm",
                    "username",
                    "teamName",
                    "n",
                    "un",
                    "tn",
                ],
            )

            if name:
                return str(name)

    direct_name = first_value(
        item,
        [
            "sellerName",
            "ownerName",
            "managerName",
            "userName",
            "unm",
        ],
    )

    if direct_name:
        return str(direct_name)

    return "—"


def parse_datetime(value):
    """Versucht, einen Zeitwert als Datum zu lesen."""
    if value is None or isinstance(value, bool):
        return None

    number = to_number(value)

    if number is not None:
        try:
            if number > 10_000_000_000:
                number /= 1000

            if number > 1_000_000_000:
                return datetime.fromtimestamp(
                    number,
                    tz=timezone.utc,
                )
        except (ValueError, OSError, OverflowError):
            pass

    if not isinstance(value, str):
        return None

    cleaned = value.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def format_remaining_time(item):
    """Formatiert die verbleibende Angebotszeit."""
    value = first_value(item, EXPIRY_KEYS)

    if value is None:
        return "—"

    date_value = parse_datetime(value)

    if date_value is not None:
        remaining_seconds = int(
            (
                date_value - datetime.now(timezone.utc)
            ).total_seconds()
        )
    else:
        number = to_number(value)

        if number is None:
            return str(value)

        if 0 <= number <= 31_536_000:
            remaining_seconds = int(number)
        else:
            return "—"

    if remaining_seconds <= 0:
        return "Abgelaufen"

    days, rest = divmod(remaining_seconds, 24 * 60 * 60)
    hours, rest = divmod(rest, 60 * 60)
    minutes = rest // 60

    if days > 0:
        return f"{days} T. {hours} Std."

    if hours > 0:
        return f"{hours} Std. {minutes} Min."

    return f"{minutes} Min."


def collect_dictionaries(data, depth=0):
    """Sammelt rekursiv alle Dictionaries einer API-Antwort."""
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


def item_information_score(item):
    """Bewertet, welches Duplikat mehr Informationen enthält."""
    checks = [
        get_market_value(item),
        get_daily_change(item),
        get_purchase_price(item),
        get_points(item),
        get_average_points(item),
        get_player_status(item) != "—",
        get_probability(item) != "—",
        get_seller_name(item) != "—",
        format_remaining_time(item) != "—",
        get_club_name(item) != "Verein unbekannt",
    ]

    return sum(
        value is not None and value is not False
        for value in checks
    )


def extract_market_items(market_sources):
    """Extrahiert Marktspieler und entfernt Duplikate."""
    by_player_id = {}

    for source in market_sources:
        data = source.get("data")

        for raw_item in collect_dictionaries(data):
            item = merge_market_item(raw_item)

            player_id = get_player_id(item)
            market_value = get_market_value(item)

            if player_id is None or market_value is None:
                continue

            previous = by_player_id.get(player_id)

            if (
                previous is None
                or item_information_score(item)
                > item_information_score(previous)
            ):
                by_player_id[player_id] = item

    return list(by_player_id.values())


def build_market_rows(items):
    """Erstellt normalisierte Datensätze für die Kacheln."""
    rows = []

    for item in items:
        rows.append(
            {
                "player_id": get_player_id(item),
                "name": get_player_name(item),
                "position": get_position(item),
                "club": get_club_name(item),
                "market_value": get_market_value(item),
                "purchase_price": get_purchase_price(item),
                "daily_change": get_daily_change(item),
                "points": get_points(item),
                "average_points": get_average_points(item),
                "status": get_player_status(item),
                "probability": get_probability(item),
                "seller": get_seller_name(item),
                "remaining": format_remaining_time(item),
                "raw": item,
            }
        )

    return rows


def market_card(row):
    """
    Erstellt das HTML einer Spielerkachel.

    Wichtig: Das HTML darf keine Einrückung enthalten.
    Sonst zeigt Streamlit den Code als Text an.
    """
    daily_change = to_number(row["daily_change"])

    if daily_change is None or daily_change == 0:
        trend_color = COLOR_NEUTRAL
    elif daily_change > 0:
        trend_color = COLOR_POSITIVE
    else:
        trend_color = COLOR_NEGATIVE

    name = escape(str(row["name"]))
    club = escape(str(row["club"]))
    position = escape(str(row["position"]))
    seller = escape(str(row["seller"]))
    remaining = escape(str(row["remaining"]))
    status = escape(str(row["status"]))
    probability = escape(str(row["probability"]))

    parts = [
        "<article class='market-card'>",
        "<div class='market-card-header'>",
        "<div>",
        f"<div class='market-player-name'>{name}</div>",
        f"<div class='market-player-meta'>{club}</div>",
        "</div>",
        f"<div class='market-position'>{position}</div>",
        "</div>",
        "<div class='market-main-value'>"
        f"{format_currency(row['market_value'])}</div>",
        "<div class='market-main-label'>Marktwert</div>",
        "<div class='market-value-grid'>",
        "<div class='market-detail'><span>Kaufpreis</span>"
        f"<strong>{format_currency(row['purchase_price'])}"
        "</strong></div>",
        "<div class='market-detail'><span>Trend 24 Std."
        "</span>"
        f"<strong style='color:{trend_color};'>"
        f"{format_signed_currency(row['daily_change'])}"
        "</strong></div>",
        "<div class='market-detail'><span>Trend 3 Tage"
        "</span><strong>Mit Historie</strong></div>",
        "<div class='market-detail'><span>Anbieter</span>"
        f"<strong>{seller}</strong></div>",
        "<div class='market-detail'><span>Angebotszeit"
        f"</span><strong>{remaining}</strong></div>",
        "<div class='market-detail'><span>Punkte</span>"
        f"<strong>{format_points(row['points'])}"
        "</strong></div>",
        "<div class='market-detail'><span>Ø Punkte</span>"
        f"<strong>{format_points(row['average_points'])}"
        "</strong></div>",
        "<div class='market-detail'><span>Status</span>"
        f"<strong>{status}</strong></div>",
        "<div class='market-detail'><span>Einsatzchance"
        f"</span><strong>{probability}</strong></div>",
        "</div>",
        "</article>",
    ]

    return "".join(parts)


MARKET_STYLE = (
    "<style>"
    ".market-grid{display:grid;"
    "grid-template-columns:repeat(auto-fit,minmax(290px,1fr));"
    "gap:1rem;margin-top:1rem;margin-bottom:1.5rem;}"
    ".market-card{border:1px solid #e6e6e6;"
    "border-radius:14px;background:#ffffff;padding:1rem;"
    "box-shadow:0 2px 10px rgba(0,0,0,0.035);}"
    ".market-card-header{display:flex;"
    "align-items:flex-start;justify-content:space-between;"
    "gap:0.7rem;padding-bottom:0.8rem;"
    "border-bottom:1px solid #eeeeee;}"
    ".market-player-name{color:#1c1c1c;font-size:1.08rem;"
    "font-weight:750;line-height:1.25;}"
    ".market-player-meta{color:#777777;font-size:0.78rem;"
    "margin-top:0.2rem;}"
    ".market-position{color:#555555;background:#f3f3f3;"
    "border-radius:999px;padding:0.25rem 0.55rem;"
    "font-size:0.72rem;white-space:nowrap;}"
    ".market-main-value{color:#1c1c1c;font-size:1.55rem;"
    "font-weight:800;margin-top:0.9rem;}"
    ".market-main-label{color:#888888;font-size:0.74rem;"
    "margin-bottom:0.85rem;}"
    ".market-value-grid{display:grid;"
    "grid-template-columns:repeat(2,minmax(0,1fr));"
    "gap:0.65rem;}"
    ".market-detail{background:#fafafa;"
    "border:1px solid #f0f0f0;border-radius:9px;"
    "padding:0.55rem 0.6rem;min-width:0;}"
    ".market-detail span{display:block;color:#888888;"
    "font-size:0.68rem;margin-bottom:0.18rem;}"
    ".market-detail strong{display:block;color:#242424;"
    "font-size:0.82rem;overflow-wrap:anywhere;}"
    "@media (max-width:640px){"
    ".market-grid{grid-template-columns:1fr;gap:0.7rem;}"
    ".market-card{padding:0.8rem;border-radius:11px;}"
    ".market-main-value{font-size:1.3rem;}"
    ".market-detail{padding:0.48rem 0.5rem;}}"
    "</style>"
)


def render_transfer_market(api, league_id, compact=False):
    """Rendert die komplette Transfermarkt-Ansicht."""
    st.markdown(MARKET_STYLE, unsafe_allow_html=True)

    st.subheader("Transfermarkt")

    if not compact:
        st.caption(
            "Die Kacheln zeigen die aktuell von der "
            "Kickbase-API gelieferten Marktdaten. Der echte "
            "Drei-Tage-Trend folgt mit der Historie."
        )

    cache_key = f"transfer_market_v2_{league_id}"

    if st.button(
        "Transfermarkt neu laden",
        use_container_width=compact,
    ):
        st.session_state.pop(cache_key, None)
        st.rerun()

    if cache_key not in st.session_state:
        with st.spinner("Transfermarkt wird geladen …"):
            try:
                sources, errors = api.get_market(league_id)
            except Exception as error:
                sources = []
                errors = [str(error)]

            items = extract_market_items(sources)
            rows = build_market_rows(items)

            st.session_state[cache_key] = {
                "rows": rows,
                "sources": sources,
                "errors": errors,
            }

    market_data = st.session_state[cache_key]
    rows = market_data["rows"]
    sources = market_data["sources"]
    errors = market_data["errors"]

    if not rows:
        st.warning(
            "Es konnten noch keine Marktspieler sicher "
            "erkannt werden. Öffne unten die Diagnose."
        )

        if sources:
            with st.expander(
                "Diagnose der Transfermarkt-Rohdaten",
                expanded=True,
            ):
                for source in sources:
                    st.write(f"**{source['path']}**")
                    st.json(source["data"])

        if errors:
            with st.expander("Fehler der Markt-Endpunkte"):
                st.write(errors)

        return

    positions = sorted(
        {row["position"] for row in rows if row["position"]}
    )

    sort_options = [
        "Marktwert",
        "Kaufpreis",
        "Trend 24 Stunden",
        "Punkte",
        "Ø Punkte",
        "Name",
    ]

    if compact:
        search = st.text_input(
            "Spieler suchen",
            placeholder="Name oder Verein",
        )

        selected_positions = st.multiselect(
            "Position",
            positions,
        )

        sort_name = st.selectbox(
            "Sortieren nach",
            sort_options,
        )

        sort_direction = st.selectbox(
            "Reihenfolge",
            ["Absteigend", "Aufsteigend"],
        )
    else:
        search_column, position_column = st.columns([3, 2])

        search = search_column.text_input(
            "Spieler suchen",
            placeholder="Name oder Verein",
        )

        selected_positions = position_column.multiselect(
            "Position",
            positions,
        )

        sort_column, direction_column = st.columns([3, 2])

        sort_name = sort_column.selectbox(
            "Sortieren nach",
            sort_options,
        )

        sort_direction = direction_column.selectbox(
            "Reihenfolge",
            ["Absteigend", "Aufsteigend"],
        )

    filtered_rows = rows

    if search:
        search_text = search.strip().lower()

        filtered_rows = [
            row
            for row in filtered_rows
            if (
                search_text in row["name"].lower()
                or search_text in row["club"].lower()
            )
        ]

    if selected_positions:
        filtered_rows = [
            row
            for row in filtered_rows
            if row["position"] in selected_positions
        ]

    sort_fields = {
        "Marktwert": "market_value",
        "Kaufpreis": "purchase_price",
        "Trend 24 Stunden": "daily_change",
        "Punkte": "points",
        "Ø Punkte": "average_points",
        "Name": "name",
    }

    sort_field = sort_fields[sort_name]
    reverse = sort_direction == "Absteigend"

    if sort_field == "name":
        filtered_rows = sorted(
            filtered_rows,
            key=lambda row: row["name"].lower(),
            reverse=reverse,
        )
    else:
        filtered_rows = sorted(
            filtered_rows,
            key=lambda row: (
                to_number(row[sort_field]) is not None,
                to_number(row[sort_field]) or 0,
            ),
            reverse=reverse,
        )

    st.caption(
        f"{len(filtered_rows)} von {len(rows)} Spielern"
    )

    if not filtered_rows:
        st.info(
            "Für diese Suche wurden keine Spieler gefunden."
        )
        return

    cards = "".join(
        market_card(row) for row in filtered_rows
    )

    st.markdown(
        f"<div class='market-grid'>{cards}</div>",
        unsafe_allow_html=True,
    )

    if not compact:
        with st.expander(
            "Diagnose der Transfermarkt-Rohdaten"
        ):
            if sources:
                for source in sources:
                    st.write(f"**{source['path']}**")
                    st.json(source["data"])
            else:
                st.write(
                    "Der Markt-Endpunkt lieferte keine Daten."
                )

            if errors:
                st.write("**Fehler:**")
                st.write(errors)

        with st.expander("Erkannte Marktdaten als Tabelle"):
            preview = pd.DataFrame(
                [
                    {
                        "Spieler": row["name"],
                        "Position": row["position"],
                        "Verein": row["club"],
                        "Marktwert": row["market_value"],
                        "Kaufpreis": row["purchase_price"],
                        "Trend 24 Std.": row["daily_change"],
                        "Punkte": row["points"],
                        "Ø Punkte": row["average_points"],
                        "Anbieter": row["seller"],
                        "Angebotszeit": row["remaining"],
                    }
                    for row in filtered_rows
                ]
            )

            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
            )

            st.write("**Rohdaten des ersten Spielers:**")
            st.json(filtered_rows[0]["raw"])
