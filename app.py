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
    """
    Gibt den ersten vorhandenen Wert aus einer Liste
    möglicher API-Feldnamen zurück.
    """
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def first_list(data, keys):
    """Sucht in einem Dictionary nach der ersten passenden Liste."""
    if not isinstance(data, dict):
        return []

    for key in keys:
        value = data.get(key)

        if isinstance(value, list):
            return value

    return []


def format_currency(value):
    """Formatiert einen Betrag als Millionen Euro."""
    if value is None or value == "":
        return "—"

    try:
        amount = float(value)
        return f"{amount / 1_000_000:,.2f} Mio. €".replace(
            ",", "X"
        ).replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def format_number(value):
    """Formatiert eine Zahl mit deutschen Tausenderpunkten."""
    if value is None or value == "":
        return "—"

    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def map_position(position):
    """Übersetzt Kickbase-Positionsnummern."""
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
    """Ermittelt den Spielernamen aus langen oder kurzen Feldnamen."""
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

    name = f"{first_name} {last_name}".strip()
    return name or "Unbekannt"


def get_manager_name(manager):
    """Ermittelt den Namen eines Managers."""
    return str(
        first_value(
            manager,
            ["name", "n", "username", "un"],
            "Unbekannter Manager",
        )
    )


def get_manager_id(manager):
    """Ermittelt die ID eines Managers."""
    return str(
        first_value(
            manager,
            ["id", "i", "userId", "uid"],
            "",
        )
    )


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
    return str(
        first_value(
            league,
            ["id", "i", "leagueId", "li"],
            "",
        )
    )


def extract_user(login_result):
    """Sucht das User-Objekt in der Login-Antwort."""
    user = first_value(
        login_result,
        ["user", "u", "usr"],
        {},
    )

    return user if isinstance(user, dict) else {}


def extract_leagues(login_result):
    """Sucht die Liga-Liste in der Login-Antwort."""
    leagues = first_list(
        login_result,
        ["leagues", "lgs", "ls", "leaguesData"],
    )

    if leagues:
        return leagues

    user = extract_user(login_result)

    return first_list(
        user,
        ["leagues", "lgs", "ls"],
    )


def extract_managers(stats):
    """Sucht die Manager-Liste in den Liga-Statistiken."""
    managers = first_list(
        stats,
        ["users", "us", "u", "managers", "ranking"],
    )

    if managers:
        return managers

    # Manche Antworten enthalten ein zusätzliches Datenobjekt.
    nested_data = first_value(
        stats,
        ["data", "d", "stats"],
        {},
    )

    return first_list(
        nested_data,
        ["users", "us", "u", "managers", "ranking"],
    )


def extract_players(data):
    """Sucht eine Spielerliste in einer API-Antwort."""
    players = first_list(
        data,
        ["players", "p", "it", "items"],
    )

    if players:
        return players

    nested_data = first_value(
        data,
        ["data", "d"],
        {},
    )

    return first_list(
        nested_data,
        ["players", "p", "it", "items"],
    )


def extract_feed_items(data):
    """Sucht Feed-Einträge in einer API-Antwort."""
    items = first_list(
        data,
        ["items", "it", "feed", "f"],
    )

    if items:
        return items

    nested_data = first_value(
        data,
        ["data", "d"],
        {},
    )

    return first_list(
        nested_data,
        ["items", "it", "feed", "f"],
    )


def player_rows(players):
    """Baut eine Tabelle aus einer Spielerliste."""
    rows = []

    for player in players:
        position = first_value(
            player,
            ["position", "pos", "p"],
        )
        market_value = first_value(
            player,
            ["marketValue", "mv"],
        )
        average_points = first_value(
            player,
            ["averagePoints", "ap", "avgPoints"],
        )
        total_points = first_value(
            player,
            ["totalPoints", "tp", "points"],
        )
        status = first_value(
            player,
            ["status", "st"],
            "—",
        )

        rows.append(
            {
                "Spieler": get_player_name(player),
                "Position": map_position(position),
                "Marktwert": format_currency(market_value),
                "Ø Punkte": format_number(average_points),
                "Gesamtpunkte": format_number(total_points),
                "Status": status,
            }
        )

    return rows


def get_feed_meta(item):
    """Liest das Meta-Objekt eines Feed-Eintrags."""
    meta = first_value(item, ["meta", "m"], {})
    return meta if isinstance(meta, dict) else {}


def feed_user_id(item):
    """Sucht die Manager-ID in einem Feed-Eintrag."""
    meta = get_feed_meta(item)

    value = first_value(
        item,
        ["userId", "uid", "ownerId"],
    )

    if value is None:
        value = first_value(
            meta,
            ["userId", "uid", "buyerId", "sellerId"],
        )

    return str(value) if value is not None else ""


