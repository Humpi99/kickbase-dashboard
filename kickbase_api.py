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
                    "Die Anmeldung war erfolgreich, aber es wurde "
                    "kein Zugriffstoken gefunden."
                )

            return result

        if response.status_code in (400, 401, 403):
            raise Exception(
                "Anmeldung abgelehnt. Bitte prüfe E-Mail und Passwort."
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
                    f"{path} hat keine gültige JSON-Antwort geliefert."
                ) from error

        if response.status_code == 401:
            raise Exception(
                "Die Anmeldung ist abgelaufen. Bitte erneut anmelden."
            )

        raise Exception(
            f"{path}: Status {response.status_code}"
        )

    def try_paths(self, paths, params=None):
        """
        Testet mehrere mögliche Endpunkte.

        Alle erfolgreichen Antworten werden zurückgegeben.
        """
        results = []
        errors = []

        for path in paths:
            try:
                result = self.get(path, params=params)

                results.append(
                    {
                        "path": path,
                        "data": result,
                    }
                )
            except Exception as error:
                errors.append(str(error))

        return results, errors

    def get_league_sources(self, league_id):
        """
        Lädt mögliche Quellen für Liga- und Managerinformationen.
        """
        paths = [
            f"/v4/leagues/{league_id}",
            f"/v4/leagues/{league_id}/info",
            f"/v4/leagues/{league_id}/overview",
            f"/v4/leagues/{league_id}/ranking",
            f"/v4/leagues/{league_id}/dashboard",
            f"/v4/leagues/{league_id}/users",
            f"/v4/leagues/{league_id}/stats",
            f"/leagues/{league_id}",
            f"/leagues/{league_id}/info",
            f"/leagues/{league_id}/ranking",
            f"/leagues/{league_id}/users",
            f"/leagues/{league_id}/stats",
        ]

        return self.try_paths(paths)

    def get_user_players(self, league_id, user_id):
        """Versucht, den Kader eines Managers zu laden."""
        paths = [
            f"/v4/leagues/{league_id}/users/{user_id}/players",
            f"/v4/leagues/{league_id}/user/{user_id}/players",
            f"/v4/leagues/{league_id}/teamcenter/{user_id}",
            f"/leagues/{league_id}/users/{user_id}/players",
        ]

        results, errors = self.try_paths(
            paths,
            params={"matchDay": 0},
        )

        if results:
            return results[0]["data"]

        raise Exception(" | ".join(errors))

    def get_market(self, league_id):
        """Versucht, den Transfermarkt zu laden."""
        paths = [
            f"/v4/leagues/{league_id}/market",
            f"/leagues/{league_id}/market",
        ]

        results, errors = self.try_paths(paths)

        if results:
            return results[0]["data"]

        raise Exception(" | ".join(errors))

    def get_league_feed(self, league_id, start=0):
        """Versucht, den Liga-Feed zu laden."""
        paths = [
            f"/v4/leagues/{league_id}/feed",
            f"/leagues/{league_id}/feed",
        ]

        results, errors = self.try_paths(
            paths,
            params={"start": start},
        )

        if results:
            return results[0]["data"]

        raise Exception(" | ".join(errors))

    def get_me(self, league_id):
        """Versucht, die eigenen Finanzdaten zu laden."""
        paths = [
            f"/v4/leagues/{league_id}/me",
            f"/leagues/{league_id}/me",
        ]

        results, errors = self.try_paths(paths)

        if results:
            return results[0]["data"]

        raise Exception(" | ".join(errors))
