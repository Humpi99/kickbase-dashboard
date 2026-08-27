"""
Client für die inoffizielle Kickbase-v4-API.
"""

import requests


class KickbaseAPI:
    """Kommunikation mit der Kickbase API."""

    def __init__(self):
        self.base_url = "https://api.kickbase.com"
        self.token = None
        self.session = requests.Session()

    def _headers(self):
        """Erstellt die Header für Kickbase-Anfragen."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def login(self, email, password):
        """Meldet den Benutzer bei Kickbase an."""
        url = f"{self.base_url}/v4/user/login"

        body = {
            "em": email.strip(),
            "pass": password,
            "loy": False,
            "rep": {},
        }

        try:
            response = self.session.post(
                url,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
        except requests.exceptions.RequestException as error:
            raise Exception(
                f"Kickbase ist nicht erreichbar: {error}"
            ) from error

        if response.status_code == 200:
            try:
                result = response.json()
            except ValueError as error:
                raise Exception(
                    "Kickbase hat keine gültige Antwort gesendet."
                ) from error

            self.token = (
                result.get("tkn")
                or result.get("token")
                or result.get("accessToken")
            )

            if not self.token:
                raise Exception(
                    "Anmeldung erfolgreich, aber kein Token gefunden."
                )

            return result

        if response.status_code in (400, 401, 403):
            raise Exception(
                "Anmeldung abgelehnt. Bitte E-Mail und Passwort prüfen."
            )

        raise Exception(
            f"Anmeldung fehlgeschlagen. Status: {response.status_code}"
        )

    def get(self, path, params=None):
        """Führt eine authentifizierte GET-Anfrage aus."""
        if not self.token:
            raise Exception("Du bist nicht angemeldet.")

        url = f"{self.base_url}{path}"

        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=30,
            )
        except requests.exceptions.RequestException as error:
            raise Exception(
                f"Kickbase-Anfrage fehlgeschlagen: {error}"
            ) from error

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as error:
                raise Exception(
                    f"{path}: keine gültige JSON-Antwort"
                ) from error

        if response.status_code == 401:
            raise Exception(
                "Anmeldung abgelaufen. Bitte neu anmelden."
            )

        raise Exception(
            f"{path}: Status {response.status_code}"
        )

    def try_paths(self, paths, params=None):
        """Testet mehrere Endpunkte und sammelt alle Treffer."""
        results = []
        errors = []

        for path in paths:
            try:
                data = self.get(path, params=params)

                results.append(
                    {
                        "path": path,
                        "data": data,
                    }
                )
            except Exception as error:
                errors.append(str(error))

        return results, errors

    def get_ranking(self, league_id):
        """Lädt das Liga-Ranking mit den Managern."""
        paths = [
            f"/v4/leagues/{league_id}/ranking",
        ]

        return self.try_paths(paths)

    def get_manager_squad(self, league_id, manager_id):
        """Lädt den Kader eines bestimmten Managers."""
        path = (
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/squad"
        )

        return self.get(path)

    def explore_manager(self, league_id, manager_id):
        """
        Probiert alle bekannten Manager-Endpunkte durch.

        Dient dazu, verfügbare Informationen zu finden.
        """
        base = f"/v4/leagues/{league_id}/managers/{manager_id}"

        paths = [
            base,
            f"{base}/squad",
            f"{base}/performance",
            f"{base}/dashboard",
            f"{base}/profile",
            f"{base}/stats",
            f"{base}/transfers",
            f"{base}/activities",
            f"{base}/activitiesFeed",
            f"{base}/feed",
            f"{base}/teamcenter",
            f"{base}/lineup",
            f"{base}/budget",
            f"{base}/matchdays",
            f"{base}/season",
            f"{base}/points",
            f"{base}/history",
            f"{base}/achievements",
            f"/v4/leagues/{league_id}/users/{manager_id}",
            f"/v4/leagues/{league_id}/users/{manager_id}/profile",
            f"/v4/leagues/{league_id}/users/{manager_id}/stats",
        ]

        return self.try_paths(paths)

    def get_manager_transfers(self, league_id, manager_id):
        """Lädt die Transferhistorie eines Managers."""
        paths = [
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/transfers",
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/activities",
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/performance",
            f"/v4/leagues/{league_id}"
            f"/managers/{manager_id}/dashboard",
        ]

        return self.try_paths(paths)

    def get_league_feed(self, league_id, start=0):
        """Lädt eine Seite des Liga-Feeds."""
        paths = [
            f"/v4/leagues/{league_id}/activitiesFeed",
            f"/v4/leagues/{league_id}/activities",
            f"/v4/leagues/{league_id}/feed",
        ]

        return self.try_paths(
            paths,
            params={"start": start, "max": 25},
        )

    def get_market(self, league_id):
        """Lädt den Transfermarkt der Liga."""
        paths = [
            f"/v4/leagues/{league_id}/market",
        ]

        return self.try_paths(paths)
