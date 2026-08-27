import streamlit as st
import pandas as pd
from kickbase_api import KickbaseAPI

st.set_page_config(page_title="Kickbase Liga Dashboard", layout="wide")

POSITIONEN = {1: "Torwart", 2: "Abwehr", 3: "Mittelfeld", 4: "Sturm"}


def euro(wert):
    try:
        return f"{wert:,.0f} €".replace(",", ".")
    except Exception:
        return "-"


# ----------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------
st.title("Kickbase Liga Dashboard")

if "api" not in st.session_state:
    st.session_state.api = None

if st.session_state.api is None:
    with st.form("login"):
        email = st.text_input("E-Mail")
        passwort = st.text_input("Passwort", type="password")
        abschicken = st.form_submit_button("Anmelden")
    if abschicken:
        api = KickbaseAPI()
        try:
            api.login(email, passwort)
            st.session_state.api = api
            st.rerun()
        except Exception as fehler:
            st.error("Login fehlgeschlagen: " + str(fehler))
    st.stop()

api = st.session_state.api

# ----------------------------------------------------------------------
# Liga waehlen
# ----------------------------------------------------------------------
ligen = api.get_leagues()
if not ligen:
    st.error("Keine Ligen gefunden.")
    st.stop()

liga_namen = [liga["name"] for liga in ligen]
liga_auswahl = st.selectbox("Liga", liga_namen)
liga = [l for l in ligen if l["name"] == liga_auswahl][0]
liga_id = liga["id"]

# ----------------------------------------------------------------------
# Manager waehlen
# ----------------------------------------------------------------------
manager_liste = api.get_managers(liga_id)
if not manager_liste:
    st.error("Keine Manager gefunden.")
    st.stop()

manager_namen = [m["name"] for m in manager_liste]
manager_auswahl = st.selectbox("Manager", manager_namen)
manager = [m for m in manager_liste if m["name"] == manager_auswahl][0]
manager_id = manager["id"]

# ----------------------------------------------------------------------
# Kader laden
# ----------------------------------------------------------------------
kader = api.get_squad(liga_id, manager_id)
if not kader:
    st.warning("Kein Kader gefunden.")
    st.stop()

zeilen = []
for spieler in kader:
    marktwert = spieler.get("mv") or 0
    gewinn = spieler.get("mvgl") or 0
    einstand = marktwert - gewinn
    aenderung = spieler.get("tfhmvt") or 0
    lo = spieler.get("lo")
    aufgestellt = isinstance(lo, int) and 0 <= lo <= 10
    zeilen.append({
        "Spieler": (str(spieler.get("fn", "")) + " " + str(spieler.get("n", ""))).strip(),
        "Position": POSITIONEN.get(spieler.get("pos"), "unbekannt"),
        "Status": "Start 11" if aufgestellt else "Trading",
        "Einstandspreis": einstand,
        "Marktwert": marktwert,
        "Gewinn gesamt": gewinn,
        "Änderung 24 Stunden": aenderung,
        "_aufgestellt": aufgestellt,
    })

tabelle = pd.DataFrame(zeilen)
tabelle = tabelle.sort_values(
    by=["_aufgestellt", "Gewinn gesamt"], ascending=[False, False]
).reset_index(drop=True)

# ----------------------------------------------------------------------
# Kennzahlen
# ----------------------------------------------------------------------
kaderwert = int(tabelle["Marktwert"].sum())
summe_einstand = int(tabelle["Einstandspreis"].sum())
anzahl_start = int(tabelle["_aufgestellt"].sum())
anzahl_trading = int(len(tabelle) - anzahl_start)
gewinn_verein = int(tabelle["Gewinn gesamt"].sum())
aenderung_24h = int(tabelle["Änderung 24 Stunden"].sum())

gewinn_realisiert, quelle = api.get_realized_profit(liga_id, manager_id)
if gewinn_realisiert is None:
    gewinn_realisiert = 0
    quelle_text = "Feld prft nicht gefunden"
else:
    gewinn_realisiert = int(gewinn_realisiert)
    quelle_text = "Feld prft aus " + str(quelle)

gewinn_gesamt = gewinn_verein + gewinn_realisiert

zeile1 = st.columns(4)
zeile1[0].metric("Kaderwert", euro(kaderwert),
                 help="Summe Einstandspreise: " + euro(summe_einstand))
zeile1[1].metric("Start 11", str(anzahl_start))
zeile1[2].metric("Trading Spieler", str(anzahl_trading))
zeile1[3].metric("Spieler im Verein", str(len(tabelle)))

zeile2 = st.columns(4)
zeile2[0].metric("Gewinn im Verein", euro(gewinn_verein))
zeile2[1].metric("Gewinn realisiert", euro(gewinn_realisiert), help=quelle_text)
zeile2[2].metric("Gewinn gesamt", euro(gewinn_gesamt))
zeile2[3].metric("Änderung 24 Stunden", euro(aenderung_24h))

# ----------------------------------------------------------------------
# Kadertabelle
# ----------------------------------------------------------------------
st.subheader("Kader")

anzeige = tabelle.drop(columns=["_aufgestellt"]).copy()


def farbe_betrag(wert):
    if isinstance(wert, (int, float)):
        if wert > 0:
            return "color: green"
        if wert < 0:
            return "color: red"
    return ""


def zeile_grau(zeile):
    if tabelle.loc[zeile.name, "_aufgestellt"]:
        return [""] * len(zeile)
    return ["background-color: #eeeeee; color: #888888"] * len(zeile)


stil = (anzeige.style
        .apply(zeile_grau, axis=1)
        .applymap(farbe_betrag, subset=["Gewinn gesamt", "Änderung 24 Stunden"])
        .format({
            "Einstandspreis": euro,
            "Marktwert": euro,
            "Gewinn gesamt": euro,
            "Änderung 24 Stunden": euro,
        }))

st.dataframe(stil, use_container_width=True, height=600)

# ----------------------------------------------------------------------
# Alle Daten zu einem Spieler
# ----------------------------------------------------------------------
with st.expander("Alle Daten zu einem Spieler"):
    namen = [(str(s.get("fn", "")) + " " + str(s.get("n", ""))).strip() for s in kader]
    gewaehlt = st.selectbox("Spieler", namen)
    for spieler in kader:
        name = (str(spieler.get("fn", "")) + " " + str(spieler.get("n", ""))).strip()
        if name == gewaehlt:
            st.json(spieler)
            break

# ----------------------------------------------------------------------
# Alle Daten zu diesem Manager
# ----------------------------------------------------------------------
with st.expander("Alle Daten zu diesem Manager"):
    if st.button("Manager-Daten laden"):
        daten = api.explore_manager(liga_id, manager_id)
        if not daten:
            st.info("Keine Endpunkte haben Daten geliefert.")
        else:
            uebersicht = []
            for pfad, inhalt in daten.items():
                felder = list(inhalt.keys()) if isinstance(inhalt, dict) else ["(Liste)"]
                uebersicht.append({"Endpunkt": pfad, "Felder": ", ".join(felder)})
            st.dataframe(pd.DataFrame(uebersicht), use_container_width=True)
            for pfad, inhalt in daten.items():
                with st.expander(pfad):
                    st.json(inhalt)
