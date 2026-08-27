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
    """Meldet sich über die aktuelle Kickbase-v4-API an."""

    url = f"{self.base_url}/v4/user/login"

    data = {
        "em": email,
        "pass": password,
        "loy": False,
        "rep": {}
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = self.session.post(
            url,
            json=data,
            headers=headers,
            timeout=20
        )
    except requests.exceptions.RequestException as error:
        raise Exception(f"Kickbase ist nicht erreichbar: {error}")

    if response.status_code == 200:
        result = response.json()

        # In der aktuellen v4-Antwort heißt der Token „tkn“.
        self.token = result.get("tkn") or result.get("token")

        if not self.token:
            raise Exception(
                "Login war erfolgreich, aber die Antwort enthält keinen Token."
            )

        return result

    if response.status_code in (400, 401, 403):
        raise Exception(
            "Login abgelehnt. Bitte E-Mail und Passwort prüfen."
        )

    raise Exception(
        f"Login fehlgeschlagen (Status {response.status_code}): "
        f"{response.text[:300]}"
    )

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
