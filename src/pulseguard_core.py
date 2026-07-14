import time
import json
import psutil
import onnxruntime as rt
import threading
import logging
from collections import deque
from datetime import datetime
import os
import numpy as np

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
audit_handler = logging.FileHandler("audit.log")
audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(audit_handler)

class PulseGuardCore:
    def __init__(self, model_path="anomaly_detector.onnx", stats_path="stats.json", log_path="anomaly_log.json"):
        self.model_path = model_path
        self.stats_path = stats_path
        self.log_path = log_path
        
        self.stats = self._load_stats()
        self.sess = self._load_model()
        
        # State
        self.window = deque(maxlen=30) # Raw readings
        self.normalized_window = deque(maxlen=30) # Normalized readings
        self.scores = deque(maxlen=30) # Anomaly scores
        self.labels = deque(maxlen=30) # Anomaly labels (-1 or 1)
        self.last_net = psutil.net_io_counters()
        self.last_disk = psutil.disk_io_counters()
        self.last_time = time.time()
        
        # Metrics for dashboard
        self.latest_raw = None
        self.latest_anomaly = False
        self.latest_latency_ms = 0.0
        
        self.running = False
        self.lock = threading.Lock()
        self.monitor_network = True # Toggle for network monitoring
        
        # Self test
        self.self_test_failed = False
        self.self_test_error = ""
        self._run_self_test()
        
    def _run_self_test(self):
        try:
            # Create a "perfectly normal" input (means)
            norm_metrics = self.normalize(self.stats["mean"])
            ordered_keys = ["cpu", "ram", "disk_read", "disk_write", "net_sent", "net_recv"]
            input_data = [[norm_metrics[k] for k in ordered_keys]]
            input_array = np.array(input_data, dtype=np.float32)
            input_name = self.sess.get_inputs()[0].name
            output = self.sess.run(None, {input_name: input_array})
            
            score = self._extract_score(output)
            if score is None:
                self.self_test_failed = True
                self.self_test_error = "Score extraction returned None"
        except Exception as e:
            self.self_test_failed = True
            self.self_test_error = str(e)
            audit_logger.error(f"Self-test failed: {e}")
        
    def _load_stats(self):
        audit_logger.info(f"READ: stats.json")
        with open(self.stats_path, 'r') as f:
            return json.load(f)
            
    def _load_model(self):
        audit_logger.info(f"READ: anomaly_detector.onnx")
        # Ensure CPUExecutionProvider only
        sess = rt.InferenceSession(self.model_path, providers=['CPUExecutionProvider'])
        return sess

    def get_model_size_mb(self):
        if os.path.exists(self.model_path):
            return os.path.getsize(self.model_path) / (1024 * 1024)
        return 0.0

    def collect_metrics(self):
        # Poll metrics
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        
        current_net = psutil.net_io_counters()
        current_disk = psutil.disk_io_counters()
        current_time = time.time()
        
        dt = current_time - self.last_time
        if dt <= 0: dt = 1.0
        
        disk_read = (current_disk.read_bytes - self.last_disk.read_bytes) / dt
        disk_write = (current_disk.write_bytes - self.last_disk.write_bytes) / dt
        net_sent = (current_net.bytes_sent - self.last_net.bytes_sent) / dt
        net_recv = (current_net.bytes_recv - self.last_net.bytes_recv) / dt
        
        self.last_net = current_net
        self.last_disk = current_disk
        self.last_time = current_time
        
        return {
            "cpu": cpu,
            "ram": ram,
            "disk_read": disk_read,
            "disk_write": disk_write,
            "net_sent": net_sent,
            "net_recv": net_recv
        }

    def normalize(self, metrics):
        norm = {}
        for k in metrics:
            mean = self.stats["mean"][k]
            std = self.stats["std"][k]
            if std == 0:
                norm[k] = 0.0
            else:
                norm[k] = (metrics[k] - mean) / std
        return norm

    def check_rules(self):
        # Check rule-based backstop: CPU% or RAM% > 95% for 3 consecutive readings
        if len(self.window) < 3:
            return False
            
        recent = list(self.window)[-3:]
        for metric in ["cpu", "ram"]:
            if all(r[metric] > 95.0 for r in recent):
                return True
        return False

    def check_model(self, current_label):
        # The window is flagged as anomalous if:
        # The MOST RECENT reading's label is -1
        if current_label == -1:
            return True
            
        # OR 3 or more of the last 5 labels are -1
        if len(self.labels) >= 5:
            recent_labels = list(self.labels)[-5:]
            anomalous_count = sum(1 for l in recent_labels if l == -1)
            if anomalous_count >= 3:
                return True
                
        return False

    def get_contributing_metrics(self, norm_metrics):
        # Calculate z-scores and return top 2
        z_scores = []
        for k, v in norm_metrics.items():
            z_scores.append({"metric": k, "z_score": round(v, 2), "abs_z": abs(v)})
        z_scores.sort(key=lambda x: x["abs_z"], reverse=True)
        top_2 = z_scores[:2]
        
        result = []
        for item in top_2:
            direction = "elevated" if item["z_score"] > 0 else "unusually low"
            result.append({"metric": item["metric"], "z_score": item["z_score"], "direction": direction})
        return result

    def get_severity(self, is_rule_anomaly, score):
        if is_rule_anomaly:
            return "HIGH"
        # Isolation Forest native decision function: negative means anomaly
        if score >= -0.05:
            return "LOW"
        elif score >= -0.1:
            return "MEDIUM"
        else:
            return "HIGH"

    def log_anomaly(self, trigger_type, score, raw_metrics, norm_metrics):
        severity = self.get_severity(trigger_type == "rule-based-backstop", score)
        contributing = self.get_contributing_metrics(norm_metrics)
        
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trigger": trigger_type,
            "score": score,
            "severity": severity,
            "metrics": raw_metrics,
            "contributing_metrics": contributing
        }
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry) + "\n")
            
    def _extract_score(self, output):
        score = None
        if isinstance(output, list) and len(output) > 1:
            if isinstance(output[1], np.ndarray):
                score = float(output[1].flatten()[0])
            elif isinstance(output[1], list) and isinstance(output[1][0], dict):
                score = float(output[1][0].get(1, list(output[1][0].values())[-1]))
            else:
                try:
                    score = float(np.array(output[1]).flatten()[0])
                except Exception:
                    pass
        elif isinstance(output, list) and len(output) == 1:
            try:
                score = float(np.array(output[0]).flatten()[0])
            except Exception:
                pass
                
        if score is None:
            logging.error(f"Failed to parse ONNX score output structure: {output}")
            
        return score

    def _extract_label(self, output):
        label = 1 # Default to normal
        if isinstance(output, list) and len(output) > 0:
            try:
                label = int(np.array(output[0]).flatten()[0])
            except Exception:
                logging.error(f"Failed to parse ONNX label output structure: {output}")
        return label

    def _loop(self):
        # Initialize psutil cpu percent
        psutil.cpu_percent(interval=None)
        
        while self.running:
            time.sleep(2.0)
            
            raw_metrics = self.collect_metrics()
            norm_metrics = self.normalize(raw_metrics)
            
            with self.lock:
                monitor_net = self.monitor_network

            # If network monitoring is disabled, clamp network features to 0.0 (the mean).
            # This preserves the ONNX model's required 6-feature input shape,
            # while ensuring network I/O has exactly 0 influence on anomaly scoring.
            if not monitor_net:
                norm_metrics["net_sent"] = 0.0
                norm_metrics["net_recv"] = 0.0
            
            # Prepare input for inference (shape [1, 6])
            ordered_keys = ["cpu", "ram", "disk_read", "disk_write", "net_sent", "net_recv"]
            input_data = [[norm_metrics[k] for k in ordered_keys]]
            input_array = np.array(input_data, dtype=np.float32)
            
            # Run inference and measure time
            t0 = time.perf_counter()
            input_name = self.sess.get_inputs()[0].name
            output = self.sess.run(None, {input_name: input_array})
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000.0
            
            # Extract anomaly score using hardened method
            extracted_score = self._extract_score(output)
            score = extracted_score if extracted_score is not None else 0.0
            label = self._extract_label(output)
            
            print(f"[DEBUG] label={label} | raw_score={score:.4f} | cpu={raw_metrics['cpu']:.1f}% | ram={raw_metrics['ram']:.1f}%")

            with self.lock:
                self.window.append(raw_metrics)
                self.normalized_window.append(norm_metrics)
                self.scores.append(score)
                self.labels.append(label)
                self.latest_raw = raw_metrics
                self.latest_latency_ms = latency_ms
                
                # Check for anomalies
                is_rule_anomaly = self.check_rules()
                is_model_anomaly = self.check_model(label)
                
                if is_rule_anomaly or is_model_anomaly:
                    self.latest_anomaly = True
                    trigger = "rule-based-backstop" if is_rule_anomaly else "model-based"
                    self.log_anomaly(trigger, score, raw_metrics, norm_metrics)
                else:
                    self.latest_anomaly = False

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False

    def get_recent_anomalies(self, limit=10):
        if not os.path.exists(self.log_path):
            return []
        
        lines = []
        try:
            with open(self.log_path, 'r') as f:
                lines = f.readlines()
        except:
            return []
            
        anomalies = []
        for line in reversed(lines):
            if not line.strip(): continue
            try:
                anomalies.append(json.loads(line))
            except:
                pass
            if len(anomalies) >= limit:
                break
        return anomalies
