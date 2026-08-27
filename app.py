"""
Kickbase Liga-Dashboard mit Streamlit.
"""

import pandas as pd
import streamlit as st

from kickbase_api import KickbaseAPI


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

def first_value(data, keys, default=None):
    """Liest den ersten vorhandenen Wert aus mehreren Feldnamen."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def first_list(data, keys):
    """Liest die erste vorhandene Liste aus mehreren Feldnamen."""
    if not isinstance(data, dict):
        return []

    for key in keys:
        value = data.get(key)

        if isinstance(value, list):
            return value

    return []


def format_currency(value):
    """Formatiert einen Betrag in Millionen Euro."""
    if value is None or value == "":
        return "—"

    try:
        number = float(value)
        formatted = f"{number / 1_000_000:,.2f}"
        formatted = formatted.replace(",", "X")
        formatted = formatted.replace(".", ",")
        formatted = formatted.replace("X", ".")
        return f"{formatted} Mio. €"
    except (TypeError, ValueError):
        return "—"


def format_number(value):
    """Formatiert eine normale Zahl."""
    if value is None or value == "":
        return "—"

    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def map_position(position):
    """Übersetzt eine Positionsnummer."""
    positions = {
        1: "Torwart",
        2: "Abwehr",
        3: "Mittelfeld",
        4: "Sturm",
    }

    try:
        return positions.get(int(position), "Unbekannt")
    except (TypeError, ValueError):
        return "Unbekannt"


def get_player_name(player):
    """Ermittelt den Namen eines Spielers."""
    if not isinstance(player, dict):
        return "Unbekannt"

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

    full_name = f"{first_name} {last_name}".strip()
    return full_name or "Unbekannt"


def get_manager_name(manager):
    """Ermittelt den Namen eines Managers."""
    return str(
        first_value(
            manager,
            ["name", "n", "username", "un", "teamName", "tn"],
            "Unbekannter Manager",
        )
    )


def get_manager_id(manager):
    """Ermittelt die ID eines Managers."""
    value = first_value(
        manager,
        ["id", "i", "userId", "uid", "ui"],
        "",
    )
    return str(value) if value is not None else ""


def get_league_name(league):
    """Ermittelt den Namen einer Liga."""
    return str(
        first_value(
            league,
            ["name", "n", "leagueName", "ln"],
            "Unbekannte Liga",
        )
    )


def get_league_id(league):
    """Ermittelt die ID einer Liga."""
    value = first_value(
        league,
        ["id", "i", "leagueId", "li"],
        "",
    )
    return str(value) if value is not None else ""


def looks_like_league(item):
    """Prüft, ob ein Objekt wahrscheinlich eine Liga ist."""
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


def find_league_list(value, depth=0):
    """
    Durchsucht die komplette Login-Antwort rekursiv
    nach einer wahrscheinlichen Liga-Liste.
    """
    if depth > 6:
        return []

    if isinstance(value, list):
        if value and all(
            isinstance(item, dict) for item in value
        ):
            probable_leagues = [
                item for item in value
                if looks_like_league(item)
            ]

            if probable_leagues:
                return probable_leagues

        for item in value:
            result = find_league_list(item, depth + 1)

            if result:
                return result

    if isinstance(value, dict):
        preferred_keys = [
            "leagues",
            "lgs",
            "ls",
            "league",
            "leagueList",
            "seasonalLeagues",
            "srvl",
        ]

        for key in preferred_keys:
            if key in value:
                result = find_league_list(
                    value[key],
                    depth + 1,
                )

                if result:
                    return result

        for key, nested_value in value.items():
            if key in ["tkn", "token", "accessToken"]:
                continue

            result = find_league_list(
                nested_value,
                depth + 1,
            )

            if result:
                return result

    return []


def find_user_object(value):
    """Sucht ein wahrscheinliches User-Objekt."""
    if not isinstance(value, dict):
        return {}

    for key in ["user", "u", "usr", "me"]:
        possible_user = value.get(key)

        if isinstance(possible_user, dict):
            return possible_user

    return {}


def extract_items(data, preferred_keys):
    """Sucht eine Liste in einer API-Antwort."""
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    direct = first_list(data, preferred_keys)

    if direct:
        return direct

    for key in ["data", "d", "result", "r"]:
        nested = data.get(key)

        if isinstance(nested, list):
            return nested

        if isinstance(nested, dict):
            nested_result = first_list(
                nested,
                preferred_keys,
            )

            if nested_result:
                return nested_result

    return []


def extract_managers(data):
    """Sucht Manager in einer API-Antwort."""
    return extract_items(
        data,
        [
            "users",
            "u",
            "us",
            "managers",
            "ranking",
            "items",
            "it",
        ],
    )


def extract_players(data):
    """Sucht Spieler in einer API-Antwort."""
    return extract_items(
        data,
        ["players", "p", "items", "it"],
    )


def extract_feed_items(data):
    """Sucht Feed-Einträge in einer API-Antwort."""
    return extract_items(
        data,
        ["items", "it", "feed", "f"],
    )


def safe_structure(value, depth=0):
    """
    Erstellt eine sichere Übersicht der API-Struktur.

    Tokenwerte werden ausgeblendet.
    """
    if depth > 4:
        return "[weitere Ebene ausgeblendet]"

    if isinstance(value, dict):
        result = {}

        for key, nested_value in value.items():
            if key.lower() in [
                "tkn",
                "token",
                "accesstoken",
                "password",
                "pass",
            ]:
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
            "Beispielstruktur": safe_structure(
                value[0],
                depth + 1,
            ),
        }

    return f"<{type(value).__name__}>"


def player_table(players):
    """Erstellt die Kader-Tabelle."""
    rows = []

    for player in players:
        rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": map_position(
                    first_value(
                        player,
                        ["position", "pos", "p"],
                    )
                ),
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
                "Status": first_value(
                    player,
                    ["status", "st"],
                    "—",
                ),
            }
        )

    return pd.DataFrame(rows)


def get_feed_meta(item):
    """Liest das Meta-Objekt eines Feed-Eintrags."""
    meta = first_value(item, ["meta", "m"], {})
    return meta if isinstance(meta, dict) else {}


def transfer_row(item):
    """Wandelt einen Transfer in eine Tabellenzeile um."""
    raw_type = first_value(item, ["type", "t"])

    try:
        item_type = int(raw_type)
    except (TypeError, ValueError):
        return None

    event_names = {
        2: "Verkauf",
        3: "Auf Transfermarkt gestellt",
        12: "Kauf",
    }

    if item_type not in event_names:
        return None

    meta = get_feed_meta(item)

    player_name = get_player_name(meta)

    if player_name == "Unbekannt":
        player_name = get_player_name(item)

    amount = first_value(
        meta,
        ["value", "v", "price", "pr", "amount", "mv"],
    )

    if amount is None:
        amount = first_value(
            item,
            ["value", "v", "price", "amount"],
        )

    date = first_value(
        item,
        ["date", "d", "createdAt", "timestamp"],
        "—",
    )

    if isinstance(date, str) and "T" in date:
        date = date.split("T")[0]

    return {
        "Datum": date,
        "Typ": event_names[item_type],
        "Spieler": player_name,
        "Betrag": format_currency(amount),
        "_type": item_type,
        "_amount": amount,
    }


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
# Abmeldung
# ---------------------------------------------------------

if st.session_state.get("logged_in"):
    if st.sidebar.button("Abmelden"):
        st.session_state.clear()
        st.rerun()


# ---------------------------------------------------------
# Anmeldung
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
                "Bitte gib E-Mail-Adresse und Passwort ein."
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

                user = find_user_object(login_result)
                leagues = find_league_list(login_result)

                # Wenn keine Liga in der Login-Antwort steckt,
                # versucht die App einen separaten Liga-Endpunkt.
                separate_league_result = None

                if not leagues:
                    try:
                        separate_league_result = (
                            api.get_leagues()
                        )
                        leagues = find_league_list(
                            separate_league_result
                        )

                        if not leagues:
                            leagues = extract_items(
                                separate_league_result,
                                [
                                    "leagues",
                                    "lgs",
                                    "ls",
                                    "items",
                                    "it",
                                ],
                            )
                    except Exception:
                        separate_league_result = None

                if not leagues:
                    st.error(
                        "Die Anmeldung funktioniert, aber die "
                        "Liga-Liste konnte noch nicht erkannt werden."
                    )

                    st.write(
                        "Sichere Struktur der Login-Antwort:"
                    )
                    st.json(
                        safe_structure(login_result)
                    )

                    if separate_league_result is not None:
                        st.write(
                            "Sichere Struktur der separaten "
                            "Liga-Antwort:"
                        )
                        st.json(
                            safe_structure(
                                separate_league_result
                            )
                        )

                    st.info(
                        "Token und Passwort werden in dieser "
                        "Diagnose automatisch ausgeblendet."
                    )
                    st.stop()

                st.session_state["api"] = api
                st.session_state["user"] = user
                st.session_state["leagues"] = leagues
                st.session_state["logged_in"] = True

                st.rerun()

            except Exception as error:
                st.sidebar.error(str(error))

    st.title("⚽ Kickbase Liga-Dashboard")
    st.info(
        "Gib links deine Kickbase-Zugangsdaten ein "
        "und klicke auf „Einloggen“."
    )
    st.stop()


# ---------------------------------------------------------
# Sitzungsdaten
# ---------------------------------------------------------

api = st.session_state["api"]
current_user = st.session_state.get("user", {})
leagues = st.session_state.get("leagues", [])

if not leagues:
    st.error("Es wurden keine Ligen gefunden.")
    st.stop()


# ---------------------------------------------------------
# Liga auswählen
# ---------------------------------------------------------

league_indices = list(range(len(leagues)))

selected_league_index = st.sidebar.selectbox(
    "Liga auswählen",
    league_indices,
    format_func=lambda index: get_league_name(
        leagues[index]
    ),
)

selected_league = leagues[selected_league_index]
league_id = get_league_id(selected_league)
league_name = get_league_name(selected_league)

if not league_id:
    st.error(
        "Die ausgewählte Liga besitzt keine erkennbare ID."
    )
    st.json(safe_structure(selected_league))
    st.stop()

current_user_id = get_manager_id(current_user)

st.sidebar.success("Erfolgreich angemeldet")

if current_user:
    st.sidebar.caption(
        f"Account: {get_manager_name(current_user)}"
    )


# ---------------------------------------------------------
# Manager laden
# ---------------------------------------------------------

st.title(f"⚽ {league_name}")

try:
    with st.spinner("Manager werden geladen …"):
        manager_result = api.get_league_users(
            league_id
        )

    managers = extract_managers(manager_result)

except Exception as error:
    st.error(
        f"Die Manager konnten nicht geladen werden: {error}"
    )
    st.stop()

if not managers:
    st.error(
        "In der API-Antwort wurde keine Manager-Liste erkannt."
    )

    st.write("Sichere Struktur der Manager-Antwort:")
    st.json(safe_structure(manager_result))
    st.stop()


# ---------------------------------------------------------
# Manager auswählen
# ---------------------------------------------------------

manager_indices = list(range(len(managers)))

selected_manager_index = st.selectbox(
    "👤 Manager auswählen",
    manager_indices,
    format_func=lambda index: get_manager_name(
        managers[index]
    ),
)

selected_manager = managers[selected_manager_index]
selected_user_id = get_manager_id(selected_manager)
selected_user_name = get_manager_name(selected_manager)

if not selected_user_id:
    st.error(
        "Für diesen Manager wurde keine User-ID gefunden."
    )
    st.json(safe_structure(selected_manager))
    st.stop()

is_own_account = (
    bool(current_user_id)
    and selected_user_id == current_user_id
)


# ---------------------------------------------------------
# Kader laden
# ---------------------------------------------------------

players = []
players_error = None

try:
    player_result = api.get_user_players(
        league_id,
        selected_user_id,
    )
    players = extract_players(player_result)

except Exception as error:
    players_error = str(error)


# ---------------------------------------------------------
# Tabs
# ---------------------------------------------------------

tabs = st.tabs(
    [
        "📋 Kader",
        "⚽ Aufstellung",
        "🏪 Transfermarkt",
        "💰 Finanzen",
        "📜 Transferhistorie",
    ]
)

tab_kader = tabs[0]
tab_lineup = tabs[1]
tab_market = tabs[2]
tab_finance = tabs[3]
tab_history = tabs[4]


# ---------------------------------------------------------
# Tab: Kader
# ---------------------------------------------------------

with tab_kader:
    st.subheader(f"Kader von {selected_user_name}")

    if players_error:
        st.error(
            f"Kader konnte nicht geladen werden: "
            f"{players_error}"
        )

    elif not players:
        st.info("Es wurden keine Spieler gefunden.")

        if "player_result" in locals():
            with st.expander(
                "Technische Struktur anzeigen"
            ):
                st.json(
                    safe_structure(player_result)
                )

    else:
        st.metric("Anzahl Spieler", len(players))

        st.dataframe(
            player_table(players),
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Tab: Aufstellung
# ---------------------------------------------------------

with tab_lineup:
    st.subheader(
        f"Aufstellung von {selected_user_name}"
    )

    if not is_own_account:
        st.info(
            "Die aktuelle Aufstellung kann über diesen "
            "Endpunkt möglicherweise nur für den eigenen "
            "Account geladen werden."
        )

    else:
        try:
            lineup_result = api.get_lineup(league_id)
            lineup_players = extract_players(
                lineup_result
            )

            formation = first_value(
                lineup_result,
                ["formation", "f", "type"],
                "Nicht angegeben",
            )

            st.metric("Formation", formation)

            if lineup_players:
                st.dataframe(
                    player_table(lineup_players),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    "Es wurde keine Aufstellung erkannt."
                )

                with st.expander(
                    "Technische Struktur anzeigen"
                ):
                    st.json(
                        safe_structure(lineup_result)
                    )

        except Exception as error:
            st.warning(
                f"Aufstellung konnte nicht geladen werden: "
                f"{error}"
            )


# ---------------------------------------------------------
# Tab: Transfermarkt
# ---------------------------------------------------------

with tab_market:
    st.subheader(
        f"Transfermarkt von {selected_user_name}"
    )

    try:
        market_result = api.get_market(league_id)
        market_players = extract_players(market_result)

        manager_market_players = []

        for player in market_players:
            owner_id = first_value(
                player,
                [
                    "userId",
                    "uid",
                    "ownerId",
                    "sellerId",
                    "ui",
                ],
            )

            if owner_id is not None:
                if str(owner_id) == selected_user_id:
                    manager_market_players.append(player)

        if manager_market_players:
            market_rows = []

            for player in manager_market_players:
                market_rows.append(
                    {
                        "Spieler": get_player_name(
                            player
                        ),
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
                        "Ablauf": first_value(
                            player,
                            [
                                "expiry",
                                "exp",
                                "expiresAt",
                            ],
                            "—",
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(market_rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "Es wurden keine eindeutig diesem Manager "
                "zugeordneten Marktspieler gefunden."
            )

        with st.expander(
            "Gesamten Transfermarkt anzeigen"
        ):
            all_rows = []

            for player in market_players:
                all_rows.append(
                    {
                        "Spieler": get_player_name(
                            player
                        ),
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
                    }
                )

            if all_rows:
                st.dataframe(
                    pd.DataFrame(all_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.write(
                    "Der Transfermarkt ist leer."
                )

    except Exception as error:
        st.error(
            f"Transfermarkt konnte nicht geladen werden: "
            f"{error}"
        )


# ---------------------------------------------------------
# Tab: Finanzen
# ---------------------------------------------------------

with tab_finance:
    st.subheader(
        f"Finanzen von {selected_user_name}"
    )

    team_value = first_value(
        selected_manager,
        ["teamValue", "tv", "squadValue", "sv"],
    )

    if team_value is None and players:
        player_values = []

        for player in players:
            market_value = first_value(
                player,
                ["marketValue", "mv"],
                0,
            )

            try:
                player_values.append(
                    float(market_value)
                )
            except (TypeError, ValueError):
                pass

        if player_values:
            team_value = sum(player_values)

    points = first_value(
        selected_manager,
        ["points", "pt", "totalPoints", "tp"],
        0,
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Kaderwert",
        format_currency(team_value),
    )

    col3.metric(
        "Punkte",
        format_number(points),
    )

    if is_own_account:
        try:
            me_result = api.get_league_me(
                league_id
            )

            budget = first_value(
                me_result,
                ["budget", "b", "cash"],
            )

            col2.metric(
                "Budget",
                format_currency(budget),
            )

        except Exception as error:
            col2.metric(
                "Budget",
                "Nicht verfügbar",
            )

            st.warning(
                f"Budget konnte nicht geladen werden: "
                f"{error}"
            )
    else:
        col2.metric(
            "Budget",
            "Nicht einsehbar",
        )

        st.caption(
            "Das genaue Budget anderer Manager wird "
            "möglicherweise nicht von der API ausgegeben."
        )


# ---------------------------------------------------------
# Tab: Transferhistorie
# ---------------------------------------------------------

with tab_history:
    st.subheader(
        f"Transferhistorie von {selected_user_name}"
    )

    feed_items = []

    try:
        for start in [0, 25, 50, 75, 100]:
            feed_result = api.get_user_feed(
                league_id,
                selected_user_id,
                start,
            )

            page_items = extract_feed_items(
                feed_result
            )

            if not page_items:
                break

            feed_items.extend(page_items)

    except Exception:
        feed_items = []

        try:
            for start in [0, 25, 50, 75, 100]:
                feed_result = api.get_league_feed(
                    league_id,
                    start,
                )

                page_items = extract_feed_items(
                    feed_result
                )

                if not page_items:
                    break

                feed_items.extend(page_items)

        except Exception as error:
            st.error(
                f"Transferhistorie konnte nicht "
                f"geladen werden: {error}"
            )

    transfer_rows = []

    for item in feed_items:
        row = transfer_row(item)

        if row:
            transfer_rows.append(row)

    if transfer_rows:
        visible_rows = []
        purchases = 0.0
        sales = 0.0

        for row in transfer_rows:
            visible_rows.append(
                {
                    "Datum": row["Datum"],
                    "Typ": row["Typ"],
                    "Spieler": row["Spieler"],
                    "Betrag": row["Betrag"],
                }
            )

            try:
                amount = float(
                    row["_amount"] or 0
                )
            except (TypeError, ValueError):
                amount = 0.0

            if row["_type"] == 12:
                purchases += amount

            if row["_type"] == 2:
                sales += amount

        st.dataframe(
            pd.DataFrame(visible_rows),
            use_container_width=True,
            hide_index=True,
        )

        transfer_col1, transfer_col2, transfer_col3 = (
            st.columns(3)
        )

        transfer_col1.metric(
            "Käufe",
            format_currency(purchases),
        )

        transfer_col2.metric(
            "Verkäufe",
            format_currency(sales),
        )

        transfer_col3.metric(
            "Transfer-Saldo",
            format_currency(
                sales - purchases
            ),
        )

        st.caption(
            "Der Transfer-Saldo entspricht Verkäufen "
            "minus Käufen."
        )

    else:
        st.info(
            "Es wurden noch keine passenden "
            "Transferereignisse erkannt."
        )

        if feed_items:
            with st.expander(
                "Sichere Feed-Struktur anzeigen"
            ):
                st.json(
                    safe_structure(
                        feed_items[:3]
                    )
                )
