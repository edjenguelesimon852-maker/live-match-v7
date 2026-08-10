from flask import Flask, jsonify, request
from entitysport import EntitySportClient, EntitySportError

from datetime import datetime, timezone
import os


app = Flask(__name__)


# ============================================================
# OUTILS TEMPORELS
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    if isinstance(value, (int, float)):

        try:

            # secondes
            if value > 10_000_000_000:
                value = value / 1000

            return datetime.fromtimestamp(
                value,
                timezone.utc
            )

        except Exception:
            return None

    if isinstance(value, str):

        try:

            text = value.strip()

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            dt = datetime.fromisoformat(text)

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt.astimezone(timezone.utc)

        except Exception:
            return None

    return None


def freshness_score_from_timestamp(timestamp):

    """
    IMPORTANT :

    Cette fonction calcule la fraîcheur uniquement si nous
    connaissons réellement le timestamp fournisseur.

    Elle ne considère PAS l'heure de réception Railway comme
    l'heure de mise à jour des statistiques.
    """

    dt = parse_datetime(timestamp)

    if dt is None:

        return {
            "score": None,
            "age_seconds": None,
            "known": False
        }

    now = datetime.now(timezone.utc)

    age = (
        now - dt
    ).total_seconds()

    # Evite un timestamp futur aberrant
    if age < 0:
        age = 0

    if age <= 15:
        score = 100

    elif age <= 30:
        score = 90

    elif age <= 60:
        score = 75

    elif age <= 120:
        score = 50

    else:
        score = 20

    return {
        "score": score,
        "age_seconds": round(age, 1),
        "known": True
    }


# ============================================================
# RECHERCHE GENERIQUE D'UNE VALEUR
# ============================================================

def find_first(obj, keys):

    if isinstance(obj, dict):

        for key in keys:

            if key in obj:

                value = obj[key]

                if value is not None:
                    return value

        for value in obj.values():

            found = find_first(
                value,
                keys
            )

            if found is not None:
                return found

    elif isinstance(obj, list):

        for item in obj:

            found = find_first(
                item,
                keys
            )

            if found is not None:
                return found

    return None


# ============================================================
# NORMALISATION D'UN MATCH
# ============================================================

def normalize_match(match):

    if not isinstance(match, dict):

        return {
            "raw": match
        }

    match_id = find_first(
        match,
        [
            "mid",
            "match_id",
            "id"
        ]
    )

    status = find_first(
        match,
        [
            "status",
            "match_status",
            "state"
        ]
    )

    minute = find_first(
        match,
        [
            "minute",
            "min",
            "match_minute",
            "current_minute"
        ]
    )

    period = find_first(
        match,
        [
            "period",
            "half",
            "current_period"
        ]
    )

    start_time = find_first(
        match,
        [
            "starting_at",
            "start_time",
            "starttime",
            "date_start",
            "timestamp"
        ]
    )

    updated_at = find_first(
        match,
        [
            "updated_at",
            "updated",
            "last_updated",
            "last_update",
            "update_time",
            "modified_at"
        ]
    )

    home_team = find_first(
        match,
        [
            "home_team",
            "home",
            "hometeam"
        ]
    )

    away_team = find_first(
        match,
        [
            "away_team",
            "away",
            "awayteam"
        ]
    )

    score = find_first(
        match,
        [
            "score",
            "scores",
            "result"
        ]
    )

    return {

        "match_id":
            match_id,

        "status":
            status,

        "minute":
            minute,

        "period":
            period,

        "start_time":
            start_time,

        "provider_updated_at":
            updated_at,

        "home_team":
            home_team,

        "away_team":
            away_team,

        "score":
            score,

        "raw":
            match
    }


# ============================================================
# EXTRACTION DE LISTE DE MATCHS
# ============================================================

