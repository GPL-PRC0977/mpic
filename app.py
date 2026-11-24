import os
from datetime import datetime
from uuid import UUID

from flask import Flask, jsonify, make_response, render_template, request, send_from_directory

app = Flask(__name__)

# In-memory sample data for prototyping. Replace with a database in production.
barcodes = [
    {"barcode": "8901234567890", "count": 14, "scanned_at": "Nov 17, 2026 10:24:36 AM", "counter": "1004"},
    {"barcode": "8930001112225", "count": 8, "scanned_at": "Nov 17, 2026 10:22:01 AM", "counter": "1001"},
    {"barcode": "8997766554433", "count": 22, "scanned_at": "Nov 17, 2026 10:19:48 AM", "counter": "1003"},
    {"barcode": "8909876543210", "count": 3, "scanned_at": "Nov 17, 2026 10:18:27 AM", "counter": "1006"},
    {"barcode": "8934567890123", "count": 14, "scanned_at": "Nov 17, 2026 10:15:09 AM", "counter": "1002"},
    {"barcode": "8991231231234", "count": 8, "scanned_at": "Nov 17, 2026 10:11:37 AM", "counter": "1004"},
    {"barcode": "8905556667778", "count": 22, "scanned_at": "Nov 17, 2026 10:09:12 AM", "counter": "1005"},
    {"barcode": "8932109876547", "count": 3, "scanned_at": "Nov 17, 2026 10:06:41 AM", "counter": "1001"},
]

activity = [
    {"barcode": row["barcode"], "count": row["count"], "time": row["scanned_at"].split()[-2] + " " + row["scanned_at"].split()[-1]}
    for row in barcodes
]

count_history = [
    {"name": "November 2026 Physical Count", "period": "Nov 17–24, 2026", "status": "In progress", "unique": "1,670", "scans": "3,284", "counters": 6, "updated": "Updated just now"},
    {"name": "October 2026 Physical Count", "period": "Oct 21–25, 2026", "status": "Completed", "unique": "2,146", "scans": "4,098", "counters": 8, "updated": "Completed Oct 25, 2026"},
    {"name": "September 2026 Physical Count", "period": "Sep 16–20, 2026", "status": "Completed", "unique": "2,008", "scans": "3,864", "counters": 7, "updated": "Completed Sep 20, 2026"},
    {"name": "August 2026 Physical Count", "period": "Aug 19–23, 2026", "status": "Completed", "unique": "1,954", "scans": "3,721", "counters": 6, "updated": "Completed Aug 23, 2026"},
    {"name": "July 2026 Physical Count", "period": "Jul 15–19, 2026", "status": "Completed", "unique": "1,889", "scans": "3,510", "counters": 6, "updated": "Completed Jul 19, 2026"},
]
processed_scan_ids = set()
deducted_count = 0


def is_valid_barcode(barcode):
    """Accept any non-empty scanner value; product rules belong in a later review step."""
    return bool(barcode.strip())


def display_scan_time(timestamp):
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%b %d, %Y %I:%M:%S %p")
    except (AttributeError, TypeError, ValueError):
        return datetime.now().strftime("%b %d, %Y %I:%M:%S %p")


@app.get("/")
def dashboard():
    initial_state = {
        "barcodes": barcodes,
        "activity": activity,
        "metrics": {"unique": 1670, "total": 3284, "today": 482, "deducted": deducted_count},
    }
    return render_template("index.html", barcodes=barcodes, activity=activity, initial_state=initial_state)


@app.get("/history")
def history():
    return render_template("history.html", count_history=count_history)


@app.get("/healthz")
def health_check():
    return jsonify({"ok": True})


@app.get("/sw.js")
def service_worker():
    """Serve the worker at the app root so it can control every app route."""
    response = make_response(send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript"))
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.post("/api/scans/sync")
def sync_scans():
    """Accept an offline queue in a single idempotent request."""
    global deducted_count
    payload = request.get_json(silent=True) or {}
    scans = payload.get("scans")
    if not isinstance(scans, list) or len(scans) > 100:
        return jsonify({"ok": False, "message": "Send up to 100 scans per sync."}), 400

    acknowledged, rejected = [], []
    for scan in scans:
        scan_id = str(scan.get("id", "")) if isinstance(scan, dict) else ""
        barcode = str(scan.get("barcode", "")).strip() if isinstance(scan, dict) else ""
        try:
            UUID(scan_id)
        except ValueError:
            rejected.append({"id": scan_id, "reason": "Invalid scan ID."})
            continue
        if not is_valid_barcode(barcode):
            rejected.append({"id": scan_id, "reason": "Barcode cannot be blank."})
            continue
        delta = scan.get("delta", 1)
        if delta not in (-1, 1):
            rejected.append({"id": scan_id, "reason": "Invalid count adjustment."})
            continue
        if scan_id in processed_scan_ids:
            acknowledged.append(scan_id)
            continue

        scanned_at = display_scan_time(scan.get("scanned_at"))
        counter = str(scan.get("counter", "1004"))
        found = next((item for item in barcodes if item["barcode"] == barcode), None)
        if found:
            if delta == -1 and found["count"] == 0:
                rejected.append({"id": scan_id, "reason": "Count is already zero."})
                continue
            found["count"] += delta
            found["scanned_at"] = scanned_at
            found["counter"] = counter
        elif delta == -1:
            rejected.append({"id": scan_id, "reason": "Cannot deduct an item with no recorded count."})
            continue
        else:
            found = {"barcode": barcode, "count": 1, "scanned_at": scanned_at, "counter": counter}
            barcodes.insert(0, found)
        activity.insert(0, {"barcode": barcode, "count": found["count"], "delta": delta, "time": scanned_at.split()[-2] + " " + scanned_at.split()[-1]})
        del activity[8:]
        if delta == -1:
            deducted_count += 1
        processed_scan_ids.add(scan_id)
        acknowledged.append(scan_id)

    return jsonify({"ok": True, "acknowledged": acknowledged, "rejected": rejected})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "").lower() == "true",
    )
