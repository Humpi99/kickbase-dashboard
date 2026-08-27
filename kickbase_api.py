"""
Einfacher Client für die inoffizielle Kickbase-v4-API.

Wichtig:
Die API ist nicht offiziell und kann sich verändern.
"""

import requests


class KickbaseAPI:
    """Kommunikation mit der Kickbase-v4-API."""

    def __init__(self):
        self.base_url = "https://api.kickbase.com"
        self.token = None

        # Eine Session behält Header und Cookies während der Sitzung.
        self.session = requests.Session()

    def _headers(self):
        """Erstellt die Header für authentifizierte Anfragen."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    @staticmethod
    def _response_text(response):
        """Kürzt die Serverantwort für Fehlermeldungen."""
        text = response.text.strip()

        if not text:
            return "Keine zusätzliche Servermeldung"

        return text[:500]

    def login(self, email, password):
        """
        Meldet den Benutzer bei Kickbase an.

        Die aktuelle v4-API erwartet:
        em   = E-Mail
        pass = Passwort
        loy  = Login-Option
        rep  = Geräteinformationen
        """
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
                timeout=20,
            )
        except requests.exceptions.RequestException as error:
            raise Exception(
                f"Kickbase ist momentan nicht erreichbar: {error}"
            ) from error

        if response.status_code == 200:
            try:
                result = response.json()
            except ValueError as error:
                raise Exception(
                    "Kickbase hat keine gültige JSON-Antwort gesendet."
                ) from error

            # In v4 heißt der Token normalerweise „tkn“.
            self.token = result.get("tkn") or result.get("token")

            if not self.token:
                raise Exception(
                    "Die Anmeldung war erfolgreich, aber es wurde "
                    "kein Zugriffstoken zurückgegeben."
                )

            # Token dauerhaft für weitere Session-Anfragen setzen.
            self.session.headers.update(self._headers())

            return result

        if response.status_code in (400, 401, 403):
            raise Exception(
                "Anmeldung abgelehnt. Bitte prüfe deine "
                "Kickbase-E-Mail-Adresse und dein Passwort."
            )

        raise Exception(
            f"Anmeldung fehlgeschlagen (Status {response.status_code}). "
            f"Servermeldung: {self._response_text(response)}"
        )

    def _get(self, path, params=None):
        """Führt eine authentifizierte GET-Anfrage aus."""
        if not self.token:
            raise Exception("Du bist nicht bei Kickbase angemeldet.")

        url = f"{self.base_url}{path}"

        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=20,
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
                    "Kickbase hat keine gültige JSON-Antwort gesendet."
                ) from error

        if response.status_code == 401:
            raise Exception(
                "Deine Anmeldung ist nicht mehr gültig. "
                "Bitte lade die App neu und melde dich erneut an."
            )

        if response.status_code == 403:
            raise Exception(
                "Für diese Daten besitzt dein Account keine Berechtigung."
            )

        if response.status_code == 404:
            raise Exception(
                f"Der Kickbase-Endpunkt wurde nicht gefunden: {path}"
            )

        raise Exception(
            f"Anfrage fehlgeschlagen (Status {response.status_code}). "
            f"Servermeldung: {self._response_text(response)}"
        )

    def get_league_stats(self, league_id):
        """Lädt Ranking und Statistiken der Liga."""
        return self._get(f"/v4/leagues/{league_id}/stats")

    def get_user_players(self, league_id, user_id, match_day=0):
        """Lädt den Kader eines Managers."""
        return self._get(
            f"/v4/leagues/{league_id}/users/{user_id}/players",
            params={"matchDay": match_day},
        )

    def get_lineup(self, league_id):
        """Lädt die eigene aktuelle Aufstellung."""
        return self._get(
            f"/v4/leagues/{league_id}/lineup/overview"
        )

    def get_market(self, league_id):
        """Lädt den Transfermarkt der Liga."""
        return self._get(
            f"/v4/leagues/{league_id}/market"
        )

    def get_league_feed(self, league_id, start=0):
        """Lädt eine Seite des Liga-Feeds."""
        return self._get(
            f"/v4/leagues/{league_id}/feed",
            params={"start": start},
        )

    def get_user_feed(self, league_id, user_id, start=0):
        """Versucht, den Feed eines bestimmten Managers zu laden."""
        return self._get(
            f"/v4/leagues/{league_id}/users/{user_id}/feed",
            params={"start": start},
        )

    def get_league_me(self, league_id):
        """Lädt eigene Finanz- und Ligaangaben."""
        return self._get(
            f"/v4/leagues/{league_id}/me"
        )

    def get_user_profile(self, league_id, user_id):
        """Lädt das Profil eines Managers."""
        return self._get(
            f"/v4/leagues/{league_id}/users/{user_id}/profile"
        )
