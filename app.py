"""
Kickbase Liga-Dashboard
Eine Streamlit Web-App zur Übersicht deiner Kickbase-Liga.
"""

import streamlit as st
import pandas as pd
from kickbase_api import KickbaseAPI


# === HILFSFUNKTIONEN ===

def format_currency(value):
    """Formatiert einen Geldbetrag in Millionen Euro."""
    if value is None:
        return "—"
    return f"{value / 1_000_000:.2f} Mio €"


def map_position(pos):
    """Wandelt Positionsnummer in Text um."""
    positionen = {
        1: "Torwart",
        2: "Abwehr",
        3: "Mittelfeld",
        4: "Sturm"
    }
    return positionen.get(pos, "Unbekannt")


def get_player_name(player):
    """Liest den Spielernamen aus (verschiedene API-Feldnamen möglich)."""
    first = player.get("firstName") or player.get("fn") or ""
    last = player.get("lastName") or player.get("ln") or ""
    name = f"{first} {last}".strip()
    return name if name else "Unbekannt"


def get_player_value(player, *keys):
    """Liest einen Wert aus einem Spieler-Objekt (probiert mehrere Feldnamen)."""
    for key in keys:
        if key in player and player[key] is not None:
            return player[key]
    return None


# === SEITEN-KONFIGURATION ===

st.set_page_config(
    page_title="Kickbase Dashboard",
    page_icon="⚽",
    layout="wide"
)


# === SIDEBAR: LOGIN ===

st.sidebar.title("⚽ Kickbase Dashboard")

# Login-Felder
email = st.sidebar.text_input("E-Mail")
password = st.sidebar.text_input("Passwort", type="password")
login_button = st.sidebar.button("Einloggen")

# Login durchführen
if login_button and email and password:
    try:
        api = KickbaseAPI()
        result = api.login(email, password)

        # Daten in Session speichern (bleibt erhalten beim Neuladen)
        st.session_state["api"] = api
st.session_state["user"] = (
    result.get("user")
    or result.get("u")
    or {}
)

st.session_state["leagues"] = (
    result.get("leagues")
    or result.get("lgs")
    or result.get("ls")
    or []
)

st.session_state["logged_in"] = True

        st.sidebar.success("✅ Erfolgreich eingeloggt!")
    except Exception as e:
        st.sidebar.error(f"❌ {str(e)}")

# Prüfen ob eingeloggt
if not st.session_state.get("logged_in", False):
    st.title("⚽ Kickbase Liga-Dashboard")
    st.info("👈 Bitte logge dich in der Sidebar mit deinen Kickbase-Daten ein.")
    st.stop()


# === SIDEBAR: LIGA-AUSWAHL ===

api = st.session_state["api"]
leagues = st.session_state["leagues"]
user_data = st.session_state["user"]

# Liga-Dropdown
liga_namen = [league.get("name", f"Liga {i+1}") for i, league in enumerate(leagues)]
selected_league_index = st.sidebar.selectbox(
    "Liga auswählen",
    range(len(liga_namen)),
    format_func=lambda i: liga_namen[i]
)

selected_league = leagues[selected_league_index]
league_id = selected_league.get("id")

st.sidebar.markdown("---")
st.sidebar.caption(f"Eingeloggt als: {user_data.get('name', user_data.get('n', 'Unbekannt'))}")


# === HAUPTBEREICH: MANAGER-AUSWAHL ===

st.title(f"⚽ {selected_league.get('name', 'Meine Liga')}")

# Liga-Stats laden für Manager-Liste
try:
    stats = api.get_league_stats(league_id)
    users = stats.get("users", stats.get("u", []))
except Exception as e:
    st.error(f"Fehler beim Laden der Liga-Daten: {str(e)}")
    st.stop()

if not users:
    st.warning("Keine Manager in dieser Liga gefunden.")
    st.stop()

# Manager-Namen und IDs extrahieren
manager_names = []
manager_ids = []
for user in users:
    name = user.get("name") or user.get("n") or "Unbekannt"
    uid = user.get("id") or user.get("i") or ""
    manager_names.append(name)
    manager_ids.append(uid)