def transfer_row(item):
    """Wandelt einen Transfer-Feed-Eintrag in eine Tabellenzeile um."""
    raw_type = first_value(item, ["type", "t"])

    try:
        item_type = int(raw_type)
    except (TypeError, ValueError):
        return None

    transfer_types = {
        2: "Verkauf",
        3: "Auf Transfermarkt gestellt",
        12: "Kauf",
    }

    if item_type not in transfer_types:
        return None

    meta = get_feed_meta(item)

    player_name = get_player_name(meta)

    if player_name == "Unbekannt":
        player_name = get_player_name(item)

    amount = first_value(
        meta,
        ["value", "v", "price", "pr", "amount", "a", "mv"],
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
        "Typ": transfer_types[item_type],
        "Spieler": player_name,
        "Betrag": format_currency(amount),
        "_typ": item_type,
        "_betrag": amount,
    }


# ---------------------------------------------------------
# Streamlit-Konfiguration
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
                "Bitte gib deine E-Mail-Adresse und dein Passwort ein."
            )
        else:
            try:
                with st.spinner("Anmeldung bei Kickbase läuft …"):
                    api = KickbaseAPI()
                    login_result = api.login(email, password)

                user = extract_user(login_result)
                leagues = extract_leagues(login_result)

               if not leagues:
    st.sidebar.error(
        "Die Anmeldung hat funktioniert, aber in der "
        "Antwort wurden keine Ligen gefunden."
    )

    # Zeigt nur die Feldnamen, niemals Passwort oder Tokenwerte.
    sichere_feldnamen = [
        key for key in login_result.keys()
        if key not in ("tkn", "token")
    ]

    st.write("Felder der Kickbase-Antwort:")
    st.code(", ".join(sichere_feldnamen))

    with st.expander("Struktur der Antwort untersuchen"):
        struktur = {}

        for key, value in login_result.items():
            if key in ("tkn", "token"):
                struktur[key] = "[AUSGEBLENDET]"
            elif isinstance(value, dict):
                struktur[key] = {
                    "Typ": "Objekt",
                    "Felder": list(value.keys())
                }
            elif isinstance(value, list):
                struktur[key] = {
                    "Typ": "Liste",
                    "Anzahl": len(value)
                }
            else:
                struktur[key] = {
                    "Typ": type(value).__name__
                }

        st.json(struktur)
                else:
                    st.session_state["api"] = api
                    st.session_state["user"] = user
                    st.session_state["leagues"] = leagues
                    st.session_state["logged_in"] = True

                    st.rerun()

            except Exception as error:
                st.sidebar.error(str(error))

    st.title("⚽ Kickbase Liga-Dashboard")
    st.info(
        "Gib links deine Kickbase-Zugangsdaten ein und "
        "klicke auf „Einloggen“."
    )
    st.stop()


# ---------------------------------------------------------
# Daten aus der Sitzung
# ---------------------------------------------------------

api = st.session_state["api"]
current_user = st.session_state.get("user", {})
leagues = st.session_state.get("leagues", [])

if not leagues:
    st.error("Für deinen Account wurden keine Ligen gefunden.")
    st.stop()


# ---------------------------------------------------------
# Liga auswählen
# ---------------------------------------------------------

league_indices = list(range(len(leagues)))

selected_league_index = st.sidebar.selectbox(
    "Liga auswählen",
    league_indices,
    format_func=lambda index: get_league_name(leagues[index]),
)

selected_league = leagues[selected_league_index]
league_id = get_league_id(selected_league)
league_name = get_league_name(selected_league)

if not league_id:
    st.error("Die ausgewählte Liga besitzt keine erkennbare Liga-ID.")
    st.stop()

current_user_id = get_manager_id(current_user)

st.sidebar.success("Erfolgreich angemeldet")
st.sidebar.caption(
    f"Account: {get_manager_name(current_user)}"
)


# ---------------------------------------------------------
# Manager laden
# ---------------------------------------------------------

st.title(f"⚽ {league_name}")

try:
    with st.spinner("Liga wird geladen …"):
        league_stats = api.get_league_stats(league_id)

    managers = extract_managers(league_stats)

except Exception as error:
    st.error(f"Liga konnte nicht geladen werden: {error}")
    st.stop()

if not managers:
    st.error(
        "In der API-Antwort wurde keine Manager-Liste gefunden."
    )

    with st.expander("Technische API-Antwort anzeigen"):
        st.json(league_stats)

    st.stop()


# ---------------------------------------------------------
# Manager auswählen
# ---------------------------------------------------------

manager_indices = list(range(len(managers)))

selected_manager_index = st.selectbox(
    "👤 Manager auswählen",
    manager_indices,
    format_func=lambda index: get_manager_name(managers[index]),
)

