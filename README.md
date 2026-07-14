# PulseGuard 🛡️
**Offline-first anomaly detection for critical systems**

PulseGuard is a lightweight, local-first Python application that monitors live system metrics (CPU, RAM, disk I/O, network I/O) and flags anomalies. It runs entirely offline with zero outbound network calls, perfect for air-gapped, regulated, or privacy-sensitive environments.

---

## Problem Statement

Cloud-based system monitoring tools (like Datadog or hosted SIEMs) cannot be used in environments where telemetry cannot leave the machine (e.g., banking, defense, healthcare). Teams in these air-gapped setups lack pattern-based anomaly detection and are stuck with manual logs or basic thresholds.

## Solution Overview

PulseGuard runs a pre-trained anomaly detection model locally, evaluating live metrics against a trained baseline. It flags anomalies using two independent mechanisms:

1. **Model-based detection** — An Isolation Forest model (exported to ONNX) scores readings, flagging anomalies based on native decision thresholds (e.g., current reading is an anomaly, or 3+ of the last 5 readings).
2. **Rule-based backstop** — A simple hardcoded check (CPU or RAM > 95% for 3 consecutive readings) catches genuinely extreme values independent of the model.

Anomalies are classified by **severity** (low/medium/high) and list the **top contributing metrics** via z-score. Network throughput spikes are handled asymmetrically—they are logged distinctly as 'High Activity' rather than full anomalies to prevent false alarms during normal large downloads. A local dashboard provides live charts, date-based anomaly browsing, and audio alerts.

## On-Device AI Usage

- **Model**: Isolation Forest, trained locally on ~2 hours of normal system usage.
- **Format**: Exported to `.onnx` via `skl2onnx`.
- **Runtime**: ONNX Runtime (`CPUExecutionProvider`) — runs in-process with no network calls and no GPU required.
- **Offline-First**: Fully functional without network access. A startup self-test verifies model health.

## Tech Stack

- **Metric collection**: `psutil`
- **Model training**: `scikit-learn` (Isolation Forest)
- **Model inference**: `onnxruntime` (CPU)
- **Backend**: `Flask` (bound to `127.0.0.1`)
- **Frontend**: HTML + Chart.js, Web Audio API
- **Logging**: Python `logging`, local `audit.log`

*(Note: `psutillogger.py` is included for transparency to show how training data was collected. It is not part of live monitoring.)*

## Setup Instructions

**Requirements:** Python 3.8+

```bash
pip install onnxruntime psutil flask
```
*(Ensure `anomaly_detector.onnx` and `stats.json` are present in the project root.)*

## Usage Instructions

1. **Start PulseGuard:** `python src/app.py`
2. **Open Dashboard:** Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000)
3. **Trigger a Demo:** Run `python stress_test.py` to spike CPU usage and trigger an alert.
4. **Audit Trail:** Check `audit.log` for system reads, and `anomaly_log.json` for flagged anomalies.
5. **Measure False-Positives:** Run `python evaluate_baseline.py --duration 30` to test the baseline accuracy passively on your hardware.

## Training on Your Own Machine (Optional)

PulseGuard ships with a pre-trained model. To improve accuracy for your specific hardware, you can retrain it:

1. **Collect Data:** Run `python psutillogger.py` for 15-30+ minutes while using your machine normally to generate a new `metrics.csv`.
2. **Retrain:** Run `python train_model.py` (Requires `pip install scikit-learn pandas skl2onnx`). This script automatically normalizes your data, trains the model, and exports the new `anomaly_detector.onnx` and `stats.json` directly into your folder.
3. **Restart:** Restart PulseGuard and it will automatically use your new, hardware-specific baseline!

## Screenshots

*Coming soon.*

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Known Limitations & Future Scope

- **Machine-Specific Baseline**: The model is intentionally trained on a single machine's normal usage. Merging data across different machines blurs the baseline. Retrain per device for best results.
- **Metrics**: Currently supports CPU, RAM, Disk, and Network I/O (measured as local NIC throughput strictly for anomaly detection, with a UI toggle to disable it). Future extensions could add per-process usage, temperature, or GPU load.
- **Storage**: Only keeps a short in-memory sliding window and an anomaly log. A persistent time-series store could enable trend analysis.
- **Network Mode**: A lightweight, offline local-network mode for monitoring a small air-gapped cluster is a possible future feature.

