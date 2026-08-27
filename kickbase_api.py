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

    def get_ranking(self, league_id, day_number=None):
        """Lädt das Liga-Ranking mit den Kaderwerten."""
        params = {}

        if day_number is not None:
            params["dayNumber"] = day_number

        paths = [
            f"/v4/leagues/{league_id}/ranking",
        ]

        return self.try_paths(
            paths,
            params=params if params else None,
        )

    def get_squad_candidates(self, league_id, user_id):
        """
        Probiert alle bekannten Pfade für den Kader
        eines Managers durch.

        Der Kader enthält Marktwerte und meistens
        auch den Kaufpreis.
        """
        paths = [
            f"/v4/leagues/{league_id}/managers/{user_id}/squad",
            f"/v4/leagues/{league_id}/users/{user_id}/squad",
            f"/v4/leagues/{league_id}/managers/{user_id}/players",
            f"/v4/leagues/{league_id}/managers/{user_id}",
            f"/v4/leagues/{league_id}/users/{user_id}/profile",
            f"/v4/leagues/{league_id}/users/{user_id}",
            f"/v4/leagues/{league_id}/squad",
            f"/v4/leagues/{league_id}/lineup",
        ]

        return self.try_paths(paths)

    def get_market(self, league_id):
        """Lädt den Transfermarkt."""
        paths = [
            f"/v4/leagues/{league_id}/market",
        ]

        return self.try_paths(paths)

    def get_me(self, league_id):
        """Lädt die eigenen Finanzdaten."""
        paths = [
            f"/v4/leagues/{league_id}/me",
        ]

        results, errors = self.try_paths(paths)

        if results:
            return results[0]["data"]

        raise Exception(" | ".join(errors))