selected_manager = managers[selected_manager_index]
selected_user_id = get_manager_id(selected_manager)
selected_user_name = get_manager_name(selected_manager)

if not selected_user_id:
    st.error(
        "Für diesen Manager wurde keine erkennbare User-ID gefunden."
    )
    st.stop()

is_own_account = (
    bool(current_user_id)
    and str(selected_user_id) == str(current_user_id)
)


# ---------------------------------------------------------
# Kader einmalig laden
# ---------------------------------------------------------

players = []
players_error = None

try:
    players_data = api.get_user_players(
        league_id,
        selected_user_id,
    )
    players = extract_players(players_data)

except Exception as error:
    players_error = str(error)


# ---------------------------------------------------------
# Tabs
# ---------------------------------------------------------

tab_kader, tab_lineup, tab_market, tab_finance, tab_history = st.tabs(
    [
        "📋 Kader",
        "⚽ Aufstellung",
        "🏪 Transfermarkt",
        "💰 Finanzen",
        "📜 Transferhistorie",
    ]
)


# ---------------------------------------------------------
# Tab 1: Kader
# ---------------------------------------------------------

with tab_kader:
    st.subheader(f"Kader von {selected_user_name}")

    if players_error:
        st.error(f"Kader konnte nicht geladen werden: {players_error}")

    elif not players:
        st.info("Für diesen Manager wurden keine Spieler gefunden.")

    else:
        rows = player_rows(players)
        dataframe = pd.DataFrame(rows)

        st.metric("Anzahl Spieler", len(players))

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Tab 2: Aufstellung
# ---------------------------------------------------------

with tab_lineup:
    st.subheader(f"Aufstellung von {selected_user_name}")

    if not is_own_account:
        st.info(
            "Der verwendete Lineup-Endpunkt liefert grundsätzlich "
            "nur die Aufstellung des angemeldeten Accounts."
        )

        if players:
            st.write(
                "Als Ersatz wird der vollständige Kader angezeigt. "
                "Die Startelf kann daraus nicht sicher bestimmt werden."
            )

            st.dataframe(
                pd.DataFrame(player_rows(players)),
                use_container_width=True,
                hide_index=True,
            )

    else:
        try:
            lineup_data = api.get_lineup(league_id)
            lineup_players = extract_players(lineup_data)

            formation = first_value(
                lineup_data,
                ["formation", "f", "type"],
                "Nicht angegeben",
            )

            st.metric("Formation", formation)

            if lineup_players:
                st.dataframe(
                    pd.DataFrame(player_rows(lineup_players)),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    "In der API-Antwort wurde keine Aufstellung gefunden."
                )

                with st.expander("Technische API-Antwort anzeigen"):
                    st.json(lineup_data)

        except Exception as error:
            st.warning(
                f"Aufstellung konnte nicht geladen werden: {error}"
            )


# ---------------------------------------------------------
# Tab 3: Transfermarkt
# ---------------------------------------------------------

