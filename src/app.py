from flask import Flask, render_template, jsonify
from pulseguard_core import PulseGuardCore
import os

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
            "anomaly": core.latest_anomaly
        })

@app.route('/api/model_info')
def get_model_info():
    with core.lock:
        latency = core.latest_latency_ms
    
    return jsonify({
        "size_mb": round(core.get_model_size_mb(), 2),
        "latency_ms": round(latency, 2),
        "recent_anomalies": core.get_recent_anomalies(10)
    })

@app.route('/api/clear_logs', methods=['POST'])
def clear_logs():
    with core.lock:
        # Clear the in-memory scores if we want to reset anomaly states
        core.scores.clear()
        core.latest_anomaly = False
        
        # Empty the JSON log file
        open(core.log_path, 'w').close()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Start the core background loop
    core.start()
    # Bind strictly to localhost (127.0.0.1)
    app.run(host='127.0.0.1', port=5000)
