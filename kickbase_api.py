import requests

BASE_URL = "https://api.kickbase.com"


class KickbaseAPI:
    def __init__(self):
        self.token = None
        self.login_data = None

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        return headers

    def _get(self, path):
        """GET-Anfrage. Gibt bei Fehler None zurueck."""
        try:
            response = requests.get(BASE_URL + path, headers=self._headers(), timeout=20)
        except Exception:
            return None
        if response.status_code != 200:
            return None
        try:
            return response.json()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self, email, password):
        body = {"em": email, "pass": password, "loy": False, "rep": {}}
        response = requests.post(BASE_URL + "/v4/user/login", json=body, timeout=20)
        if response.status_code != 200:
            raise Exception("Login fehlgeschlagen (Status " + str(response.status_code) + ")")
        data = response.json()
        token = data.get("tkn")
        if not token:
            raise Exception("Kein Token in der Antwort gefunden")
        self.token = token
        self.login_data = data
        return data

    # ------------------------------------------------------------------
    # Ligen
    # ------------------------------------------------------------------
    def get_leagues(self):
        """Sucht rekursiv nach Liga-Objekten in der Login-Antwort."""
        gefunden = []

        def suche(objekt):
            if isinstance(objekt, dict):
                hat_id = "i" in objekt or "id" in objekt
                hat_name = "n" in objekt or "name" in objekt
                if hat_id and hat_name:
                    liga_id = str(objekt.get("i", objekt.get("id")))
                    liga_name = objekt.get("n", objekt.get("name"))
                    if liga_id and liga_name and len(liga_id) > 4:
                        gefunden.append({"id": liga_id, "name": liga_name})
                for wert in objekt.values():
                    suche(wert)
            elif isinstance(objekt, list):
                for eintrag in objekt:
                    suche(eintrag)

        suche(self.login_data)

        # Duplikate entfernen
        eindeutig = {}
        for liga in gefunden:
            eindeutig[liga["id"]] = liga
        return list(eindeutig.values())

    # ------------------------------------------------------------------
    # Manager
    # ------------------------------------------------------------------
    def get_managers(self, league_id):
        daten = self._get("/v4/leagues/" + str(league_id) + "/ranking")
        if not daten:
            return []
        manager = []
        for eintrag in daten.get("us", []):
            manager.append({
                "id": str(eintrag.get("i")),
                "name": eintrag.get("n"),
                "punkte": eintrag.get("sp", 0),
                "teamwert": eintrag.get("tv", 0),
            })
        return manager

    # ------------------------------------------------------------------
    # Kader
    # ------------------------------------------------------------------
    def get_squad(self, league_id, manager_id):
        pfad = ("/v4/leagues/" + str(league_id) +
                "/managers/" + str(manager_id) + "/squad")
        daten = self._get(pfad)
        if not daten:
            return []
        return daten.get("it", daten.get("players", []))

    # ------------------------------------------------------------------
    # Realisierter Gewinn ueber das Feld prft
    # ------------------------------------------------------------------
    def get_realized_profit(self, league_id, manager_id):
        """Sucht das Feld prft in den Manager-Endpunkten.

        Rueckgabe: (wert, quelle). Wert ist None, wenn nichts gefunden wurde.
        """
        pfade = [
            "/v4/leagues/{L}/managers/{M}/dashboard",
            "/v4/leagues/{L}/managers/{M}/profile",
            "/v4/leagues/{L}/managers/{M}/performance",
            "/v4/leagues/{L}/managers/{M}",
            "/v4/leagues/{L}/users/{M}/dashboard",
            "/v4/leagues/{L}/users/{M}/profile",
            "/v4/leagues/{L}/users/{M}/performance",
            "/v4/leagues/{L}/managers/{M}/squad",
        ]
        for vorlage in pfade:
            pfad = vorlage.replace("{L}", str(league_id)).replace("{M}", str(manager_id))
            daten = self._get(pfad)
            if daten is None:
                continue
            wert = self._finde_feld(daten, "prft")
            if wert is not None:
                return wert, pfad
        return None, None

    def _finde_feld(self, objekt, feldname):
        """Sucht rekursiv nach einem Feld und gibt den ersten Zahlenwert zurueck."""
        if isinstance(objekt, dict):
            if feldname in objekt:
                wert = objekt[feldname]
                if isinstance(wert, (int, float)):
                    return wert
            for wert in objekt.values():
                treffer = self._finde_feld(wert, feldname)
                if treffer is not None:
                    return treffer
        elif isinstance(objekt, list):
            for eintrag in objekt:
                treffer = self._finde_feld(eintrag, feldname)
                if treffer is not None:
                    return treffer
        return None

    # ------------------------------------------------------------------
    # Exploration (zur Kontrolle)
    # ------------------------------------------------------------------
    def explore_manager(self, league_id, manager_id):
        endpunkte = [
            "squad", "performance", "dashboard", "profile", "stats",
            "transfers", "activities", "feed", "teamcenter", "lineup",
            "budget", "matchdays", "season", "points", "history",
            "achievements",
        ]
        ergebnis = {}
        for endpunkt in endpunkte:
            for basis in ["managers", "users"]:
                pfad = ("/v4/leagues/" + str(league_id) + "/" + basis + "/" +
                        str(manager_id) + "/" + endpunkt)
                daten = self._get(pfad)
                if daten is not None:
                    ergebnis[pfad] = daten
        return ergebnis