# Dropdown für Manager-Auswahl
selected_manager_index = st.selectbox(
    "👤 Manager auswählen",
    range(len(manager_names)),
    format_func=lambda i: manager_names[i]
)

selected_user_id = manager_ids[selected_manager_index]
selected_user_name = manager_names[selected_manager_index]
is_own_account = (selected_user_id == user_data.get("id"))

st.markdown("---")


# === TABS ===

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Kader",
    "⚽ Aufstellung",
    "🏪 Transfermarkt",
    "💰 Finanzen",
    "📜 Transferhistorie"
])


# --- TAB 1: KADER ---
with tab1:
    st.subheader(f"Kader von {selected_user_name}")

    try:
        players_data = api.get_user_players(league_id, selected_user_id)
        players = players_data.get("players", players_data.get("p", []))

        if players:
            # Tabelle aufbauen
            rows = []
            for p in players:
                rows.append({
                    "Spieler": get_player_name(p),
                    "Position": map_position(get_player_value(p, "position", "pos") or 0),
                    "Marktwert": format_currency(get_player_value(p, "marketValue", "mv")),
                    "Ø Punkte": get_player_value(p, "averagePoints", "ap") or 0,
                    "Gesamtpunkte": get_player_value(p, "totalPoints", "tp") or 0,
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Anzahl Spieler: {len(players)}")
        else:
            st.info("Keine Spieler gefunden.")

    except Exception as e:
        st.error(f"Fehler beim Laden des Kaders: {str(e)}")


# --- TAB 2: AUFSTELLUNG ---
with tab2:
    st.subheader("Aktuelle Aufstellung")

    if is_own_account:
        try:
            lineup_data = api.get_lineup(league_id)
            formation = lineup_data.get("formation", lineup_data.get("f", "Unbekannt"))
            lineup_players = lineup_data.get("players", lineup_data.get("p", []))

            st.metric("Formation", formation)

            if lineup_players:
                rows = []
                for p in lineup_players:
                    rows.append({
                        "Spieler": get_player_name(p),
                        "Position": map_position(get_player_value(p, "position", "pos") or 0),
                        "Marktwert": format_currency(get_player_value(p, "marketValue", "mv")),
                    })
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Keine Aufstellung gesetzt.")

        except Exception as e:
            st.warning(f"Aufstellung konnte nicht geladen werden: {str(e)}")
    else:
        st.info("ℹ️ Die Aufstellung ist nur für deinen eigenen Account einsehbar.")


# --- TAB 3: TRANSFERMARKT ---
with tab3:
    st.subheader("Transfermarkt")

    try:
        market_data = api.get_market(league_id)
        market_players = market_data.get("players", market_data.get("p", []))

        if market_players:
            rows = []
            for p in market_players:
                # Prüfen ob der Spieler dem ausgewählten Manager gehört
                owner_id = p.get("userId") or p.get("uid") or p.get("ownerId") or ""

                rows.append({
                    "Spieler": get_player_name(p),
                    "Marktwert": format_currency(get_player_value(p, "marketValue", "mv")),
                    "Preis": format_currency(get_player_value(p, "price", "p")),
                    "Besitzer": "📌 Ausgewählter Manager" if owner_id == selected_user_id else "",
                })

            df = pd.DataFrame(rows)

            # Filter: Nur Spieler des ausgewählten Managers
            eigene = df[df["Besitzer"] != ""]
            if not eigene.empty:
                st.write(f"**Spieler von {selected_user_name} auf dem Markt:**")
                st.dataframe(eigene.drop(columns=["Besitzer"]), use_container_width=True, hide_index=True)
            else:
                st.info(f"{selected_user_name} hat aktuell keine Spieler auf dem Transfermarkt.")

            # Alle anzeigen
            with st.expander("Gesamten Transfermarkt anzeigen"):
                st.dataframe(df.drop(columns=["Besitzer"]), use_container_width=True, hide_index=True)
        else:
            st.info("Der Transfermarkt ist leer.")

    except Exception as e:
        st.error(f"Fehler beim Laden des Transfermarkts: {str(e)}")


# --- TAB 4: FINANZEN ---
with tab4:
    st.subheader(f"Finanzen von {selected_user_name}")

    # Kaderwert aus Stats holen
    selected_user_stats = users[selected_manager_index]
    team_value = selected_user_stats.get("teamValue") or selected_user_stats.get("tv")
    points = selected_user_stats.get("points") or selected_user_stats.get("pt") or 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📊 Kaderwert", format_currency(team_value))

    with col2:
        if is_own_account:
            try:
                me_data = api.get_league_me(league_id)
                budget = me_data.get("budget") or me_data.get("b")
                st.metric("💰 Budget", format_currency(budget))
            except:
                st.metric("💰 Budget", "Nicht verfügbar")
        else:
            st.metric("💰 Budget", "Nur eigenes sichtbar")

    with col3:
        st.metric("⭐ Punkte", f"{points:,}".replace(",", "."))

    # Zusatz-Info
    if is_own_account:
        try:
            me_data = api.get_league_me(league_id)
            tv_me = me_data.get("teamValue") or me_data.get("tv")
            if tv_me and budget:
                st.metric("💎 Gesamtwert (Kader + Budget)", format_currency(tv_me + budget))
        except:
            pass


# --- TAB 5: TRANSFERHISTORIE ---
with tab5:
    st.subheader(f"Transferhistorie von {selected_user_name}")

    try:
        # Feed laden (mehrere Seiten für mehr Historie)
        all_items = []
        for start in range(0, 75, 25):  # Bis zu 3 Seiten laden
            try:
                feed_data = api.get_user_feed(league_id, selected_user_id, start=start)
                items = feed_data.get("items", feed_data.get("it", []))
                if not items:
                    break
                all_items.extend(items)
            except:
                break

        # Transfer-Events filtern
        # Typ 2 = Verkauf, Typ 3 = Auf Markt gestellt, Typ 12 = Kauf
        transfer_types = {2: "💸 Verkauf", 3: "🏪 Gelistet", 12: "🛒 Kauf"}

        transfers = []
        for item in all_items:
            item_type = item.get("type") or item.get("t") or 0
            if item_type in transfer_types:
                meta = item.get("meta") or item.get("m") or {}

                # Spielername aus Meta-Daten
                player_fn = meta.get("pfn") or meta.get("fn") or ""
                player_ln = meta.get("pln") or meta.get("ln") or ""
                player_name = f"{player_fn} {player_ln}".strip() or "Unbekannt"

                # Betrag
                value = meta.get("v") or meta.get("val") or meta.get("mv") or None

                # Datum
                date = item.get("date") or item.get("d") or ""
                if date and "T" in date:
                    date = date.split("T")[0]  # Nur Datum, ohne Uhrzeit

                transfers.append({
                    "Datum": date,
                    "Typ": transfer_types[item_type],
                    "Spieler": player_name,
                    "Betrag": format_currency(value) if value else "—",
                })

        if transfers:
            df = pd.DataFrame(transfers)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Gefundene Transfers: {len(transfers)}")

            # Gewinn/Verlust berechnen
            kaeufe = sum(
                (item.get("meta") or item.get("m") or {}).get("v", 0)
                for item in all_items
                if (item.get("type") or item.get("t")) == 12
            )
            verkaeufe = sum(
                (item.get("meta") or item.get("m") or {}).get("v", 0)
                for item in all_items
                if (item.get("type") or item.get("t")) == 2
            )

            if kaeufe or verkaeufe:
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🛒 Ausgaben (Käufe)", format_currency(kaeufe))
                with col2:
                    st.metric("💸 Einnahmen (Verkäufe)", format_currency(verkaeufe))
                with col3:
                    gewinn = verkaeufe - kaeufe
                    st.metric(
                        "📈 Realisierter Gewinn/Verlust",
                        format_currency(abs(gewinn)),
                        delta=format_currency(gewinn),
                        delta_color="normal"
                    )
        else:
            st.info("Keine Transfers in der Historie gefunden.")

    except Exception as e:
        st.error(f"Fehler beim Laden der Transferhistorie: {str(e)}")
