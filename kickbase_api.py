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
        """Header für Anfragen an die API."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    @staticmethod
    def _error_text(response):
        """Kürzt die Serverantwort für eine Fehlermeldung."""
        text = response.text.strip()

        if not text:
            return "Keine zusätzliche Servermeldung"

        return text[:500]

    def login(self, email, password):
        """Meldet den Benutzer bei der Kickbase-v4-API an."""
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
                    "Kickbase hat keine gültige JSON-Antwort gesendet."
                ) from error

            self.token = (
                result.get("tkn")
                or result.get("token")
                or result.get("accessToken")
            )

            if not self.token:
                raise Exception(
                    "Der Login wurde angenommen, aber Kickbase hat "
                    "keinen Zugriffstoken zurückgegeben."
                )

            self.session.headers.update(self._headers())
            return result

        if response.status_code in (400, 401, 403):
            raise Exception(
                "Anmeldung abgelehnt. Bitte prüfe deine "
                "Kickbase-E-Mail-Adresse und dein Passwort."
            )

        raise Exception(
            f"Anmeldung fehlgeschlagen (Status {response.status_code}). "
            f"Servermeldung: {self._error_text(response)}"
        )

    def _get_candidates(self, paths, params=None):
        """
        Probiert mehrere mögliche API-Pfade.

        Das ist hilfreich, weil die inoffizielle Dokumentation
        nicht bei allen Endpunkten vollständig ist.
        """
        errors = []

        for path in paths:
            url = f"{self.base_url}{path}"

            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._headers(),
                    timeout=30,
                )
            except requests.exceptions.RequestException as error:
                errors.append(f"{path}: {error}")
                continue

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    errors.append(f"{path}: ungültige JSON-Antwort")
                    continue

            if response.status_code == 401:
                raise Exception(
                    "Deine Anmeldung ist nicht mehr gültig. "
                    "Bitte melde dich erneut an."
                )

            errors.append(
                f"{path}: Status {response.status_code}"
            )

        raise Exception(
            "Keiner der bekannten API-Endpunkte hat funktioniert. "
            + " | ".join(errors)
        )

    def get_leagues(self):
        """Versucht, die Ligen des angemeldeten Accounts separat zu laden."""
        return self._get_candidates(
            [
                "/v4/leagues",
                "/v4/leagues/selection",
                "/v4/user/leagues",
                "/leagues",
            ]
        )

    def get_league_users(self, league_id):
        """Lädt die Manager einer Liga."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/users",
                f"/v4/leagues/{league_id}/stats",
                f"/leagues/{league_id}/users",
                f"/leagues/{league_id}/stats",
            ]
        )

    def get_league_stats(self, league_id):
        """Lädt die Liga-Statistiken."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/stats",
                f"/leagues/{league_id}/stats",
            ]
        )

    def get_user_players(self, league_id, user_id, match_day=0):
        """Lädt den Kader eines Managers."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/users/{user_id}/players",
                f"/leagues/{league_id}/users/{user_id}/players",
            ],
            params={"matchDay": match_day},
        )

    def get_lineup(self, league_id):
        """Lädt die aktuelle eigene Aufstellung."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/lineup/overview",
                f"/v4/leagues/{league_id}/lineup",
                f"/leagues/{league_id}/lineup",
            ]
        )

    def get_market(self, league_id):
        """Lädt den Transfermarkt."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/market",
                f"/leagues/{league_id}/market",
            ]
        )

    def get_league_feed(self, league_id, start=0):
        """Lädt den Liga-Feed."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/feed",
                f"/leagues/{league_id}/feed",
            ],
            params={"start": start},
        )

    def get_user_feed(self, league_id, user_id, start=0):
        """Versucht, den Feed eines Managers zu laden."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/users/{user_id}/feed",
                f"/leagues/{league_id}/users/{user_id}/feed",
            ],
            params={"start": start},
        )

    def get_league_me(self, league_id):
        """Lädt die eigenen Finanzdaten."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/me",
                f"/leagues/{league_id}/me",
            ]
        )

    def get_user_profile(self, league_id, user_id):
        """Lädt das Profil eines Managers."""
        return self._get_candidates(
            [
                f"/v4/leagues/{league_id}/users/{user_id}/profile",
                f"/leagues/{league_id}/users/{user_id}/profile",
            ]
        )
