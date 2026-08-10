import os
import time
import requests
from datetime import datetime, timezone


BASE_URL = os.getenv(
    "ENTITYSPORT_BASE_URL",
    "https://restapi.entitysport.com/v2"
)

REQUEST_TIMEOUT = int(
    os.getenv("ENTITYSPORT_TIMEOUT", "15")
)


class EntitySportError(Exception):
    pass


class EntitySportClient:

    def __init__(self):

        self.token = os.getenv("ENTITYSPORT_TOKEN")

        if not self.token:
            raise EntitySportError(
                "ENTITYSPORT_TOKEN n'est pas configuré sur Railway."
            )

        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "LIVE-MATCH-ANALYST-V7/1.0"
        })

    # ---------------------------------------------------------
    # UTILITAIRE REQUETE
    # ---------------------------------------------------------

    def request(self, endpoint, params=None):

        if params is None:
            params = {}

        params = dict(params)

        # Token uniquement côté serveur
        params["token"] = self.token

        started = time.monotonic()

        try:

            response = self.session.get(
                f"{BASE_URL}/{endpoint.lstrip('/')}",
                params=params,
                timeout=REQUEST_TIMEOUT
            )

        except requests.RequestException as error:

            raise EntitySportError(
                f"Erreur réseau Entity Sport: {error}"
            )

        latency = round(
            (time.monotonic() - started) * 1000,
            1
        )

        try:
            data = response.json()
        except ValueError:

            raise EntitySportError(
                f"Réponse Entity Sport non JSON "
                f"(HTTP {response.status_code})"
            )

        if response.status_code >= 400:

            raise EntitySportError(
                self._safe_error_message(
                    response.status_code,
                    data
                )
            )

        # Entity Sport peut retourner un status applicatif
        api_status = data.get("status")

        if api_status in (
            "unauthorized",
            "accessdenied",
            "error",
            "invalid"
        ):

            raise EntitySportError(
                f"Entity Sport status: {api_status}"
            )

        return {
            "endpoint": endpoint,
            "latency_ms": latency,
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "http_status": response.status_code,
            "api_status": api_status,
            "data": data
        }

    # ---------------------------------------------------------
    # MESSAGE ERREUR SANS TOKEN
    # ---------------------------------------------------------

    def _safe_error_message(self, status_code, data):

        message = ""

        if isinstance(data, dict):

            message = (
                data.get("message")
                or data.get("error")
                or data.get("status")
                or ""
            )

        # Protection supplémentaire :
        # ne jamais renvoyer le token dans une erreur
        if self.token and self.token in message:
            message = message.replace(
                self.token,
                "***TOKEN_MASQUE***"
            )

        return (
            f"Entity Sport HTTP {status_code}"
            + (f": {message}" if message else "")
        )

    # ---------------------------------------------------------
    # MATCHS LIVE
    # ---------------------------------------------------------

    def live_matches(self):

        params = {
            "status": "live"
        }

        # Entity Sport indique que le paramètre start
        # peut servir à obtenir les données live les plus récentes.
        #
        # Il est désactivable si ton abonnement/endpoint ne l'accepte pas.
        use_start = os.getenv(
            "ENTITYSPORT_USE_START",
            "true"
        ).lower() == "true"

        if use_start:
            params["start"] = int(time.time())

        try:

            return self.request(
                "matches",
                params
            )

        except EntitySportError:

            # Fallback : certains environnements/anciens
            # endpoints peuvent ne pas accepter "start".
            if "start" in params:

                params.pop("start")

                return self.request(
                    "matches",
                    params
                )

            raise

    # ---------------------------------------------------------
    # MATCHS A VENIR
    # ---------------------------------------------------------

    def upcoming_matches(self):

        return self.request(
            "matches",
            {
                "status": "upcoming"
            }
        )

    # ---------------------------------------------------------
    # TOUS LES MATCHS D'UNE PERIODE
    # ---------------------------------------------------------

    def matches(self, params=None):

        return self.request(
            "matches",
            params or {}
        )

    # ---------------------------------------------------------
    # DETAILS D'UN MATCH
    # ---------------------------------------------------------

    def match_info(self, match_id):

        if not match_id:
            raise EntitySportError(
                "match_id manquant."
            )

        return self.request(
            f"matches/{match_id}"
        )

    # ---------------------------------------------------------
    # STATISTIQUES D'UN MATCH
    #
    # On laisse l'endpoint configurable parce que la disponibilité
    # dépend du produit/plan Entity Sport utilisé.
    # ---------------------------------------------------------

    def match_stats(self, match_id):

        endpoint = os.getenv(
            "ENTITYSPORT_STATS_ENDPOINT",
            "matches/{match_id}/stats"
        ).format(
            match_id=match_id
        )

        return self.request(endpoint)

    # ---------------------------------------------------------
    # EVENEMENTS D'UN MATCH
    # ---------------------------------------------------------

    def match_events(self, match_id):

        endpoint = os.getenv(
            "ENTITYSPORT_EVENTS_ENDPOINT",
            "matches/{match_id}/events"
        ).format(
            match_id=match_id
        )

        return self.request(endpoint)
