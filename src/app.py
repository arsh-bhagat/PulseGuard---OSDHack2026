from flask import Flask, render_template, jsonify
from pulseguard_core import PulseGuardCore
import os
import json

app = Flask(__name__)
core = PulseGuardCore()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/metrics')
def get_metrics():
    with core.lock:
        if not core.latest_raw:
            return jsonify({})
        return jsonify({
            "metrics": core.latest_raw,
            "anomaly": core.latest_anomaly,
            "monitor_network": core.monitor_network
        })

@app.route('/api/model_info')
def get_model_info():
    with core.lock:
        latency = core.latest_latency_ms
    
    return jsonify({
        "size_mb": round(core.get_model_size_mb(), 2),
        "latency_ms": round(latency, 2),
        "recent_anomalies": core.get_recent_anomalies(10),
        "self_test_failed": core.self_test_failed,
        "self_test_error": core.self_test_error
    })

@app.route('/api/anomalies/dates')
def get_anomaly_dates():
    if not os.path.exists(core.log_path):
        return jsonify({"dates": []})
    dates = set()
    try:
        with open(core.log_path, 'r') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    entry = json.loads(line)
                    # timestamp is like "2026-07-10T20:21:39.123Z"
                    date_str = entry["timestamp"].split("T")[0]
                    dates.add(date_str)
                except:
                    pass
    except:
        pass
    return jsonify({"dates": sorted(list(dates), reverse=True)})

@app.route('/api/anomalies')
def get_anomalies_by_date():
    from flask import request
    target_date = request.args.get('date')
    if not target_date or not os.path.exists(core.log_path):
        return jsonify({"anomalies": []})
        
    anomalies = []
    try:
        with open(core.log_path, 'r') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    entry = json.loads(line)
                    date_str = entry["timestamp"].split("T")[0]
                    if date_str == target_date:
                        anomalies.append(entry)
                except:
                    pass
    except:
        pass
    # Return newest first
    return jsonify({"anomalies": anomalies[::-1]})

@app.route('/api/clear_logs', methods=['POST'])
def clear_logs():
    with core.lock:
        # Clear the in-memory scores if we want to reset anomaly states
        core.scores.clear()
        core.latest_anomaly = False
        
        # Empty the JSON log file
        open(core.log_path, 'w').close()
    return jsonify({"status": "ok"})

@app.route('/api/settings/network-monitor', methods=['POST'])
def toggle_network_monitor():
    from flask import request
    data = request.json or {}
    enabled = data.get('enabled', True)
    with core.lock:
        core.monitor_network = bool(enabled)
    return jsonify({"status": "ok", "monitor_network": core.monitor_network})

if __name__ == '__main__':
    # Start the core background loop
    core.start()
    # Bind strictly to localhost (127.0.0.1)
    app.run(host='127.0.0.1', port=5000)
