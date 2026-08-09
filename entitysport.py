import os
import time
import requests
from datetime import datetime, timezone


BASE_URL = "https://restapi.entitysport.com/v2"


class EntitySportClient:

    def __init__(self):
        self.token = os.getenv("ENTITYSPORT_TOKEN")

        if not self.token:
            raise RuntimeError(
                "ENTITYSPORT_TOKEN n'est pas configuré."
            )

    def request(self, endpoint, params=None):

        if params is None:
            params = {}

        params["token"] = self.token

        started = time.time()

        response = requests.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            timeout=15
        )

        latency = round(
            (time.time() - started) * 1000
        )

        response.raise_for_status()

        data = response.json()

        return {
            "latency_ms": latency,
            "received_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "data": data
        }

    def live_matches(self):

        return self.request(
            "matches",
            {
                "status": "live"
            }
  )
      