with tab_market:
    st.subheader(
        f"Transfermarkt-Spieler von {selected_user_name}"
    )

    try:
        market_data = api.get_market(league_id)
        market_players = extract_players(market_data)

        selected_market_players = []

        for player in market_players:
            owner = first_value(
                player,
                ["userId", "uid", "ownerId", "sellerId"],
            )

            if owner is None:
                meta = first_value(player, ["meta", "m"], {})

                if isinstance(meta, dict):
                    owner = first_value(
                        meta,
                        ["userId", "uid", "ownerId", "sellerId"],
                    )

            if owner is not None and str(owner) == str(selected_user_id):
                selected_market_players.append(player)

        if selected_market_players:
            rows = []

            for player in selected_market_players:
                rows.append(
                    {
                        "Spieler": get_player_name(player),
                        "Marktwert": format_currency(
                            first_value(
                                player,
                                ["marketValue", "mv"],
                            )
                        ),
                        "Angebotspreis": format_currency(
                            first_value(
                                player,
                                ["price", "pr", "value", "v"],
                            )
                        ),
                        "Ablauf": first_value(
                            player,
                            ["expiry", "exp", "expiresAt"],
                            "—",
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                f"Es wurden aktuell keine eindeutig {selected_user_name} "
                "zugeordneten Transfermarkt-Spieler gefunden."
            )

        with st.expander("Gesamten Transfermarkt anzeigen"):
            all_market_rows = []

            for player in market_players:
                all_market_rows.append(
                    {
                        "Spieler": get_player_name(player),
                        "Marktwert": format_currency(
                            first_value(
                                player,
                                ["marketValue", "mv"],
                            )
                        ),
                        "Angebotspreis": format_currency(
                            first_value(
                                player,
                                ["price", "pr", "value", "v"],
                            )
                        ),
                    }
                )

            if all_market_rows:
                st.dataframe(
                    pd.DataFrame(all_market_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.write("Der Transfermarkt ist leer.")

    except Exception as error:
        st.error(
            f"Transfermarkt konnte nicht geladen werden: {error}"
        )


# ---------------------------------------------------------
# Tab 4: Finanzen
# ---------------------------------------------------------

with tab_finance:
    st.subheader(f"Finanzen von {selected_user_name}")

    team_value = first_value(
        selected_manager,
        ["teamValue", "tv", "squadValue", "sv"],
    )

    # Ersatzberechnung: Summe der Marktwerte aller Spieler.
    if team_value is None and players:
        values = []

        for player in players:
            value = first_value(
                player,
                ["marketValue", "mv"],
                0,
            )

            try:
                values.append(float(value))
            except (TypeError, ValueError):
                pass

        if values:
            team_value = sum(values)

    points = first_value(
        selected_manager,
        ["points", "pt", "totalPoints", "tp"],
        0,
    )

    column_1, column_2, column_3 = st.columns(3)

    column_1.metric(
        "Kaderwert",
        format_currency(team_value),
    )

    column_3.metric(
        "Punkte",
        format_number(points),
    )

    if is_own_account:
        try:
            me_data = api.get_league_me(league_id)

            budget = first_value(
                me_data,
                ["budget", "b", "cash"],
            )

            own_team_value = first_value(
                me_data,
                ["teamValue", "tv", "squadValue"],
            )

            if own_team_value is not None:
                column_1.metric(
                    "Kaderwert",
                    format_currency(own_team_value),
                )

            column_2.metric(
                "Budget",
                format_currency(budget),
            )

        except Exception as error:
            column_2.metric("Budget", "Nicht verfügbar")
            st.warning(
                f"Eigene Finanzdaten konnten nicht geladen werden: {error}"
            )

    else:
        column_2.metric("Budget", "Nicht einsehbar")
        st.caption(
            "Das genaue Budget anderer Manager wird von diesem "
            "API-Endpunkt nicht bereitgestellt."
        )


# ---------------------------------------------------------
# Tab 5: Transferhistorie
# ---------------------------------------------------------

with tab_history:
    st.subheader(
        f"Transferhistorie von {selected_user_name}"
    )

    all_feed_items = []
    used_league_feed = False

    # Zuerst wird der User-Feed probiert.
    try:
        for start in (0, 25, 50, 75, 100):
            feed_data = api.get_user_feed(
                league_id,
                selected_user_id,
                start,
            )
            items = extract_feed_items(feed_data)

            if not items:
                break

            all_feed_items.extend(items)

    except Exception:
        # Falls der User-Feed nicht existiert, wird der Liga-Feed verwendet.
        used_league_feed = True
        all_feed_items = []

        try:
            for start in (0, 25, 50, 75, 100):
                feed_data = api.get_league_feed(
                    league_id,
                    start,
                )
                items = extract_feed_items(feed_data)

                if not items:
                    break

                all_feed_items.extend(items)

        except Exception as error:
            st.error(
                f"Transferhistorie konnte nicht geladen werden: {error}"
            )

    transfer_rows = []

    for item in all_feed_items:
        # Beim Liga-Feed möglichst auf den ausgewählten User filtern.
        if used_league_feed:
            item_user_id = feed_user_id(item)

            if item_user_id and item_user_id != str(selected_user_id):
                continue

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
                amount = float(row["_betrag"] or 0)
            except (TypeError, ValueError):
                amount = 0.0

            if row["_typ"] == 12:
                purchases += amount

            elif row["_typ"] == 2:
                sales += amount

        st.dataframe(
            pd.DataFrame(visible_rows),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            f"{len(visible_rows)} Transferereignisse geladen."
        )

        finance_column_1, finance_column_2, finance_column_3 = st.columns(3)

        finance_column_1.metric(
            "Käufe",
            format_currency(purchases),
        )
        finance_column_2.metric(
            "Verkäufe",
            format_currency(sales),
        )
        finance_column_3.metric(
            "Transfer-Saldo",
            format_currency(sales - purchases),
        )

        st.info(
            "Der Transfer-Saldo ist Verkäufe minus Käufe. Ein echter "
            "realisierter Gewinn je Spieler kann nur berechnet werden, "
            "wenn für denselben Spieler sowohl Kaufpreis als auch "
            "Verkaufspreis vollständig im geladenen Feed vorhanden sind."
        )

    else:
        st.info(
            "Es wurden keine passenden Transfers gefunden. "
            "Möglicherweise verwendet der Feed andere Ereignistypen "
            "oder stellt für diesen Manager keine vollständige "
            "Historie bereit."
        )

        if all_feed_items:
            with st.expander("Technischen Feed zur Fehleranalyse anzeigen"):
                st.json(all_feed_items[:10])
