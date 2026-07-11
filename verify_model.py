import onnxruntime as ort
import numpy as np
import json

# Load stats
with open('stats.json') as f:
    stats = json.load(f)

mean = np.array(list(stats['mean'].values()), dtype=np.float32)
std = np.array(list(stats['std'].values()), dtype=np.float32)

# Load model
sess = ort.InferenceSession('anomaly_detector.onnx', providers=['CPUExecutionProvider'])
input_name = sess.get_inputs()[0].name

# Test with a normal-looking sample (all zeros = at the mean, after normalization)
normal_sample = np.zeros((1, len(mean)), dtype=np.float32)

# Test with an extreme sample (way outside normal range)
anomalous_sample = np.array([[10, 10, 10, 10, 10, 10]], dtype=np.float32)

for name, sample in [("Normal", normal_sample), ("Anomalous", anomalous_sample)]:
    result = sess.run(None, {input_name: sample})
    print(f"{name} sample -> prediction: {result[0]}, score: {result[1] if len(result) > 1 else 'N/A'}")

print("\nModel loaded and ran successfully — you're good to hand off to Antigravity.")