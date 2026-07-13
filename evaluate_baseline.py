import argparse
import time
import sys
import os

# Add src to path so we can import pulseguard_core
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from pulseguard_core import PulseGuardCore

def main():
    parser = argparse.ArgumentParser(description="Evaluate PulseGuard False Positive Rate on a clean baseline.")
    parser.add_argument("--duration", type=int, default=30, help="Duration to run the evaluation in minutes.")
    args = parser.parse_args()
    
    print(f"Starting PulseGuard baseline evaluation for {args.duration} minutes...")
    print("Please ensure the system is idle and not under induced stress.")
    
    # Initialize core but do NOT start the thread. We will run it synchronously here.
    core = PulseGuardCore()
    
    if core.self_test_failed:
        print(f"Warning: Core self-test failed: {core.self_test_error}")
        
    duration_seconds = args.duration * 60
    start_time = time.time()
    
    total_readings = 0
    anomalies_flagged = 0
    
    # Force initialize psutil
    core.collect_metrics()
    
    while time.time() - start_time < duration_seconds:
        time.sleep(2.0)
        
        raw_metrics = core.collect_metrics()
        norm_metrics = core.normalize(raw_metrics)
        
        # Prepare input
        import numpy as np
        ordered_keys = ["cpu", "ram", "disk_read", "disk_write", "net_sent", "net_recv"]
        input_data = [[norm_metrics[k] for k in ordered_keys]]
        input_array = np.array(input_data, dtype=np.float32)
        
        input_name = core.sess.get_inputs()[0].name
        output = core.sess.run(None, {input_name: input_array})
        
        score = core._extract_score(output)
        if score is None: score = 0.0
        
        core.window.append(raw_metrics)
        core.normalized_window.append(norm_metrics)
        core.scores.append(score)
        
        is_rule_anomaly = core.check_rules()
        is_model_anomaly = core.check_model(score)
        
        total_readings += 1
        if is_rule_anomaly or is_model_anomaly:
            anomalies_flagged += 1
            
        elapsed = time.time() - start_time
        print(f"\rElapsed: {int(elapsed)}s / {duration_seconds}s | Readings: {total_readings} | Anomalies: {anomalies_flagged}", end="")
            
    print("\n\n--- Evaluation Complete ---")
    print(f"Total Readings Evaluated : {total_readings}")
    print(f"Total Anomalies Flagged  : {anomalies_flagged}")
    
    if total_readings > 0:
        fpr = (anomalies_flagged / total_readings) * 100.0
        print(f"False Positive Rate      : {fpr:.2f}%")
    else:
        print("False Positive Rate      : N/A")

if __name__ == "__main__":
    main()
