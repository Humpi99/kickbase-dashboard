"""
Schnelle Transfermarkt-Ansicht für das Kickbase-Dashboard.

Ladeablauf:
1. Transfermarkt sofort aus den vorhandenen Marktdaten anzeigen.
2. Spielerdetails auf Wunsch separat laden.
3. Drei-Tage-Marktwertänderungen auf Wunsch separat laden.
"""

from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st


# ---------------------------------------------------------
# Konstanten
# ---------------------------------------------------------

IMAGE_BASE_URL = "https://kickbase.b-cdn.net/"

PLAYER_PHOTO_SIZE = 42
PLAYER_PHOTO_SIZE_MOBILE = 36

TEAM_LOGO_SIZE = 22
TEAM_LOGO_SIZE_MOBILE = 18

POSITION_NAMES = {
    1: "Torwart",
    2: "Abwehr",
    3: "Mittelfeld",
    4: "Sturm",
}

S11_PROBABILITY = {
    1: {
        "label": "Sicher",
        "symbol": "+",
        "css_class": "market-probability-safe",
    },
    2: {
        "label": "Erwartet",
        "symbol": "✓",
        "css_class": "market-probability-expected",
    },
    3: {
        "label": "Unsicher",
        "symbol": "?",
        "css_class": "market-probability-uncertain",
    },
    4: {
        "label": "Unwahrscheinlich",
        "symbol": "!",
        "css_class": "market-probability-unlikely",
    },
    5: {
        "label": "Ausgeschlossen",
        "symbol": "×",
        "css_class": "market-probability-excluded",
    },
}

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

MARKET_VALUE_KEYS = [
    "mv",
    "marketValue",
    "currentValue",
    "cv",
]

DAILY_CHANGE_KEYS = [
    "tfhmvt",
    "dailyChange",
    "marketValueChange",
    "mvt",
    "sdmvt",
    "dmv",
]

THREE_DAY_CHANGE_KEYS = [
    "thdmvt",
    "threeDayChange",
    "three_day_change",
    "marketValueChange3d",
    "market_value_change_3d",
    "change3d",
    "trend3d",
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
    "total_points",
    "seasonPoints",
    "season_points",
    "tp",
    "p",
]

AVERAGE_POINTS_KEYS = [
    "averagePoints",
    "average_points",
    "avgPoints",
    "avg_points",
    "average",
    "avg",
    "ap",
    "ppg",
]

MATCH_COUNT_KEYS = [
    "appearances",
    "matches",
    "games",
    "playedMatches",
    "played_matches",
    "matchCount",
    "match_count",
    "apps",
    "mp",
    "mdc",
]

