"""
Kickbase Liga-Dashboard.
"""

import pandas as pd
import streamlit as st

from kickbase_api import KickbaseAPI


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


def format_currency(value):
    """Formatiert einen Geldbetrag."""
    if value is None or value == "":
        return "—"

    try:
        amount = float(value) / 1_000_000
        text = f"{amount:,.2f}"
        text = text.replace(",", "X")
        text = text.replace(".", ",")
        text = text.replace("X", ".")
        return f"{text} Mio. €"
    except (TypeError, ValueError):
        return "—"


def format_number(value):
    """Formatiert eine Zahl."""
    if value is None or value == "":
        return "—"

    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def get_league_id(league):
    """Ermittelt die Liga-ID."""
    value = first_value(
        league,
        ["id", "i", "leagueId", "li"],
        "",
    )

    return str(value) if value is not None else ""


def get_league_name(league):
    """Ermittelt den Namen der Liga."""
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
    """Ermittelt den Namen eines Managers."""
    return str(
        first_value(
            manager,
            [
                "name",
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
    """Ermittelt den Namen eines Spielers."""
    direct_name = first_value(
        player,
        ["name", "n", "playerName", "pn"],
    )

    if direct_name:
        return str(direct_name)

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

    name = f"{first_name} {last_name}".strip()
    return name or "Unbekannt"


def looks_like_league(item):
    """Prüft, ob ein Objekt wie eine Liga aussieht."""
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
    """Prüft, ob ein Objekt wie ein Manager aussieht."""
    if not isinstance(item, dict):
        return False

    manager_id = get_manager_id(item)
    manager_name = get_manager_name(item)

    if not manager_id:
        return False

    if manager_name == "Unbekannter Manager":
        return False

    manager_fields = {
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
    }

    return bool(manager_fields.intersection(item.keys()))


def find_leagues(value, depth=0):
    """Sucht rekursiv nach der Liga-Liste."""
    if depth > 7:
        return []

    if isinstance(value, list):
        leagues = [
            item for item in value
            if looks_like_league(item)
        ]

        if leagues:
            return leagues

        for item in value:
            result = find_leagues(item, depth + 1)

            if result:
                return result

    if isinstance(value, dict):
        preferred_keys = [
            "leagues",
            "lgs",
            "ls",
            "leagueList",
            "seasonalLeagues",
            "srvl",
        ]

        for key in preferred_keys:
            if key in value:
                result = find_leagues(
                    value[key],
                    depth + 1,
                )

                if result:
                    return result

        for key, nested_value in value.items():
            if key in ["tkn", "token", "accessToken"]:
                continue

            result = find_leagues(
                nested_value,
                depth + 1,
            )

            if result:
                return result

    return []


def find_managers(value, depth=0):
    """Sucht rekursiv nach einer Liste von Managern."""
    if depth > 8:
        return []

    if isinstance(value, list):
        managers = [
            item for item in value
            if looks_like_manager(item)
        ]

        if managers:
            return managers

        for item in value:
            result = find_managers(item, depth + 1)

            if result:
                return result

    if isinstance(value, dict):
        preferred_keys = [
            "users",
            "us",
            "u",
            "managers",
            "members",
            "ranking",
            "standings",
            "participants",
            "teams",
            "it",
            "items",
        ]

        for key in preferred_keys:
            if key in value:
                result = find_managers(
                    value[key],
                    depth + 1,
                )

                if result:
                    return result

        for nested_value in value.values():
            result = find_managers(
                nested_value,
                depth + 1,
            )

            if result:
                return result

    return []


def find_players(value, depth=0):
    """Sucht rekursiv nach Spielern."""
    if depth > 7:
        return []

    if isinstance(value, list):
        possible_players = []

        for item in value:
            if not isinstance(item, dict):
                continue

            has_name = (
                "firstName" in item
                or "fn" in item
                or "lastName" in item
                or "ln" in item
                or "n" in item
            )

            has_player_value = (
                "marketValue" in item
                or "mv" in item
                or "position" in item
                or "pos" in item
                or "totalPoints" in item
                or "tp" in item
            )

            if has_name and has_player_value:
                possible_players.append(item)

        if possible_players:
            return possible_players

        for item in value:
            result = find_players(item, depth + 1)

            if result:
                return result

    if isinstance(value, dict):
        preferred_keys = [
            "players",
            "p",
            "it",
            "items",
            "lp",
            "squad",
        ]

        for key in preferred_keys:
            if key in value:
                result = find_players(
                    value[key],
                    depth + 1,
                )

                if result:
                    return result

        for nested_value in value.values():
            result = find_players(
                nested_value,
                depth + 1,
            )

            if result:
                return result

    return []


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


def create_player_table(players):
    """Erstellt die Tabelle für den Kader."""
    positions = {
        1: "Torwart",
        2: "Abwehr",
        3: "Mittelfeld",
        4: "Sturm",
    }

    rows = []

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

        rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": position_name,
                "Marktwert": format_currency(
                    first_value(
                        player,
                        ["marketValue", "mv"],
                    )
                ),
                "Ø Punkte": format_number(
                    first_value(
                        player,
                        ["averagePoints", "ap"],
                    )
                ),
                "Gesamtpunkte": format_number(
                    first_value(
                        player,
                        ["totalPoints", "tp", "points"],
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# Streamlit-Einstellungen
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
                with st.spinner(
                    "Anmeldung bei Kickbase läuft …"
                ):
                    api = KickbaseAPI()
                    login_result = api.login(
                        email,
                        password,
                    )

                leagues = find_leagues(login_result)

                if not leagues:
                    st.error(
                        "Der Login funktioniert, aber die "
                        "Liga-Liste wurde nicht erkannt."
                    )

                    st.json(
                        safe_structure(login_result)
                    )

                    st.stop()

                st.session_state["api"] = api
                st.session_state["login_result"] = login_result
                st.session_state["leagues"] = leagues
                st.session_state["logged_in"] = True

                st.rerun()

            except Exception as error:
                st.sidebar.error(str(error))

    st.title("⚽ Kickbase Liga-Dashboard")

    st.info(
        "Gib links deine Kickbase-Zugangsdaten ein."
    )

    st.stop()


# ---------------------------------------------------------
# Liga auswählen
# ---------------------------------------------------------

api = st.session_state["api"]
login_result = st.session_state["login_result"]
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
# Manager suchen
# ---------------------------------------------------------

managers = find_managers(selected_league)
manager_sources = []
manager_errors = []

if not managers:
    with st.spinner("Manager der Liga werden geladen …"):
        manager_sources, manager_errors = (
            api.get_league_sources(league_id)
        )

    for source in manager_sources:
        found = find_managers(source["data"])

        if found:
            managers = found
            break

if not managers:
    managers = find_managers(login_result)


# ---------------------------------------------------------
# Wenn keine Manager gefunden wurden
# ---------------------------------------------------------

if not managers:
    st.error(
        "Die Liga wurde gefunden, aber die Managerliste "
        "konnte nicht erkannt werden."
    )

    for source in manager_sources:
        with st.expander(
            f"Struktur von {source['path']}"
        ):
            st.json(
                safe_structure(source["data"])
            )

    with st.expander("Fehler der Endpunkte"):
        st.write(manager_errors)

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
selected_user_id = get_manager_id(selected_manager)
selected_manager_name = get_manager_name(
    selected_manager
)


# ---------------------------------------------------------
# Übersicht
# ---------------------------------------------------------

col1, col2, col3 = st.columns(3)

col1.metric(
    "Kaderwert",
    format_currency(
        first_value(
            selected_manager,
            ["teamValue", "tv", "squadValue", "sv"],
        )
    ),
)

col2.metric(
    "Punkte",
    format_number(
        first_value(
            selected_manager,
            ["points", "pt", "totalPoints", "tp"],
        )
    ),
)

col3.metric(
    "Platzierung",
    format_number(
        first_value(
            selected_manager,
            ["rank", "placement", "r", "pl"],
        )
    ),
)


# ---------------------------------------------------------
# Spieltag auswählen
# ---------------------------------------------------------

day_number = st.number_input(
    "Spieltag",
    min_value=1,
    max_value=34,
    value=1,
    step=1,
)


# ---------------------------------------------------------
# Kader laden
# ---------------------------------------------------------

players = []
players_error = None
player_result = None

try:
    with st.spinner("Kader wird geladen …"):
        player_result = api.get_user_players(
            league_id,
            selected_user_id,
            day_number=int(day_number),
        )

    players = find_players(player_result)

except Exception as error:
    players_error = str(error)


# ---------------------------------------------------------
# Tabs
# ---------------------------------------------------------

tabs = st.tabs(
    [
        "📋 Kader",
        "🏪 Transfermarkt",
        "💰 Finanzen",
        "📜 Transferhistorie",
    ]
)

tab_kader = tabs[0]
tab_market = tabs[1]
tab_finance = tabs[2]
tab_history = tabs[3]


# ---------------------------------------------------------
# Tab: Kader
# ---------------------------------------------------------

with tab_kader:
    st.subheader(
        f"Kader von {selected_manager_name}"
    )

    if players_error:
        st.error(
            f"Kader konnte nicht geladen werden: "
            f"{players_error}"
        )

    elif players:
        st.metric("Anzahl Spieler", len(players))

        st.dataframe(
            create_player_table(players),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "Die Antwort kam an, aber es wurden keine "
            "Spieler erkannt."
        )

        if player_result is not None:
            with st.expander(
                "Sichere Struktur anzeigen"
            ):
                st.json(
                    safe_structure(player_result)
                )


# ---------------------------------------------------------
# Tab: Transfermarkt
# ---------------------------------------------------------

with tab_market:
    st.subheader("Transfermarkt")

    try:
        market_result = api.get_market(league_id)
        market_players = find_players(market_result)

        if market_players:
            market_rows = []

            for player in market_players:
                owner_id = first_value(
                    player,
                    [
                        "userId",
                        "uid",
                        "ui",
                        "ownerId",
                        "sellerId",
                    ],
                )

                if owner_id is not None:
                    owner_text = (
                        selected_manager_name
                        if str(owner_id) == selected_user_id
                        else "Anderer Manager"
                    )
                else:
                    owner_text = "Kickbase"

                market_rows.append(
                    {
                        "Spieler": get_player_name(player),
                        "Marktwert": format_currency(
                            first_value(
                                player,
                                ["marketValue", "mv"],
                            )
                        ),
                        "Preis": format_currency(
                            first_value(
                                player,
                                ["price", "pr", "value"],
                            )
                        ),
                        "Anbieter": owner_text,
                    }
                )

            st.dataframe(
                pd.DataFrame(market_rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "Es wurden keine Marktspieler erkannt."
            )

            with st.expander(
                "Sichere Struktur anzeigen"
            ):
                st.json(
                    safe_structure(market_result)
                )

    except Exception as error:
        st.warning(
            f"Transfermarkt konnte nicht geladen "
            f"werden: {error}"
        )


# ---------------------------------------------------------
# Tab: Finanzen
# ---------------------------------------------------------

with tab_finance:
    st.subheader(
        f"Finanzen von {selected_manager_name}"
    )

    team_value = first_value(
        selected_manager,
        ["teamValue", "tv", "squadValue", "sv"],
    )

    if team_value is None and players:
        values = []

        for player in players:
            market_value = first_value(
                player,
                ["marketValue", "mv"],
                0,
            )

            try:
                values.append(float(market_value))
            except (TypeError, ValueError):
                pass

        if values:
            team_value = sum(values)

    finance_col1, finance_col2 = st.columns(2)

    finance_col1.metric(
        "Kaderwert",
        format_currency(team_value),
    )

    try:
        me_result = api.get_me(league_id)

        budget = first_value(
            me_result,
            ["budget", "b", "cash"],
        )

        finance_col2.metric(
            "Eigenes Budget",
            format_currency(budget),
        )

    except Exception:
        finance_col2.metric(
            "Eigenes Budget",
            "Nicht verfügbar",
        )


# ---------------------------------------------------------
# Tab: Transferhistorie
# ---------------------------------------------------------

with tab_history:
    st.subheader("Transferhistorie der Liga")

    feed_items = []

    try:
        for start in [0, 25, 50, 75]:
            feed_result = api.get_league_feed(
                league_id,
                start,
            )

            if isinstance(feed_result, dict):
                page_items = (
                    feed_result.get("items")
                    or feed_result.get("it")
                    or []
                )
            else:
                page_items = []

            if not page_items:
                break

            feed_items.extend(page_items)

    except Exception as error:
        st.warning(
            f"Feed konnte nicht geladen werden: {error}"
        )

    event_names = {
        2: "Verkauf",
        3: "Auf Markt gestellt",
        12: "Kauf",
    }

    transfer_rows = []

    for item in feed_items:
        raw_type = first_value(item, ["type", "t"])

        try:
            item_type = int(raw_type)
        except (TypeError, ValueError):
            continue

        if item_type not in event_names:
            continue

        meta = first_value(item, ["meta", "m"], {})

        if not isinstance(meta, dict):
            meta = {}

        player_name = get_player_name(meta)

        if player_name == "Unbekannt":
            player_name = get_player_name(item)

        amount = first_value(
            meta,
            ["value", "v", "price", "pr", "mv"],
        )

        date = first_value(
            item,
            ["date", "d", "createdAt"],
            "—",
        )

        if isinstance(date, str) and "T" in date:
            date = date.split("T")[0]

        transfer_rows.append(
            {
                "Datum": date,
                "Typ": event_names[item_type],
                "Spieler": player_name,
                "Betrag": format_currency(amount),
            }
        )

    if transfer_rows:
        st.dataframe(
            pd.DataFrame(transfer_rows),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "Es wurden keine Transferereignisse erkannt."
        )

        if feed_items:
            with st.expander(
                "Sichere Feed-Struktur anzeigen"
            ):
                st.json(
                    safe_structure(feed_items[:3])
                )
