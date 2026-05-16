from flask import Flask, jsonify
from vehicle_maintence_scheduler.scheduler import build_schedule
from notification_app_be.priority_inbox import extract_top, sample_feed

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "service": "Backend Assessment API",
        "endpoints": [
            "/api/v1/schedule",
            "/api/v1/priority-inbox"
        ]
    })


@app.route("/api/v1/schedule")
def schedule():
    try:
        results = build_schedule()
        return jsonify({"status": "success", "data": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/v1/priority-inbox")
def priority_inbox():
    top_10 = extract_top(sample_feed, count=10)
    output = []
    for pos, item in enumerate(top_10, 1):
        output.append({
            "rank": pos,
            "id": item.uid,
            "type": item.category,
            "message": item.body,
            "score": item.rank
        })
    return jsonify({"status": "success", "data": output})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