PROBABILITY_KEYS = [
    "prob",
    "probability",
    "lineupProbability",
    "appearanceProbability",
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

PLAYER_IMAGE_KEYS = [
    "pim",
    "playerImage",
    "plim",
    "profileImage",
    "image",
    "imageUrl",
    "img",
]

TEAM_ID_KEYS = [
    "tid",
    "teamId",
    "ti",
    "clubId",
    "ci",
]

TEAM_NAME_KEYS = [
    "teamName",
    "clubName",
    "tn",
    "cn",
]

TEAM_SHORT_NAME_KEYS = [
    "tabb",
    "teamAbbreviation",
    "abbreviation",
    "tsym",
    "symbol",
    "shortName",
    "sn",
]

TEAM_IMAGE_KEYS = [
    "tim",
    "teamImage",
    "teamLogo",
    "clubImage",
    "clubLogo",
    "logo",
    "logoUrl",
    "crest",
    "badge",
    "tiy",
]

PLAYER_CONTAINER_KEYS = [
    "player",
    "playerData",
    "footballer",
    "pl",
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

HISTORY_DATE_KEYS = [
    "dt",
    "date",
    "timestamp",
    "time",
    "ts",
    "createdAt",
    "created_at",
    "day",
]

HISTORY_VALUE_KEYS = [
    "mv",
    "marketValue",
    "market_value",
    "value",
    "v",
    "price",
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


def first_text(data, keys):
    """Gibt den ersten nicht leeren Text zurück."""
    if not isinstance(data, dict):
        return ""

    for key in keys:
        value = data.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


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


def parse_datetime(value):
    """Wandelt verschiedene Zeitformate in ein Datum um."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            pass

    number = to_number(value)

    if number is None:
        return None

    try:
        if number > 10_000_000_000:
            number /= 1000

        if number > 1_000_000_000:
            return datetime.fromtimestamp(
                number,
                tz=timezone.utc,
            )

    except (
        ValueError,
        OSError,
        OverflowError,
    ):
        pass

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

    if number > 0:
        return f"+{format_currency(number)}"

    if number < 0:
        return f"-{format_currency(abs(number))}"

    return format_currency(0)


def format_percentage(value):
    """Formatiert einen Prozentwert."""
    number = to_number(value)

    if number is None:
        return "—"

    text = f"{abs(number):.2f}".replace(".", ",")

    if number > 0:
        return f"+{text} %"

    if number < 0:
        return f"-{text} %"

    return "0,00 %"


def format_points(value):
    """Formatiert Gesamtpunkte."""
    number = to_number(value)

    if number is None:
        return "—"

    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")

    text = f"{number:,.1f}"
    text = text.replace(",", "X")
    text = text.replace(".", ",")
    text = text.replace("X", ".")

    return text


def format_average_points(value):
    """Formatiert Durchschnittspunkte."""
    number = to_number(value)

    if number is None:
        return "—"

    return f"{number:.1f}".replace(".", ",")


def collect_dictionaries(data, depth=0):
    """Sammelt alle verschachtelten Dictionaries."""
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


def get_nested_dictionary(data, keys):
    """Sucht ein direkt enthaltenes Dictionary."""
    if not isinstance(data, dict):
        return None

    for key in keys:
        value = data.get(key)

        if isinstance(value, dict):
            return value

    return None


def build_image_url(value):
    """Erstellt eine vollständige Bildadresse."""
    if not isinstance(value, str):
        return ""

    cleaned = value.strip()

    if not cleaned:
        return ""

    if cleaned.startswith(
        ("http://", "https://")
    ):
        return cleaned

    if cleaned.startswith("//"):
        return f"https:{cleaned}"

    return (
        IMAGE_BASE_URL
        + cleaned.lstrip("/")
    )


def image_html(
    url,
    label,
    size,
    css_class,
):
    """Erstellt ein HTML-Bild."""
    if not url:
        return ""

    return (
        f"<img src='{escape(url)}' "
        f"alt='{escape(str(label or ''))}' "
        f"title='{escape(str(label or ''))}' "
        f"class='{css_class}' "
        f"style='width:{size}px;"
        f"height:{size}px;' />"
    )


def value_css_class(value):
    """Bestimmt die Farbe eines Änderungswertes."""
    number = to_number(value)

    if number is None or number == 0:
        return "market-value-neutral"

    if number > 0:
        return "market-value-positive"

    return "market-value-negative"


def signed_value_html(value):
    """Erstellt einen farbigen Änderungswert."""
    return (
        f"<span class='{value_css_class(value)}'>"
        f"{escape(format_signed_currency(value))}"
        "</span>"
    )


# ---------------------------------------------------------
# Spieler- und Angebotsdaten
# ---------------------------------------------------------

def merge_market_item(item):
    """Verbindet Angebot und Spielerdaten."""
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
    merged["_player_data"] = player_data

    return merged


def merge_detail_data(base_item, details):
    """Ergänzt fehlende Werte durch Spielerdetails."""
    merged = dict(base_item)

    if not isinstance(details, dict):
        return merged

    candidates = [details]

    for key in [
        "player",
        "data",
        "item",
        "pl",
    ]:
        nested = details.get(key)

        if isinstance(nested, dict):
            candidates.append(nested)

    for candidate in candidates:
        for key, value in candidate.items():
            if (
                key not in merged
                or merged[key] is None
                or merged[key] == ""
            ):
                merged[key] = value

    return merged


def get_player_id(item):
    """Ermittelt die Spieler-ID."""
    if not isinstance(item, dict):
        return None

    player_data = item.get("_player_data")

    if isinstance(player_data, dict):
        value = first_value(
            player_data,
            PLAYER_ID_KEYS,
        )

        if value is not None:
            return str(value)

    nested_player = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    if nested_player:
        value = first_value(
            nested_player,
            PLAYER_ID_KEYS,
        )

        if value is not None:
            return str(value)

    value = first_value(
        item,
        PLAYER_ID_KEYS,
    )

    return (
        str(value)
        if value is not None
        else None
    )


def get_player_name(item):
    """Ermittelt den Spielernamen."""
    first_name = first_value(
        item,
        FIRST_NAME_KEYS,
        "",
    )

    last_name = first_value(
        item,
        LAST_NAME_KEYS,
        "",
    )

    combined = (
        f"{first_name} {last_name}".strip()
    )

    if combined:
        return combined

    full_name = first_value(
        item,
        FULL_NAME_KEYS,
    )

    if full_name:
        return str(full_name)

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    if player_data:
        return get_player_name(player_data)

    return "Unbekannter Spieler"


def get_position(item):
    """Ermittelt die Spielerposition."""
    value = first_value(
        item,
        POSITION_KEYS,
    )

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = first_value(
            player_data,
            POSITION_KEYS,
        )

    number = to_number(value)

    if number is not None:
        return POSITION_NAMES.get(
            int(number),
            str(value),
        )

    if value:
        return str(value)

    return "Unbekannt"


def get_market_value(item):
    """Ermittelt den aktuellen Marktwert."""
    value = to_number(
        first_value(
            item,
            MARKET_VALUE_KEYS,
        )
    )

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(
            player_data,
            MARKET_VALUE_KEYS,
        )
    )


def get_daily_change(item):
    """Ermittelt die Änderung der letzten 24 Stunden."""
    value = to_number(
        first_value(
            item,
            DAILY_CHANGE_KEYS,
        )
    )

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(
            player_data,
            DAILY_CHANGE_KEYS,
        )
    )


def get_direct_three_day_change(item):
    """Sucht einen direkt vorhandenen Drei-Tage-Wert."""
    value = to_number(
        first_value(
            item,
            THREE_DAY_CHANGE_KEYS,
        )
    )

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(
            player_data,
            THREE_DAY_CHANGE_KEYS,
        )
    )


def get_purchase_price(item):
    """Ermittelt den Angebots- oder Kaufpreis."""
    value = to_number(
        first_value(
            item,
            PRICE_KEYS,
        )
    )

    if value is not None:
        return value

    return get_market_value(item)


def get_points(item):
    """Ermittelt die Gesamtpunkte."""
    value = to_number(
        first_value(
            item,
            POINTS_KEYS,
        )
    )

    if value is not None:
        return value

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return to_number(
        first_value(
            player_data,
            POINTS_KEYS,
        )
    )


def get_average_points(item):
    """Ermittelt den persönlichen Punktedurchschnitt."""
    value = to_number(
        first_value(
            item,
            AVERAGE_POINTS_KEYS,
        )
    )

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = to_number(
            first_value(
                player_data,
                AVERAGE_POINTS_KEYS,
            )
        )

    if value is not None:
        return value

    total_points = get_points(item)

    match_count = to_number(
        first_value(
            item,
            MATCH_COUNT_KEYS,
        )
    )

    if (
        total_points is not None
        and match_count is not None
        and match_count > 0
    ):
        return total_points / match_count

    return None


def get_probability(item):
    """Ermittelt die S11-Prognose aus prob."""
    value = to_number(
        first_value(
            item,
            PROBABILITY_KEYS,
        )
    )

    if value is None:
        player_data = get_nested_dictionary(
            item,
            PLAYER_CONTAINER_KEYS,
        )

        value = to_number(
            first_value(
                player_data,
                PROBABILITY_KEYS,
            )
        )

    if value is None:
        return None

    probability = int(value)

    if probability not in S11_PROBABILITY:
        return None

    return probability


def probability_label(value):
    """Gibt die Bezeichnung der S11-Prognose zurück."""
    number = to_number(value)

    if number is None:
        return "Keine Angabe"

    information = S11_PROBABILITY.get(
        int(number)
    )

    if not information:
        return "Keine Angabe"

    return information["label"]


def probability_badge_html(value):
    """Erstellt das farbige S11-Symbol."""
    number = to_number(value)

    if number is None:
        return ""

    probability = int(number)
    information = S11_PROBABILITY.get(
        probability
    )

    if not information:
        return ""

    return (
        "<span "
        f"class='market-probability-badge "
        f"{information['css_class']}' "
        f"title='S11-Prognose: "
        f"{escape(information['label'])} "
        f"(Stufe {probability})'>"
        f"{escape(information['symbol'])}"
        "</span>"
    )


def probability_legend_html():
    """Erstellt die Legende."""
    entries = []

    for probability, information in (
        S11_PROBABILITY.items()
    ):
        entries.append(
            "<span class='market-legend-entry'>"
            f"{probability_badge_html(probability)}"
            f"<span>{escape(information['label'])}</span>"
            "</span>"
        )

    return (
        "<div class='market-legend'>"
        "<strong>S11-Prognose:</strong>"
        f"{''.join(entries)}"
        "</div>"
    )


def get_player_photo(item):
    """Ermittelt das Spielerfoto."""
    value = first_text(
        item,
        PLAYER_IMAGE_KEYS,
    )

    if value:
        return build_image_url(value)

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    return build_image_url(
        first_text(
            player_data,
            PLAYER_IMAGE_KEYS,
        )
    )


def get_team_id(item):
    """Ermittelt die Vereins-ID."""
    value = first_value(
        item,
        TEAM_ID_KEYS,
    )

    if value is not None and not isinstance(
        value,
        (dict, list, bool),
    ):
        return str(value)

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    value = first_value(
        player_data,
        TEAM_ID_KEYS,
    )

    if value is None or isinstance(
        value,
        (dict, list, bool),
    ):
        return None

    return str(value)


def get_direct_team_name(item):
    """Ermittelt einen direkt vorhandenen Vereinsnamen."""
    value = first_value(
        item,
        TEAM_SHORT_NAME_KEYS + TEAM_NAME_KEYS,
    )

    if isinstance(value, str) and value.strip():
        return value.strip()

    for container_key in [
        "team",
        "club",
        "teamData",
        "clubData",
    ]:
        container = item.get(container_key)

        if not isinstance(container, dict):
            continue

        value = first_value(
            container,
            [
                "name",
                "n",
                "shortName",
                "sn",
                "tabb",
                "teamName",
                "clubName",
            ],
        )

        if value:
            return str(value)

    player_data = get_nested_dictionary(
        item,
        PLAYER_CONTAINER_KEYS,
    )

    if player_data:
        return get_direct_team_name(
            player_data
        )

    return ""


def get_seller_name(item):
    """Ermittelt den Anbieter."""
    for key in SELLER_CONTAINER_KEYS:
        value = item.get(key)

        if not isinstance(value, dict):
            continue

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

    return (
        str(direct_name)
        if direct_name
        else "—"
    )


def format_remaining_time(item):
    """Formatiert die verbleibende Angebotszeit."""
    value = first_value(
        item,
        EXPIRY_KEYS,
    )

    if value is None:
        return "—"

    expiry = parse_datetime(value)

    if expiry is not None:
        remaining_seconds = int(
            (
                expiry
                - datetime.now(timezone.utc)
            ).total_seconds()
        )

    else:
        number = to_number(value)

        if number is None:
            return str(value)

        if not 0 <= number <= 31_536_000:
            return "—"

        remaining_seconds = int(number)

    if remaining_seconds <= 0:
        return "Abgelaufen"

    days, remaining_seconds = divmod(
        remaining_seconds,
        86_400,
    )

    hours, remaining_seconds = divmod(
        remaining_seconds,
        3_600,
    )

    minutes = remaining_seconds // 60

    if days > 0:
        return f"{days} T. {hours} Std."

    if hours > 0:
        return f"{hours} Std. {minutes} Min."

    return f"{minutes} Min."


# ---------------------------------------------------------
# Transfermarktspieler erkennen
# ---------------------------------------------------------

def item_information_score(item):
    """Bewertet die Informationsmenge eines Datensatzes."""
    checks = [
        get_market_value(item),
        get_daily_change(item),
        get_direct_three_day_change(item),
        get_purchase_price(item),
        get_points(item),
        get_average_points(item),
        get_probability(item),
        get_player_photo(item),
        get_team_id(item),
        get_direct_team_name(item),
        get_seller_name(item) != "—",
        format_remaining_time(item) != "—",
    ]

    return sum(
        value is not None
        and value is not False
        and value != ""
        for value in checks
    )


def extract_market_items(market_sources):
    """Erkennt Marktspieler und entfernt Duplikate."""
    by_player_id = {}

    for source in market_sources:
        data = source.get("data")

        for raw_item in collect_dictionaries(data):
            item = merge_market_item(raw_item)
            player_id = get_player_id(item)
            market_value = get_market_value(item)

            if (
                player_id is None
                or market_value is None
            ):
                continue

            previous = by_player_id.get(
                player_id
            )

            if (
                previous is None
                or item_information_score(item)
                > item_information_score(previous)
            ):
                by_player_id[player_id] = item

    return list(
        by_player_id.values()
    )


# ---------------------------------------------------------
# Vereinsdaten
# ---------------------------------------------------------

def looks_like_team(item):
    """Prüft, ob ein Datensatz ein Verein ist."""
    if not isinstance(item, dict):
        return False

    if any(
        key in item
        for key in [
            "mv",
            "mvgl",
            "tfhmvt",
            "pim",
            "pn",
        ]
    ):
        return False

    team_id = first_value(
        item,
        [
            "id",
            "i",
            "tid",
            "teamId",
        ],
    )

    if team_id is None:
        return False

    name = first_text(
        item,
        [
            "name",
            "n",
            "shortName",
            "sn",
            "tabb",
            "teamName",
            "tn",
        ],
    )

    logo = first_text(
        item,
        TEAM_IMAGE_KEYS,
    )

    return bool(name or logo)


def extract_teams(sources):
    """Erstellt eine Vereinsübersicht."""
    teams = {}

    for source in sources:
        for item in collect_dictionaries(
            source.get("data")
        ):
            if not looks_like_team(item):
                continue

            team_id = str(
                first_value(
                    item,
                    [
                        "id",
                        "i",
                        "tid",
                        "teamId",
                    ],
                )
            )

            entry = teams.setdefault(
                team_id,
                {
                    "name": "",
                    "long_name": "",
                    "logo": "",
                },
            )

            if not entry["name"]:
                entry["name"] = first_text(
                    item,
                    TEAM_SHORT_NAME_KEYS,
                )

            if not entry["long_name"]:
                entry["long_name"] = first_text(
                    item,
                    TEAM_NAME_KEYS + ["name", "n"],
                )

            if not entry["logo"]:
                entry["logo"] = build_image_url(
                    first_text(
                        item,
                        TEAM_IMAGE_KEYS,
                    )
                )

    for entry in teams.values():
        if not entry["name"]:
            entry["name"] = entry["long_name"]

    return teams


def get_team_name(
    team_id,
    teams,
    item=None,
):
    """Ermittelt den Vereinsnamen."""
    if team_id:
        team = teams.get(
            str(team_id),
            {},
        )

        name = (
            team.get("name")
            or team.get("long_name")
            or ""
        )

        if name:
            return name

    if item:
        direct_name = get_direct_team_name(
            item
        )

        if direct_name:
            return direct_name

    return "Verein unbekannt"


def get_team_logo(
    team_id,
    teams,
    item=None,
):
    """Ermittelt das Vereinslogo."""
    if team_id:
        logo = teams.get(
            str(team_id),
            {},
        ).get(
            "logo",
            "",
        )

        if logo:
            return logo

    if item:
        return build_image_url(
            first_text(
                item,
                TEAM_IMAGE_KEYS,
            )
        )

    return ""


# ---------------------------------------------------------
# Spielplan
# ---------------------------------------------------------

def extract_matches(sources):
    """Erkennt zukünftige Spiele."""
    matches = []
    seen = set()
    now = datetime.now(timezone.utc)

    for source in sources:
        for item in collect_dictionaries(
            source.get("data")
        ):
            home_id = first_value(
                item,
                [
                    "t1",
                    "homeTeamId",
                    "home",
                    "ht",
                ],
            )

            away_id = first_value(
                item,
                [
                    "t2",
                    "awayTeamId",
                    "away",
                    "at",
                ],
            )

            if (
                home_id is None
                or away_id is None
                or isinstance(
                    home_id,
                    (dict, list, bool),
                )
                or isinstance(
                    away_id,
                    (dict, list, bool),
                )
            ):
                continue

            match_date = None

            for key in [
                "dt",
                "date",
                "kickoff",
                "startDate",
                "md",
            ]:
                match_date = parse_datetime(
                    item.get(key)
                )

                if match_date is not None:
                    break

            if (
                match_date is None
                or match_date < now
            ):
                continue

            signature = (
                str(home_id),
                str(away_id),
                match_date.isoformat(),
            )

            if signature in seen:
                continue

            seen.add(signature)

            matches.append(
                {
                    "home_id": str(home_id),
                    "away_id": str(away_id),
                    "date": match_date,
                }
            )

    return matches


def build_next_matches(matches, count=2):
    """Ordnet die nächsten Spiele den Vereinen zu."""
    by_team = {}

    for match in sorted(
        matches,
        key=lambda entry: entry["date"],
    ):
        date_text = match["date"].strftime(
            "%d.%m."
        )

        by_team.setdefault(
            match["home_id"],
            [],
        ).append(
            {
                "place": "H",
                "opponent_id": match["away_id"],
                "date": date_text,
            }
        )

        by_team.setdefault(
            match["away_id"],
            [],
        ).append(
            {
                "place": "A",
                "opponent_id": match["home_id"],
                "date": date_text,
            }
        )

    return {
        team_id: entries[:count]
        for team_id, entries in by_team.items()
    }


def next_matches_text(
    team_id,
    next_matches,
    teams,
):
    """Erstellt einen Text der nächsten Spiele."""
    entries = next_matches.get(
        str(team_id or ""),
        [],
    )

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent = get_team_name(
            entry["opponent_id"],
            teams,
        )

        parts.append(
            f"{entry['place']} "
            f"{opponent} "
            f"{entry['date']}"
        )

    return " · ".join(parts)


def next_matches_html(
    team_id,
    next_matches,
    teams,
    logo_size,
):
    """Erstellt die Spielanzeige mit Logos."""
    entries = next_matches.get(
        str(team_id or ""),
        [],
    )

    if not entries:
        return "—"

    parts = []

    for entry in entries:
        opponent_id = entry["opponent_id"]

        opponent_name = get_team_name(
            opponent_id,
            teams,
        )

        opponent_logo = get_team_logo(
            opponent_id,
            teams,
        )

        logo = image_html(
            opponent_logo,
            opponent_name,
            logo_size,
            "market-team-logo",
        )

        parts.append(
            "<span class='market-match'>"
            f"<strong>{entry['place']}</strong>"
            f"{logo}"
            f"<span>{entry['date']}</span>"
            "</span>"
        )

    return "".join(parts)


# ---------------------------------------------------------
# Schnelle Basiszeilen
# ---------------------------------------------------------

def create_fast_row(
    item,
    teams,
    next_matches,
):
    """Erstellt ohne zusätzliche API-Aufrufe eine Zeile."""
    player_id = get_player_id(item)
    team_id = get_team_id(item)

    direct_three_day_change = (
        get_direct_three_day_change(item)
    )

    market_value = get_market_value(item)

    three_day_percentage = None

    if (
        direct_three_day_change is not None
        and market_value is not None
    ):
        reference_value = (
            market_value
            - direct_three_day_change
        )

        if reference_value != 0:
            three_day_percentage = (
                direct_three_day_change
                / reference_value
                * 100
            )

    return {
        "player_id": player_id,
        "name": get_player_name(item),
        "photo": get_player_photo(item),
        "position": get_position(item),
        "team_id": team_id,
        "club": get_team_name(
            team_id,
            teams,
            item,
        ),
        "club_logo": get_team_logo(
            team_id,
            teams,
            item,
        ),
        "probability": get_probability(item),
        "market_value": market_value,
        "purchase_price": get_purchase_price(item),
        "daily_change": get_daily_change(item),
        "three_day_change": (
            direct_three_day_change
        ),
        "three_day_percentage": (
            three_day_percentage
        ),
        "points": get_points(item),
        "average_points": get_average_points(item),
        "seller": get_seller_name(item),
        "remaining": format_remaining_time(item),
        "matches_text": next_matches_text(
            team_id,
            next_matches,
            teams,
        ),
        "matches_html": next_matches_html(
            team_id,
            next_matches,
            teams,
            TEAM_LOGO_SIZE,
        ),
        "details_loaded": False,
        "history_loaded": (
            direct_three_day_change is not None
        ),
        "detail_path": None,
        "history_path": None,
        "history_reference_date": None,
        "history_points": [],
        "raw": item,
        "details": {},
    }


# ---------------------------------------------------------
# Spielerdetails separat laden
# ---------------------------------------------------------

def load_single_player_details(
    api,
    league_id,
    player_id,
):
    """Lädt mit möglichst wenigen Anfragen Spielerdetails."""
    cache_key = (
        f"market_player_details_v2_"
        f"{league_id}_{player_id}"
    )

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    paths = [
        f"/v4/players/{player_id}",
        (
            f"/v4/competitions/1"
            f"/players/{player_id}"
        ),
    ]

    result = {
        "data": {},
        "path": None,
    }

    for path in paths:
        try:
            data = api.get(path)

        except Exception:
            continue

        result = {
            "data": data,
            "path": path,
        }

        break

    st.session_state[cache_key] = result

    return result


def enrich_row_with_details(
    api,
    league_id,
    row,
    teams,
    next_matches,
):
    """Ergänzt eine Zeile mit Spielerdetails."""
    player_id = row["player_id"]

    result = load_single_player_details(
        api,
        league_id,
        player_id,
    )

    details = result["data"]

    if not details:
        updated = dict(row)
        updated["details_loaded"] = True
        return updated

    complete_item = merge_detail_data(
        row["raw"],
        details,
    )

    updated = dict(row)

    new_team_id = (
        get_team_id(complete_item)
        or row["team_id"]
    )

    updated.update(
        {
            "name": get_player_name(
                complete_item
            ),
            "photo": (
                get_player_photo(complete_item)
                or row["photo"]
            ),
            "position": get_position(
                complete_item
            ),
            "team_id": new_team_id,
            "club": get_team_name(
                new_team_id,
                teams,
                complete_item,
            ),
            "club_logo": get_team_logo(
                new_team_id,
                teams,
                complete_item,
            ),
            "probability": get_probability(
                complete_item
            ),
            "market_value": (
                get_market_value(complete_item)
            ),
            "daily_change": (
                get_daily_change(complete_item)
            ),
            "points": get_points(
                complete_item
            ),
            "average_points": (
                get_average_points(complete_item)
            ),
            "matches_text": next_matches_text(
                new_team_id,
                next_matches,
                teams,
            ),
            "matches_html": next_matches_html(
                new_team_id,
                next_matches,
                teams,
                TEAM_LOGO_SIZE,
            ),
            "details_loaded": True,
            "detail_path": result["path"],
            "details": details,
        }
    )

    return updated


# ---------------------------------------------------------
# Drei-Tage-Historie separat laden
# ---------------------------------------------------------

def history_path_templates():
    """Bekannte mögliche Historienpfade."""
    return [
        (
            "/v4/players/{player_id}"
            "/marketValue/{league_id}"
        ),
        (
            "/v4/players/{player_id}"
            "/marketvalue/{league_id}"
        ),
        (
            "/v4/players/{player_id}"
            "/market-value/{league_id}"
        ),
        (
            "/v4/leagues/{league_id}"
            "/players/{player_id}/marketValue"
        ),
        (
            "/v4/leagues/{league_id}"
            "/players/{player_id}/marketvalue"
        ),
        (
            "/v4/competitions/1"
            "/players/{player_id}/marketValue"
        ),
        (
            "/v4/players/{player_id}"
            "/marketValue"
        ),
        (
            "/v4/players/{player_id}"
            "/history"
        ),
    ]


def create_history_path(
    template,
    league_id,
    player_id,
):
    """Füllt einen Historienpfad aus."""
    return template.format(
        league_id=league_id,
        player_id=player_id,
    )


def extract_history_points(data):
    """Sucht datierte Marktwerte."""
    points = []

    for item in collect_dictionaries(data):
        date = parse_datetime(
            first_value(
                item,
                HISTORY_DATE_KEYS,
            )
        )

        market_value = to_number(
            first_value(
                item,
                HISTORY_VALUE_KEYS,
            )
        )

        if (
            date is None
            or market_value is None
            or market_value < 1000
        ):
            continue

        points.append(
            {
                "date": date,
                "market_value": market_value,
            }
        )

    unique = {}

    for point in points:
        signature = (
            point["date"].isoformat(),
            point["market_value"],
        )

        unique[signature] = point

    return sorted(
        unique.values(),
        key=lambda point: point["date"],
    )


def calculate_three_day_change(
    history_points,
    current_market_value,
):
    """Berechnet die Änderung gegenüber vor drei Tagen."""
    current_value = to_number(
        current_market_value
    )

    if (
        current_value is None
        or not history_points
    ):
        return None, None, None

    target = (
        datetime.now(timezone.utc)
        - timedelta(days=3)
    )

    candidates = [
        point
        for point in history_points
        if point["date"] <= target
    ]

    if not candidates:
        return None, None, None

    reference = max(
        candidates,
        key=lambda point: point["date"],
    )

    reference_value = reference[
        "market_value"
    ]

    change = (
        current_value
        - reference_value
    )

    percentage = None

    if reference_value != 0:
        percentage = (
            change
            / reference_value
            * 100
        )

    return (
        change,
        percentage,
        reference["date"],
    )


def load_history_response(
    api,
    league_id,
    player_id,
    template,
):
    """Lädt einen bereits bekannten Historienpfad."""
    cache_key = (
        f"market_history_v2_"
        f"{league_id}_{player_id}_"
        f"{abs(hash(template))}"
    )

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    path = create_history_path(
        template,
        league_id,
        player_id,
    )

    result = {
        "path": path,
        "points": [],
    }

    try:
        data = api.get(path)
        result["points"] = extract_history_points(
            data
        )

    except Exception:
        pass

    st.session_state[cache_key] = result

    return result


def discover_history_template(
    api,
    league_id,
    rows,
):
    """
    Ermittelt den Historienpfad einmal.

    Es werden höchstens drei Spieler zur Ermittlung
    des passenden Endpunkts verwendet.
    """
    template_cache_key = (
        f"market_history_template_v2_{league_id}"
    )

    if template_cache_key in st.session_state:
        return st.session_state[
            template_cache_key
        ]

    candidate_rows = rows[:3]

    for template in history_path_templates():
        for row in candidate_rows:
            result = load_history_response(
                api,
                league_id,
                row["player_id"],
                template,
            )

            (
                change,
                _,
                _,
            ) = calculate_three_day_change(
                result["points"],
                row["market_value"],
            )

            if change is not None:
                st.session_state[
                    template_cache_key
                ] = template

                return template

    st.session_state[
        template_cache_key
    ] = None

    return None


def enrich_row_with_history(
    api,
    league_id,
    row,
    template,
):
    """Ergänzt die Drei-Tage-Änderung."""
    updated = dict(row)

    if row["three_day_change"] is not None:
        updated["history_loaded"] = True
        return updated

    if not template:
        updated["history_loaded"] = True
        return updated

    result = load_history_response(
        api,
        league_id,
        row["player_id"],
        template,
    )

    (
        change,
        percentage,
        reference_date,
    ) = calculate_three_day_change(
        result["points"],
        row["market_value"],
    )

    updated.update(
        {
            "three_day_change": change,
            "three_day_percentage": percentage,
            "history_loaded": True,
            "history_path": result["path"],
            "history_reference_date": reference_date,
            "history_points": result["points"],
        }
    )

    return updated


# ---------------------------------------------------------
# Tabellenanzeige
# ---------------------------------------------------------

def player_cell_html(
    row,
    photo_size,
):
    """Erstellt Spielerfoto, Name und S11-Symbol."""
    photo = image_html(
        row["photo"],
        row["name"],
        photo_size,
        "market-player-photo",
    )

    badge = probability_badge_html(
        row["probability"]
    )

    return (
        "<div class='market-player-cell'>"
        f"{photo}"
        "<div class='market-player-text'>"
        "<div class='market-player-name-line'>"
        f"<span class='market-player-name'>"
        f"{escape(row['name'])}"
        "</span>"
        f"{badge}"
        "</div>"
        "</div>"
        "</div>"
    )


def club_cell_html(
    row,
    logo_size,
):
    """Erstellt Vereinslogo und Vereinsnamen."""
    logo = image_html(
        row["club_logo"],
        row["club"],
        logo_size,
        "market-team-logo",
    )

    return (
        "<div class='market-club-cell'>"
        f"{logo}"
        f"<span>{escape(row['club'])}</span>"
        "</div>"
    )


def points_cell_html(row):
    """Zeigt Gesamtpunkte und Durchschnitt."""
    total = format_points(
        row["points"]
    )

    average = format_average_points(
        row["average_points"]
    )

    if average == "—":
        return escape(total)

    return (
        f"{escape(total)} "
        "<span class='market-points-average'>"
        f"({escape(average)} Ø)"
        "</span>"
    )


def three_day_cell_html(row):
    """Zeigt Drei-Tage-Änderung und Prozentwert."""
    change = row["three_day_change"]

    if change is None:
        if row["history_loaded"]:
            title = (
                "Keine auswertbare "
                "Drei-Tage-Historie gefunden"
            )

        else:
            title = (
                "Drei-Tage-Werte wurden "
                "noch nicht geladen"
            )

        return (
            "<span class='market-no-history' "
            f"title='{escape(title)}'>"
            "—"
            "</span>"
        )

    return (
        "<div class='market-trend-cell'>"
        f"{signed_value_html(change)}"
        "<span class='market-trend-percent'>"
        f"{escape(format_percentage(row['three_day_percentage']))}"
        "</span>"
        "</div>"
    )


def render_market_table(
    rows,
    compact,
):
    """Zeigt die Transfermarkt-Spielerliste."""
    if compact:
        columns = [
            "Spieler",
            "Position",
            "Verein",
            "Marktwert",
            "3 Tage",
            "Nächste Spiele",
            "Kaufpreis",
            "Angebotszeit",
        ]

    else:
        columns = [
            "Spieler",
            "Position",
            "Verein",
            "Nächste Spiele",
            "Marktwert",
            "24 Stunden",
            "3 Tage",
            "Punkte",
            "Kaufpreis",
            "Anbieter",
            "Angebotszeit",
        ]

    headers = "".join(
        f"<th>{escape(column)}</th>"
        for column in columns
    )

    photo_size = (
        PLAYER_PHOTO_SIZE_MOBILE
        if compact
        else PLAYER_PHOTO_SIZE
    )

    logo_size = (
        TEAM_LOGO_SIZE_MOBILE
        if compact
        else TEAM_LOGO_SIZE
    )

    table_rows = []

    for row in rows:
        values = {
            "Spieler": player_cell_html(
                row,
                photo_size,
            ),
            "Position": escape(
                row["position"]
            ),
            "Verein": club_cell_html(
                row,
                logo_size,
            ),
            "Nächste Spiele": row[
                "matches_html"
            ],
            "Marktwert": escape(
                format_currency(
                    row["market_value"]
                )
            ),
            "24 Stunden": signed_value_html(
                row["daily_change"]
            ),
            "3 Tage": three_day_cell_html(
                row
            ),
            "Punkte": points_cell_html(row),
            "Kaufpreis": escape(
                format_currency(
                    row["purchase_price"]
                )
            ),
            "Anbieter": escape(
                row["seller"]
            ),
            "Angebotszeit": escape(
                row["remaining"]
            ),
        }

        cells = "".join(
            f"<td>{values[column]}</td>"
            for column in columns
        )

        table_rows.append(
            f"<tr>{cells}</tr>"
        )

    table_class = (
        "market-table market-table-mobile"
        if compact
        else "market-table"
    )

    st.markdown(
        "<div class='market-table-wrapper'>"
        f"<table class='{table_class}'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

MARKET_STYLE = """
<style>
:root {
    --market-text: #1c1c1c;
    --market-muted: #747a80;
    --market-border: #e0e3e6;
    --market-row-border: #eceef0;
    --market-background: #ffffff;
    --market-header-background: #f2f4f7;
    --market-header-text: #30363d;
    --market-hover: #f6f8f9;
    --market-positive: #0b8f43;
    --market-negative: #d32929;
    --market-photo-background: #eef0f2;
}

.market-table-wrapper {
    width: 100%;
    overflow-x: auto;
    margin: 0.7rem 0 0.8rem;
    border: 1px solid var(--market-border);
    border-radius: 9px;
    background: var(--market-background);
}

.market-table {
    width: 100%;
    min-width: 1450px;
    border-collapse: collapse;
    color: var(--market-text);
    background: var(--market-background);
    font-size: 0.82rem;
}

.market-table-mobile {
    min-width: 980px;
    font-size: 0.74rem;
}

.market-table th {
    padding: 0.7rem 0.65rem;
    border-right: 1px solid var(--market-border);
    border-bottom: 1px solid var(--market-border);
    color: var(--market-header-text);
    background: var(--market-header-background);
    font-size: 0.68rem;
    font-weight: 750;
    text-align: left;
    text-transform: uppercase;
    white-space: nowrap;
}

.market-table td {
    height: 62px;
    padding: 0.65rem;
    border-right: 1px solid var(--market-row-border);
    border-bottom: 1px solid var(--market-row-border);
    color: var(--market-text);
    background: var(--market-background);
    vertical-align: middle;
    white-space: nowrap;
}

.market-table th:last-child,
.market-table td:last-child {
    border-right: none;
}

.market-table tbody tr:last-child td {
    border-bottom: none;
}

.market-table tbody tr:hover td {
    background: var(--market-hover);
}

.market-player-cell {
    display: flex;
    align-items: center;
    min-width: 175px;
    gap: 0.65rem;
}

.market-player-photo {
    flex: 0 0 auto;
    border-radius: 50%;
    object-fit: cover;
    background: var(--market-photo-background);
}

.market-player-name-line {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.market-player-name {
    color: var(--market-text);
    font-weight: 750;
}

.market-club-cell {
    display: flex;
    align-items: center;
    min-width: 105px;
    gap: 0.4rem;
}

.market-team-logo {
    flex: 0 0 auto;
    object-fit: contain;
}

.market-match {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    margin-right: 0.55rem;
    color: var(--market-text);
}

.market-value-positive {
    color: var(--market-positive);
    font-weight: 750;
}

.market-value-negative {
    color: var(--market-negative);
    font-weight: 750;
}

.market-value-neutral {
    color: var(--market-text);
    font-weight: 650;
}

.market-trend-cell {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
}

.market-trend-percent {
    color: var(--market-muted);
    font-size: 0.7rem;
}

.market-points-average {
    color: var(--market-muted);
    font-size: 0.82em;
}

.market-no-history {
    color: var(--market-muted);
}

.market-probability-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 19px;
    height: 19px;
    min-width: 19px;
    border-radius: 50%;
    color: #ffffff !important;
    font-family: Arial, sans-serif;
    font-size: 13px;
    font-weight: 800;
    line-height: 1;
    box-sizing: border-box;
    cursor: help;
}

.market-probability-safe {
    background: #159bd3;
}

.market-probability-expected {
    background: #26a95b;
}

.market-probability-uncertain {
    background: #e2a51d;
}

.market-probability-unlikely {
    background: #e35a35;
}

.market-probability-excluded {
    background: #555b63;
}

.market-legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.55rem 1rem;
    margin: 0.4rem 0 1rem;
    color: var(--market-text);
    font-size: 0.76rem;
}

.market-legend strong {
    color: var(--market-muted);
}

.market-legend-entry {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
}

html[data-theme="dark"],
body[data-theme="dark"],
[data-theme="dark"] {
    --market-text: #ffffff;
    --market-muted: #c5cad0;
    --market-border: #464c54;
    --market-row-border: #353b43;
    --market-background: #171b20;
    --market-header-background: #3b434d;
    --market-header-text: #ffffff;
    --market-hover: #292f36;
    --market-positive: #52d889;
    --market-negative: #ff7474;
    --market-photo-background: #30363d;
}

@media (max-width: 640px) {
    .market-table td {
        height: 55px;
        padding: 0.5rem;
    }

    .market-probability-badge {
        width: 17px;
        height: 17px;
        min-width: 17px;
        font-size: 11px;
    }

    .market-legend {
        font-size: 0.7rem;
        gap: 0.45rem 0.7rem;
    }
}
</style>
"""


# ---------------------------------------------------------
# Filter und Sortierung
# ---------------------------------------------------------

def filter_and_sort_rows(
    rows,
    compact,
):
    """Filtert und sortiert die Marktspieler."""
    positions = sorted(
        {
            row["position"]
            for row in rows
            if row["position"]
        }
    )

    probability_options = [
        information["label"]
        for information in (
            S11_PROBABILITY.values()
        )
    ]

    sort_options = [
        "Marktwert",
        "Kaufpreis",
        "Änderung 24 Stunden",
        "Änderung 3 Tage",
        "Änderung 3 Tage in Prozent",
        "Punkte",
        "Ø Punkte",
        "S11-Prognose",
        "Name",
    ]

    if compact:
        search = st.text_input(
            "Spieler suchen",
            placeholder="Name oder Verein",
            key="market_search",
        )

        selected_positions = st.multiselect(
            "Position",
            positions,
            key="market_positions",
        )

        selected_probabilities = st.multiselect(
            "S11-Prognose",
            probability_options,
            key="market_probabilities",
        )

        sort_name = st.selectbox(
            "Sortieren nach",
            sort_options,
            key="market_sort",
        )

        sort_direction = st.selectbox(
            "Reihenfolge",
            [
                "Absteigend",
                "Aufsteigend",
            ],
            key="market_direction",
        )

    else:
        (
            search_column,
            position_column,
            probability_column,
        ) = st.columns([3, 2, 2])

        search = search_column.text_input(
            "Spieler suchen",
            placeholder="Name oder Verein",
            key="market_search",
        )

        selected_positions = (
            position_column.multiselect(
                "Position",
                positions,
                key="market_positions",
            )
        )

        selected_probabilities = (
            probability_column.multiselect(
                "S11-Prognose",
                probability_options,
                key="market_probabilities",
            )
        )

        sort_column, direction_column = (
            st.columns([3, 2])
        )

        sort_name = sort_column.selectbox(
            "Sortieren nach",
            sort_options,
            key="market_sort",
        )

        sort_direction = (
            direction_column.selectbox(
                "Reihenfolge",
                [
                    "Absteigend",
                    "Aufsteigend",
                ],
                key="market_direction",
            )
        )

    filtered_rows = list(rows)

    if search:
        search_text = search.strip().lower()

        filtered_rows = [
            row
            for row in filtered_rows
            if (
                search_text
                in row["name"].lower()
                or search_text
                in row["club"].lower()
            )
        ]

    if selected_positions:
        filtered_rows = [
            row
            for row in filtered_rows
            if row["position"]
            in selected_positions
        ]

    if selected_probabilities:
        filtered_rows = [
            row
            for row in filtered_rows
            if probability_label(
                row["probability"]
            )
            in selected_probabilities
        ]

    sort_fields = {
        "Marktwert": "market_value",
        "Kaufpreis": "purchase_price",
        "Änderung 24 Stunden": "daily_change",
        "Änderung 3 Tage": "three_day_change",
        "Änderung 3 Tage in Prozent": (
            "three_day_percentage"
        ),
        "Punkte": "points",
        "Ø Punkte": "average_points",
        "S11-Prognose": "probability",
        "Name": "name",
    }

    sort_field = sort_fields[sort_name]
    reverse = (
        sort_direction == "Absteigend"
    )

    if sort_field == "name":
        return sorted(
            filtered_rows,
            key=lambda row: row["name"].lower(),
            reverse=reverse,
        )

    if sort_field == "probability":
        return sorted(
            filtered_rows,
            key=lambda row: (
                row["probability"]
                if row["probability"] is not None
                else 99
            ),
            reverse=reverse,
        )

    return sorted(
        filtered_rows,
        key=lambda row: (
            to_number(row[sort_field])
            is not None,
            to_number(row[sort_field]) or 0,
        ),
        reverse=reverse,
    )


# ---------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------

def render_transfer_market(
    api,
    league_id,
    compact=False,
):
    """Rendert die schnelle Transfermarktansicht."""
    st.markdown(
        MARKET_STYLE,
        unsafe_allow_html=True,
    )

    st.subheader("Transfermarkt")

    st.caption(
        "Die Marktliste wird zuerst ohne langsame "
        "Einzelabfragen angezeigt. Spielerdetails und "
        "Drei-Tage-Werte kannst du danach separat laden."
    )

    cache_key = (
        f"transfer_market_fast_v1_{league_id}"
    )

    if st.button(
        "Transfermarkt neu laden",
        key="reload_transfer_market",
        use_container_width=compact,
    ):
        st.session_state.pop(
            cache_key,
            None,
        )

        st.session_state.pop(
            f"market_history_template_v2_{league_id}",
            None,
        )

        st.rerun()

    if cache_key not in st.session_state:
        with st.spinner(
            "Transfermarkt wird geladen …"
        ):
            try:
                market_sources, market_errors = (
                    api.get_market(league_id)
                )

            except Exception as error:
                market_sources = []
                market_errors = [str(error)]

            existing_context = (
                st.session_state.get(
                    f"team_matches_v11_{league_id}"
                )
            )

            if existing_context:
                teams = existing_context.get(
                    "teams",
                    {},
                )

                next_matches = (
                    existing_context.get(
                        "next_matches",
                        {},
                    )
                )

            else:
                try:
                    team_sources, _ = (
                        api.get_teams()
                    )

                except Exception:
                    team_sources = []

                try:
                    match_sources, _ = (
                        api.get_matches(
                            league_id
                        )
                    )

                except Exception:
                    match_sources = []

                teams = extract_teams(
                    team_sources
                    + match_sources
                )

                next_matches = build_next_matches(
                    extract_matches(
                        match_sources
                    )
                )

            items = extract_market_items(
                market_sources
            )

            rows = [
                create_fast_row(
                    item,
                    teams,
                    next_matches,
                )
                for item in items
            ]

            st.session_state[cache_key] = {
                "rows": rows,
                "sources": market_sources,
                "errors": market_errors,
                "teams": teams,
                "next_matches": next_matches,
            }

    market_data = st.session_state[
        cache_key
    ]

    rows = market_data["rows"]
    sources = market_data["sources"]
    errors = market_data["errors"]
    teams = market_data["teams"]
    next_matches = market_data[
        "next_matches"
    ]

    if not rows:
        st.warning(
            "Es konnten keine Marktspieler sicher "
            "erkannt werden."
        )

        if sources:
            with st.expander(
                "Diagnose der Transfermarkt-Rohdaten",
                expanded=True,
            ):
                for source in sources:
                    st.write(
                        f"**{source['path']}**"
                    )

                    st.json(
                        source["data"]
                    )

        if errors:
            with st.expander(
                "Fehler der Markt-Endpunkte"
            ):
                st.write(errors)

        return

    details_loaded = all(
        row["details_loaded"]
        for row in rows
    )

    history_loaded = all(
        row["history_loaded"]
        for row in rows
    )

    detail_column, history_column = (
        st.columns(2)
    )

    with detail_column:
        detail_button_text = (
            "Spielerdetails neu laden"
            if details_loaded
            else (
                "Spielerfotos, Vereine und "
                "S11-Prognosen laden"
            )
        )

        load_details = st.button(
            detail_button_text,
            key="load_market_details",
            use_container_width=True,
        )

    with history_column:
        history_button_text = (
            "Drei-Tage-Werte neu laden"
            if history_loaded
            else "Drei-Tage-Werte laden"
        )

        load_history = st.button(
            history_button_text,
            key="load_market_history",
            use_container_width=True,
        )

    if load_details:
        progress = st.progress(
            0.0,
            text=(
                "Spielerdetails werden geladen …"
            ),
        )

        updated_rows = []

        for index, row in enumerate(rows):
            updated_rows.append(
                enrich_row_with_details(
                    api,
                    league_id,
                    row,
                    teams,
                    next_matches,
                )
            )

            progress.progress(
                (index + 1) / len(rows),
                text=(
                    "Spielerdetails werden geladen … "
                    f"{index + 1} von {len(rows)}"
                ),
            )

        progress.empty()

        market_data["rows"] = updated_rows
        st.session_state[cache_key] = (
            market_data
        )

        st.rerun()

    if load_history:
        with st.spinner(
            "Passenden Historien-Endpunkt "
            "ermitteln …"
        ):
            template = (
                discover_history_template(
                    api,
                    league_id,
                    rows,
                )
            )

        if template is None:
            market_data["rows"] = [
                {
                    **row,
                    "history_loaded": True,
                }
                for row in rows
            ]

            st.session_state[cache_key] = (
                market_data
            )

            st.warning(
                "Kickbase hat über die getesteten "
                "Endpunkte keine auswertbare "
                "Drei-Tage-Historie geliefert."
            )

        else:
            progress = st.progress(
                0.0,
                text=(
                    "Drei-Tage-Werte werden geladen …"
                ),
            )

            updated_rows = []

            for index, row in enumerate(rows):
                updated_rows.append(
                    enrich_row_with_history(
                        api,
                        league_id,
                        row,
                        template,
                    )
                )

                progress.progress(
                    (index + 1) / len(rows),
                    text=(
                        "Drei-Tage-Werte werden geladen … "
                        f"{index + 1} von {len(rows)}"
                    ),
                )

            progress.empty()

            market_data["rows"] = (
                updated_rows
            )

            st.session_state[cache_key] = (
                market_data
            )

            st.rerun()

    filtered_rows = filter_and_sort_rows(
        rows,
        compact,
    )

    st.caption(
        f"{len(filtered_rows)} von "
        f"{len(rows)} Spielern"
    )

    if not filtered_rows:
        st.info(
            "Für diese Auswahl wurden keine "
            "Spieler gefunden."
        )

        return

    render_market_table(
        filtered_rows,
        compact,
    )

    st.markdown(
        probability_legend_html(),
        unsafe_allow_html=True,
    )

    if not details_loaded:
        st.info(
            "Für vollständige Spielerfotos, Vereinsdaten "
            "und S11-Symbole klicke oben auf "
            "„Spielerfotos, Vereine und "
            "S11-Prognosen laden“."
        )

    if not history_loaded:
        st.info(
            "Die Spalte „3 Tage“ bleibt leer, bis du "
            "oben auf „Drei-Tage-Werte laden“ klickst."
        )

    if not compact:
        with st.expander(
            "Diagnose der Transfermarkt-Daten"
        ):
            player_names = [
                row["name"]
                for row in filtered_rows
            ]

            selected_name = st.selectbox(
                "Spieler auswählen",
                player_names,
                key="market_diagnostic_player",
            )

            selected_row = next(
                row
                for row in filtered_rows
                if row["name"] == selected_name
            )

            st.write(
                "**Verwendeter Detail-Endpunkt:**"
            )

            if selected_row["detail_path"]:
                st.code(
                    selected_row["detail_path"],
                    language="text",
                )

            else:
                st.write(
                    "Spielerdetails wurden noch nicht "
                    "geladen oder der Endpunkt war "
                    "nicht erreichbar."
                )

            st.write(
                "**Verwendeter Historien-Endpunkt:**"
            )

            if selected_row["history_path"]:
                st.code(
                    selected_row["history_path"],
                    language="text",
                )

            else:
                st.write(
                    "Die Drei-Tage-Historie wurde noch "
                    "nicht geladen oder konnte nicht "
                    "ermittelt werden."
                )

            st.write(
                "**Transfermarkt-Rohdaten:**"
            )

            st.json(
                selected_row["raw"],
                expanded=False,
            )

            st.write(
                "**Ergänzende Spielerdaten:**"
            )

            st.json(
                selected_row["details"],
                expanded=False,
            )

            if errors:
                st.write(
                    "**Fehler der Markt-Endpunkte:**"
                )

                st.write(errors)