def extract_matches(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    response = data.get(
        "response"
    )

    if isinstance(response, list):
        return response

    if isinstance(response, dict):

        for key in [
            "items",
            "matches",
            "data",
            "results"
        ]:

            value = response.get(key)

            if isinstance(value, list):
                return value

    for key in [
        "matches",
        "data",
        "results",
        "items"
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

    return []


# ============================================================
# CONSTRUCTION DU SNAPSHOT
# ============================================================

def build_snapshot(api_result):

    collected_at = api_result.get(
        "collected_at"
    )

    raw_data = api_result.get(
        "data"
    )

    matches = extract_matches(
        raw_data
    )

    normalized = []

    for match in matches:

        normalized.append(
            normalize_match(match)
        )

    # --------------------------------------------------------
    # Recherche d'un timestamp fournisseur global
    # --------------------------------------------------------

    provider_timestamp = find_first(
        raw_data,
        [
            "updated_at",
            "last_updated",
            "last_update",
            "update_time",
            "modified_at"
        ]
    )

    freshness = freshness_score_from_timestamp(
        provider_timestamp
    )

    # --------------------------------------------------------
    # Qualité temporelle
    # --------------------------------------------------------

    matches_with_time = 0

    for match in normalized:

        if (
            match.get("minute") is not None
            or
            match.get("provider_updated_at") is not None
        ):
            matches_with_time += 1

    if not normalized:

        temporal_consistency = 0

    elif matches_with_time == len(normalized):

        temporal_consistency = 100

    elif matches_with_time > 0:

        temporal_consistency = round(
            (
                matches_with_time
                /
                len(normalized)
            ) * 100
        )

    else:

        temporal_consistency = 40

    # --------------------------------------------------------
    # Data quality
    # --------------------------------------------------------

    data_quality = calculate_data_quality(
        normalized,
        freshness,
        temporal_consistency
    )

    return {

        "robot":
            "LIVE MATCH ANALYST PRO V7",

        "status":
            "LIVE_DATA_RECEIVED",

        "collected_at":
            collected_at,

        "provider_updated_at":
            provider_timestamp,

        "freshness":
            freshness,

        "temporal_consistency":
            temporal_consistency,

        "data_quality":
            data_quality,

        "latency_ms":
            api_result.get(
                "latency_ms"
            ),

        "http_status":
            api_result.get(
                "http_status"
            ),

        "api_status":
            api_result.get(
                "api_status"
            ),

        "match_count":
            len(normalized),

        "matches":
            normalized,

        "raw_data":
            raw_data
    }


# ============================================================
# SCORE QUALITE
# ============================================================

def calculate_data_quality(
    matches,
    freshness,
    temporal_consistency
):

    if not matches:
        return 0

    # Fractions de données utiles
    ids = sum(
        1
        for m in matches
        if m.get("match_id") is not None
    )

    statuses = sum(
        1
        for m in matches
        if m.get("status") is not None
    )

    minutes = sum(
        1
        for m in matches
        if m.get("minute") is not None
    )

    scores = sum(
        1
        for m in matches
        if m.get("score") is not None
    )

    n = len(matches)

    identity_quality = (
        (ids / n) * 100
    )

    status_quality = (
        (statuses / n) * 100
    )

    minute_quality = (
        (minutes / n) * 100
    )

    score_quality = (
        (scores / n) * 100
    )

    freshness_value = (
        freshness["score"]
        if freshness["known"]
        else 50
    )

    quality = (

        identity_quality * 0.20

        +

        status_quality * 0.15

        +

        minute_quality * 0.20

        +

        score_quality * 0.15

        +

        freshness_value * 0.15

        +

        temporal_consistency * 0.15

    )

    return round(
        max(
            0,
            min(
                100,
                quality
            )
        )
    )


# ============================================================
# PAGE ACCUEIL
# ============================================================

@app.get("/")
def home():

    return jsonify({

        "robot":
            "LIVE MATCH ANALYST PRO V7",

        "status":
            "ONLINE",

        "engine":
            "Entity Sport Collector",

        "version":
            "V7.1",

        "endpoints":
            [
                "/",
                "/health",
                "/live",
                "/upcoming",
                "/match/<match_id>",
                "/match/<match_id>/stats",
                "/match/<match_id>/events"
            ],

        "message":
            "API collector actif"
    })


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return jsonify({

        "status":
            "ok",

        "robot":
            "LIVE MATCH ANALYST PRO V7",

        "time_utc":
            datetime.now(
                timezone.utc
            ).isoformat()
    })


# ============================================================
# LIVE
# ============================================================

@app.get("/live")
def live():

    try:

        client = EntitySportClient()

        result = client.live_matches()

        snapshot = build_snapshot(
            result
        )

        # ----------------------------------------------------
        # Par défaut on ne renvoie pas le raw complet.
        #
        # /live?raw=1
        # permet de le récupérer.
        # ----------------------------------------------------

        include_raw = (
            request.args.get(
                "raw",
                "0"
            ).lower()
            in [
                "1",
                "true",
                "yes"
            ]
        )

        if not include_raw:

            snapshot.pop(
                "raw_data",
                None
            )

            for match in snapshot["matches"]:

                # On garde le raw uniquement sur demande
                match.pop(
                    "raw",
                    None
                )

        return jsonify(
            snapshot
        )

    except EntitySportError as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "LIVE_DATA_ERROR",

            "error":
                str(error)

        }), 502

    except Exception as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "INTERNAL_ERROR",

            "error":
                str(error)

        }), 500


