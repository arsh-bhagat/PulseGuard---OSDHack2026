# PulseGuard 🛡️

**Offline-first anomaly detection for critical systems**

PulseGuard is a lightweight, local-first Python application that monitors live system metrics — CPU, RAM, disk I/O, and network I/O — and flags anomalous behavior in real time. It runs its AI model entirely offline, with zero outbound network calls, making it suitable for air-gapped, regulated, or privacy-sensitive environments where sending system data to a cloud monitoring service isn't an option.

Built for **OSDHack 2026** (theme: On Device AI).

---

## Problem Statement

Most system monitoring and anomaly detection tools rely on cloud-based dashboards or APIs — Datadog, cloud SIEM tools, hosted APM services. That's a non-starter in environments where system telemetry can't leave the machine: banking infrastructure, defense networks, healthcare systems, or any air-gapped setup. Teams in these environments are often left with basic threshold alerts or manual log-watching, with no access to the kind of pattern-based anomaly detection that cloud tools offer.

## Solution Overview

PulseGuard runs a small, pre-trained anomaly detection model directly on the device being monitored. It continuously polls system metrics, evaluates them against a trained baseline of "normal" behavior for that machine, and flags anomalies using two independent mechanisms:

1. **Model-based detection** — an Isolation Forest model (exported to ONNX) scores each reading against learned patterns of normal system behavior, and flags a window as anomalous if the latest reading crosses a threshold, or if 3+ of the last 5 readings are individually anomalous.
2. **Rule-based backstop** — a simple, explainable hardcoded check (CPU or RAM > 95% for 3 consecutive readings) that fires independently of the model, so genuinely extreme values are caught even if they fall outside what the model saw during training.

Every anomaly is logged with which mechanism triggered it, so the tool's behavior stays explainable rather than being a black box — and everything is visible on a local dashboard.

## On-Device AI Usage

- **Model**: Isolation Forest, trained on system metrics (CPU%, RAM%, disk read/write rate, network sent/recv rate) collected from a real machine over ~2 hours of normal use.
- **Format**: Exported to ONNX (`.onnx`) via `skl2onnx`.
- **Runtime**: [ONNX Runtime](https://onnxruntime.ai/) with `CPUExecutionProvider` — no GPU required.
- **Where it runs**: Entirely on the local machine being monitored. Inference happens in-process, on every polling cycle, with no network call involved.
- **Why local**: The core anomaly detection can never depend on network access — that's the entire point. If the device is offline, air-gapped, or the network is down, PulseGuard keeps working exactly the same.

## Tech Stack

| Layer | Tool |
|---|---|
| Metric collection | `psutil` |
| Model training | `scikit-learn` (Isolation Forest) |
| Model export | `skl2onnx` |
| Local inference | `onnxruntime` (CPU) |
| Backend / API | `Flask`, bound strictly to `127.0.0.1` |
| Frontend | HTML + Chart.js (bundled locally, no CDN) |
| Audit logging | Python `logging`, local `audit.log` |

No cloud services are used anywhere in this project — model training was done locally/in a notebook as a one-time offline step, and the exported model file is committed as a static artifact.

**Note on `psutillogger.py`:** this is the one-time data collection script used to build `metrics.csv`, the training data behind `anomaly_detector.onnx` and `stats.json`. It's not part of the live monitoring pipeline — it's included in the repo for transparency/reproducibility, so anyone can see exactly how the training data was generated.

## Setup Instructions

**Requirements:** Python 3.8+

```bash
pip install onnxruntime psutil flask
```

Clone the repository and make sure `anomaly_detector.onnx` and `stats.json` are present in the project root (they're committed to this repo).

## Usage Instructions

**1. Start PulseGuard:**
```bash
python src/app.py
```
This starts both the background metrics/inference loop and the local dashboard server.

**2. Open the dashboard:**
Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

**3. Trigger a demo anomaly (optional):**
In a separate terminal:
```bash
python stress_test.py
```
This spikes CPU usage across all cores, which will trigger the rule-based backstop and appear on the dashboard within a couple of polling cycles. Press `Ctrl+C` to stop the stress test.

**4. Check the audit trail:**
`audit.log` records every read of the model and stats files, and `anomaly_log.json` records every detected anomaly with a timestamp, trigger type, score, and the raw metrics that caused it.

## Demo Video

<!-- To be added: link to a 2–5 minute walkthrough showing the dashboard, a live-triggered anomaly via stress_test.py, and a run with network access disabled. -->
*Coming soon.*

## Screenshots

<!-- To be added: dashboard during normal operation, dashboard showing a flagged anomaly, and the anomaly_log.json / audit.log output. -->
*Coming soon.*

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Known Limitations & Future Scope

- The model's baseline is intentionally trained on a single machine's normal usage pattern, not pooled across multiple devices. This is a deliberate design choice, not an oversight — "normal" CPU/RAM/I/O behavior varies significantly between machines (hardware, OS, workload), so merging data from a different device would blur the baseline rather than improve it. Each deployment of PulseGuard is meant to be trained on the specific machine it will monitor. Retraining on a new machine takes only a few minutes using the included `psutillogger.py` script.
- Currently supports a fixed set of six metrics (CPU, RAM, disk read/write, network sent/recv). Extending to additional metrics (per-process usage, temperature, GPU load) is a natural next step.
- No persistent metric history is stored beyond the in-memory sliding window and the anomaly log — a longer-term local time-series store could enable trend analysis, not just point-in-time flagging.
- Currently runs as a single-machine monitor. A lightweight local-network mode for monitoring a small cluster of air-gapped machines (still without any external cloud dependency) is a possible extension.
- Planned: an optional embedded/hardware alert (e.g. an Arduino-driven buzzer or LED) that fires on high-severity anomalies, for environments without someone actively watching a screen.
