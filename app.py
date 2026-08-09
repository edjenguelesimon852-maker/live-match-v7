from flask import Flask, jsonify
from entitysport import EntitySportClient
from datetime import datetime, timezone


app = Flask(__name__)


def freshness_score(received_at):

    try:
        received = datetime.fromisoformat(
            received_at.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        age = (
            now - received
        ).total_seconds()

    except Exception:
        return 0, None

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

    return score, round(age, 1)


@app.get("/")
def home():

    return jsonify({
        "robot": "LIVE MATCH ANALYST PRO V7",
        "status": "ONLINE",
        "engine": "Entity Sport Collector",
        "message": "API collector actif"
    })


@app.get("/health")
def health():

    return jsonify({
        "status": "ok"
    })


@app.get("/live")
def live():

    try:

        client = EntitySportClient()

        result = client.live_matches()

        received_at = result["received_at"]

        freshness, age = freshness_score(
            received_at
        )

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "LIVE_DATA_RECEIVED",

            "received_at":
                received_at,

            "data_age_seconds":
                age,

            "freshness":
                freshness,

            "latency_ms":
                result["latency_ms"],

            "raw_data":
                result["data"]

        })

    except Exception as error:

        return jsonify({

            "robot":
                "LIVE MATCH ANALYST PRO V7",

            "status":
                "LIVE_DATA_ERROR",

            "error":
                str(error)

        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000
      )