# ============================================================
# UPCOMING
# ============================================================

@app.get("/upcoming")
def upcoming():

    try:

        client = EntitySportClient()

        result = client.upcoming_matches()

        snapshot = build_snapshot(
            result
        )

        snapshot["status"] = (
            "UPCOMING_DATA_RECEIVED"
        )

        snapshot.pop(
            "raw_data",
            None
        )

        for match in snapshot["matches"]:
            match.pop(
                "raw",
                None
            )

        return jsonify(
            snapshot
        )

    except EntitySportError as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "UPCOMING_DATA_ERROR",

            "error":
                str(error)

        }), 502

    except Exception as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "INTERNAL_ERROR",

            "error":
                str(error)

        }), 500


# ============================================================
# MATCH INDIVIDUEL
# ============================================================

@app.get("/match/<match_id>")
def match_info(match_id):

    try:

        client = EntitySportClient()

        result = client.match_info(
            match_id
        )

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "MATCH_DATA_RECEIVED",

            "match_id":
                match_id,

            "collected_at":
                result.get(
                    "collected_at"
                ),

            "latency_ms":
                result.get(
                    "latency_ms"
                ),

            "data":
                result.get(
                    "data"
                )
        })

    except EntitySportError as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "MATCH_DATA_ERROR",

            "match_id":
                match_id,

            "error":
                str(error)

        }), 502


# ============================================================
# STATISTIQUES D'UN MATCH
# ============================================================

@app.get("/match/<match_id>/stats")
def match_stats(match_id):

    try:

        client = EntitySportClient()

        result = client.match_stats(
            match_id
        )

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "MATCH_STATS_RECEIVED",

            "match_id":
                match_id,

            "collected_at":
                result.get(
                    "collected_at"
                ),

            "latency_ms":
                result.get(
                    "latency_ms"
                ),

            "data":
                result.get(
                    "data"
                )
        })

    except EntitySportError as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "MATCH_STATS_ERROR",

            "match_id":
                match_id,

            "error":
                str(error)

        }), 502


# ============================================================
# EVENEMENTS D'UN MATCH
# ============================================================

@app.get("/match/<match_id>/events")
def match_events(match_id):

    try:

        client = EntitySportClient()

        result = client.match_events(
            match_id
        )

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "MATCH_EVENTS_RECEIVED",

            "match_id":
                match_id,

            "collected_at":
                result.get(
                    "collected_at"
                ),

            "latency_ms":
                result.get(
                    "latency_ms"
                ),

            "data":
                result.get(
                    "data"
                )
        })

    except EntitySportError as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "MATCH_EVENTS_ERROR",

            "match_id":
                match_id,

            "error":
                str(error)

        }), 502


# ============================================================
# DEMARRAGE LOCAL
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
            )
