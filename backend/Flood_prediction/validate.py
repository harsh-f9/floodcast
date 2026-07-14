"""
Startup validation for the Flood Prediction system.
Runs the 3 sample_io.json tests to verify the model loads correctly.

Usage:
    from Flood_prediction.validate import run_validation
    run_validation()  # raises AssertionError if any sample fails
"""

import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEPLOY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy")
SAMPLE_IO_PATH = os.path.join(DEPLOY_DIR, "sample_io.json")


def run_validation():
    """
    Validate StreamflowPredictor against sample_io.json.
    Uses the .predict() method (pre-processed arrays) for exact comparison.
    """
    from prediction_service import get_predictor

    predictor = get_predictor()

    with open(SAMPLE_IO_PATH) as f:
        samples = json.load(f)

    print(f"🔬 Running validation against {len(samples)} samples...")

    for s in samples:
        x_dynamic = np.array(s["x_dynamic_sample"], dtype="float32")
        x_flat    = np.array(s["x_flat_sample"],    dtype="float32")

        # prev_raw_streamflow = actual_streamflow - y_delta_scaled (from spec)
        # Actually: the predict method expects prev_raw_streamflow
        # From sample: pred_raw_streamflow = prev_raw + raw_delta
        # So: prev_raw = pred_raw_streamflow - raw_delta
        # But we need to compute it differently.
        # The sample gives us y_raw_streamflow (actual) and y_delta_scaled.
        # target_scaler.inverse_transform of hybrid_delta_scaled gives raw_delta
        # pred_raw = prev_raw + raw_delta
        # So prev_raw = actual_streamflow - (actual_raw_delta)
        # But from the spec: prev_raw = actual_streamflow - y_delta_scaled
        # Wait, y_delta_scaled is the scaled delta, not raw.
        # Let's use: prev_raw = y_raw_streamflow - target_scaler.inverse_transform(y_delta_scaled)
        # But simpler: the sample has the expected pred_raw_streamflow.
        # We need prev_raw such that pred = prev_raw + predicted_delta
        # Using actual: prev_raw = y_raw_streamflow - actual_delta
        # Since we want to match pred_raw_streamflow, let's reverse-engineer:
        # We know the model will produce a certain hybrid_delta_scaled
        # pred_raw = prev_raw + inverse_transform(hybrid_delta_scaled)
        # The sample stores: actual_streamflow and y_delta_scaled
        # actual_delta_raw = target_scaler.inverse_transform(y_delta_scaled)
        # prev_raw = actual_streamflow - actual_delta_raw
        actual_delta_raw = float(
            predictor.target_scaler.inverse_transform(
                [[s["y_delta_scaled"]]]
            )[0][0]
        )
        prev_raw = s["y_raw_streamflow"] - actual_delta_raw

        result = predictor.predict(x_dynamic, x_flat, prev_raw)

        diff = abs(result["pred_raw_streamflow"] - s["pred_raw_streamflow"])
        assert diff < 0.5, (
            f"Sample {s['index']} FAILED: "
            f"expected={s['pred_raw_streamflow']:.4f}, "
            f"got={result['pred_raw_streamflow']:.4f}, "
            f"diff={diff:.4f}"
        )
        print(f"  ✅ Sample {s['index']} passed (diff={diff:.4f})")

    print("✅ All validation samples passed. Model is loaded correctly.\n")


if __name__ == "__main__":
    run_validation()
