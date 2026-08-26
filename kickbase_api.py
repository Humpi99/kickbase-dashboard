"""
Kickbase API Client
Dieses Modul kommuniziert mit der Kickbase API (inoffiziell).
Authentifizierung läuft über Cookie (kkstrauth).
"""

import requests


class KickbaseAPI:
    """Klasse zur Kommunikation mit der Kickbase API."""

    def __init__(self):
        self.base_url = "https://api.kickbase.com"
        self.token = None
        self.session = requests.Session()

    def _headers(self):
        """Erstellt die HTTP-Header mit Cookie-Auth."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if self.token:
            headers["Cookie"] = f"kkstrauth={self.token}"
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, email, password):
        """
        Meldet sich bei Kickbase an.
        Probiert mehrere bekannte Login-Endpunkte.
        """
        # Verschiedene bekannte Pfade versuchen
        endpoints = [
            "/user/login",
            "/v4/user/login",
            "/v4/user/token",
        ]

        data = {
            "email": email,
            "password": password,
            "ext": False
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        last_status = None
        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            try:
                response = self.session.post(url, json=data, headers=headers)
                last_status = response.status_code

                if response.status_code == 200:
                    result = response.json()

                    # Token aus Response JSON holen
                    self.token = result.get("token") or result.get("tkn")

                    # Oder Token aus Set-Cookie Header holen
                    if not self.token:
                        cookies = response.cookies
                        if "kkstrauth" in cookies:
                            self.token = cookies["kkstrauth"]

                    # Auch aus dem Set-Cookie Header direkt
                    if not self.token:
                        set_cookie = response.headers.get("Set-Cookie", "")
                        if "kkstrauth=" in set_cookie:
                            self.token = set_cookie.split("kkstrauth=")[1].split(";")[0]

                    if self.token:
                        return result
                    else:
                        # Kein Token gefunden, aber 200 OK - trotzdem nutzen
                        return result

                elif response.status_code == 401:
                    raise Exception("❌ Login fehlgeschlagen: E-Mail oder Passwort falsch.")

            except requests.exceptions.ConnectionError:
                continue
            except Exception as e:
                if "fehlgeschlagen" in str(e):
                    raise e
                continue

        raise Exception(f"❌ Login fehlgeschlagen - kein Endpunkt erreichbar (letzter Status: {last_status})")

    def _get(self, path):
        """Führt einen GET-Request aus."""
        # Versuche mit und ohne /v4 Prefix
        urls_to_try = [
            f"{self.base_url}/v4{path}",
            f"{self.base_url}{path}",
        ]

        for url in urls_to_try:
            response = self.session.get(url, headers=self._headers())
            if response.status_code == 200:
                return response.json()

        # Wenn nichts klappt, letzten Fehler melden
        raise Exception(f"Anfrage fehlgeschlagen für {path} (Status {response.status_code})")

    def get_league_stats(self, league_id):
        """Holt die Liga-Statistiken (Ranking aller Manager)."""
        return self._get(f"/leagues/{league_id}/stats")

    def get_user_players(self, league_id, user_id, match_day=0):
        """Holt alle Spieler eines bestimmten Managers."""
        return self._get(f"/leagues/{league_id}/users/{user_id}/players?matchDay={match_day}")

    def get_lineup(self, league_id):
        """Holt die aktuelle Aufstellung (nur eigener Account)."""
        return self._get(f"/leagues/{league_id}/lineup/overview")

    def get_market(self, league_id):
        """Holt den aktuellen Transfermarkt der Liga."""
        return self._get(f"/leagues/{league_id}/market")

    def get_league_feed(self, league_id, start=0):
        """Holt den Liga-Feed (Aktivitäten wie Transfers etc.)."""
        return self._get(f"/leagues/{league_id}/feed?start={start}")

    def get_user_feed(self, league_id, user_id, start=0):
        """Holt den Feed eines bestimmten Users (seine Transferhistorie)."""
        return self._get(f"/leagues/{league_id}/users/{user_id}/feed?start={start}")

    def get_league_me(self, league_id):
        """Holt eigene Liga-Daten (Budget, Kaderwert, Punkte)."""
        return self._get(f"/leagues/{league_id}/me")

    def get_user_profile(self, league_id, user_id):
        """Holt das Profil eines Managers in der Liga."""
        return self._get(f"/leagues/{league_id}/users/{user_id}/profile")
