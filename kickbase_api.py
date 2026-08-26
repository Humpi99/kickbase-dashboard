"""
Kickbase API Client
Dieses Modul kommuniziert mit der Kickbase API (inoffiziell).
"""

import requests


class KickbaseAPI:
    """Klasse zur Kommunikation mit der Kickbase API."""

    def __init__(self):
        # Basis-URL der Kickbase API
        self.base_url = "https://api.kickbase.com"
        # Token wird nach dem Login gesetzt
        self.token = None

    def _headers(self):
        """Erstellt die HTTP-Header mit dem Auth-Token."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def login(self, email, password):
        """
        Meldet sich bei Kickbase an.
        Gibt User-Daten und eine Liste der Ligen zurück.
        """
        url = f"{self.base_url}/user/login"
        data = {
            "email": email,
            "password": password,
            "ext": False
        }

        response = requests.post(url, json=data)

        if response.status_code == 200:
            result = response.json()
            # Token speichern für zukünftige Anfragen
            self.token = result.get("token")
            return result
        elif response.status_code == 401:
            raise Exception("Login fehlgeschlagen: E-Mail oder Passwort falsch.")
        else:
            raise Exception(f"Login fehlgeschlagen (Status {response.status_code})")

    def get_league_stats(self, league_id):
        """Holt die Liga-Statistiken (Ranking aller Manager)."""
        url = f"{self.base_url}/v4/leagues/{league_id}/stats"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Liga-Stats konnten nicht geladen werden (Status {response.status_code})")

    def get_user_players(self, league_id, user_id, match_day=0):
        """Holt alle Spieler eines bestimmten Managers."""
        url = f"{self.base_url}/v4/leagues/{league_id}/users/{user_id}/players?matchDay={match_day}"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Spieler konnten nicht geladen werden (Status {response.status_code})")

    def get_lineup(self, league_id):
        """Holt die aktuelle Aufstellung (nur eigener Account)."""
        url = f"{self.base_url}/v4/leagues/{league_id}/lineup/overview"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Aufstellung konnte nicht geladen werden (Status {response.status_code})")

    def get_market(self, league_id):
        """Holt den aktuellen Transfermarkt der Liga."""
        url = f"{self.base_url}/v4/leagues/{league_id}/market"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Transfermarkt konnte nicht geladen werden (Status {response.status_code})")

    def get_league_feed(self, league_id, start=0):
        """Holt den Liga-Feed (Aktivitäten wie Transfers etc.)."""
        url = f"{self.base_url}/v4/leagues/{league_id}/feed?start={start}"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Liga-Feed konnte nicht geladen werden (Status {response.status_code})")

    def get_user_feed(self, league_id, user_id, start=0):
        """Holt den Feed eines bestimmten Users (seine Transferhistorie)."""
        url = f"{self.base_url}/v4/leagues/{league_id}/users/{user_id}/feed?start={start}"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"User-Feed konnte nicht geladen werden (Status {response.status_code})")

    def get_league_me(self, league_id):
        """Holt eigene Liga-Daten (Budget, Kaderwert, Punkte)."""
        url = f"{self.base_url}/v4/leagues/{league_id}/me"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Eigene Daten konnten nicht geladen werden (Status {response.status_code})")

    def get_user_profile(self, league_id, user_id):
        """Holt das Profil eines Managers in der Liga."""
        url = f"{self.base_url}/v4/leagues/{league_id}/users/{user_id}/profile"
        response = requests.get(url, headers=self._headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"User-Profil konnte nicht geladen werden (Status {response.status_code})")