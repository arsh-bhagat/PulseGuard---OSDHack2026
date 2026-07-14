import pandas as pd
import json
from sklearn.ensemble import IsolationForest
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import os

def train():
    if not os.path.exists("metrics.csv"):
        print("Error: metrics.csv not found. Please run psutillogger.py first to collect data.")
        return

    print("Loading metrics.csv...")
    df = pd.read_csv("metrics.csv")
    
    # disk and network metrics are cumulative counters from psutil.
    # We must convert them to rates (bytes per second) to match the live backend.
    # Since psutillogger logs every 1 second, the difference between rows is the rate.
    cols_to_diff = ["disk_read", "disk_write", "net_sent", "net_recv"]
    for col in cols_to_diff:
        df[col] = df[col].diff()
        
    # Drop the first row which will have NaNs from the diff operation
    df.dropna(inplace=True)
    
    # Calculate stats for normalization in the backend
    stats = {
        "mean": df.mean().to_dict(),
        "std": df.std().to_dict()
    }
    with open("stats.json", "w") as f:
        json.dump(stats, f, indent=4)
    print("Saved stats.json")
    
    # Normalize the training data
    df_norm = (df - df.mean()) / df.std()
    df_norm.fillna(0, inplace=True) # Handle standard deviation of 0
    
    print("Training Isolation Forest model...")
    # Adjust contamination based on how many anomalies you expect in your baseline data
    clf = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
    clf.fit(df_norm)
    
    print("Exporting model to ONNX format...")
    initial_type = [('float_input', FloatTensorType([None, df_norm.shape[1]]))]
    onnx_model = convert_sklearn(clf, initial_types=initial_type)
    
    with open("anomaly_detector.onnx", "wb") as f:
        f.write(onnx_model.SerializeToString())
    print("Saved anomaly_detector.onnx")
    
    print("\nTraining complete! You can now restart PulseGuard to use your custom baseline.")

if __name__ == "__main__":
    train()
