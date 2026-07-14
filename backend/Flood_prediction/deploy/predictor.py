import torch
import numpy as np
import xgboost as xgb
import joblib
import json
import pandas as pd
from flood_lstm import FloodLSTM


class StreamflowPredictor:
    """
    End-to-end inference pipeline with full preprocessing.
    Usage:
        predictor = StreamflowPredictor("path/to/deploy/")

        # Option A — pass raw DataFrame window (recommended)
        result = predictor.predict_from_raw(df_window, prev_raw_streamflow)

        # Option B — pass already-preprocessed arrays
        result = predictor.predict(x_dynamic, x_flat, prev_raw_streamflow)
    """

    def __init__(self, deploy_dir: str, device: str = "cpu"):
        self.device     = torch.device(device)
        self.deploy_dir = deploy_dir.rstrip("/") + "/"

        with open(f"{self.deploy_dir}model_config.json") as f:
            self.config = json.load(f)

        arch         = self.config["architecture"]
        self.seq_len = arch["seq_len"]

        # ── Load LSTM ─────────────────────────────────────────
        self.lstm = FloodLSTM(
            input_size  = arch["input_size"],
            hidden_size = arch["hidden_size"],
            num_layers  = arch["num_layers"],
            dropout     = arch["dropout"],
        )
        ckpt  = torch.load(
            f"{self.deploy_dir}best_flood_lstm.pt",
            map_location=self.device,
            weights_only=False
        )
        # Strip DataParallel prefix if present
        state = {k.replace("module.", ""): v
                 for k, v in ckpt["model_state"].items()}
        self.lstm.load_state_dict(state)
        self.lstm.eval().to(self.device)

        # ── Load XGBoost ──────────────────────────────────────
        self.xgb = xgb.XGBRegressor()
        self.xgb.load_model(f"{self.deploy_dir}flood_xgb_corrector.json")

        # ── Load all 4 scalers ────────────────────────────────
        self.yj_transformer = joblib.load(f"{self.deploy_dir}yj_transformer.pkl")
        self.mm_scaler      = joblib.load(f"{self.deploy_dir}mm_scaler.pkl")
        self.feature_scaler = joblib.load(f"{self.deploy_dir}feature_scaler.pkl")
        self.target_scaler  = joblib.load(f"{self.deploy_dir}target_scaler.pkl")

        # ── Column maps from config ───────────────────────────
        sc = self.config["input_scalers"]
        self.yj_raw_cols    = sc["yj_transformer"]["raw_input_cols"]
        self.mm_cols        = sc["mm_scaler"]["applies_to"]
        self.feature_cols   = sc["feature_scaler"]["applies_to"]
        self.dynamic_cols   = self.config["dynamic_cols"]
        self.flat_cols      = self.config["flat_cols"]

        print(f"✅ StreamflowPredictor ready on {device}")
        print(f"   Dynamic features : {len(self.dynamic_cols)}")
        print(f"   Flat features    : {len(self.flat_cols)}")

    # ──────────────────────────────────────────────────────────
    def preprocess(self, df_window: pd.DataFrame):
        """
        Apply all 3 input scalers to a raw DataFrame window.

        Args:
            df_window : pd.DataFrame shape (SEQ_LEN, raw_feature_cols)
                        Rows are chronological. Columns are RAW names
                        (e.g. 'UP_AREA', not 'UP_AREA_yj').
                        The last row is the prediction timestep.
        Returns:
            x_dynamic : np.ndarray (SEQ_LEN, 32)  → LSTM
            x_flat    : np.ndarray (42,)           → XGBoost (last row only)
        """
        df = df_window.copy()

        # Step 1: Yeo-Johnson → transform raw cols → rename to _yj
        df[self.yj_raw_cols] = self.yj_transformer.transform(df[self.yj_raw_cols])
        rename_map = {col: f"{col}_yj" for col in self.yj_raw_cols}
        df = df.rename(columns=rename_map)

        # Step 2: MinMax scale antecedent / capacity cols
        present_mm = [c for c in self.mm_cols if c in df.columns]
        df[present_mm] = self.mm_scaler.transform(df[present_mm])

        # Step 3: Standard scale delta / static / routing cols
        present_fs = [c for c in self.feature_cols if c in df.columns]
        df[present_fs] = self.feature_scaler.transform(df[present_fs])

        # Step 4: Extract arrays in exact column order
        x_dynamic = df[self.dynamic_cols].values.astype(np.float32)       # (SEQ_LEN, 32)
        x_flat    = df[self.flat_cols].iloc[-1].values.astype(np.float32)  # (42,)

        return x_dynamic, x_flat

    # ──────────────────────────────────────────────────────────
    def _forward(self, x_dynamic: np.ndarray, x_flat: np.ndarray,
                 prev_raw_streamflow: float) -> dict:
        """
        Core inference — assumes x_dynamic and x_flat are already preprocessed.
        """
        assert x_dynamic.shape == (self.seq_len, len(self.dynamic_cols)), (
            f"x_dynamic shape mismatch: "
            f"expected ({self.seq_len}, {len(self.dynamic_cols)}), "
            f"got {x_dynamic.shape}"
        )
        assert x_flat.shape == (len(self.flat_cols),), (
            f"x_flat shape mismatch: "
            f"expected ({len(self.flat_cols)},), got {x_flat.shape}"
        )

        # LSTM forward
        x_dyn_t = torch.from_numpy(x_dynamic).unsqueeze(0).to(self.device)
        with torch.no_grad():
            lstm_pred, hidden = self.lstm(x_dyn_t, return_hidden=True)
        lstm_pred_np = lstm_pred.cpu().numpy().ravel()   # (1,)
        hidden_np    = hidden.cpu().numpy()              # (1, 256)

        # XGBoost forward
        xgb_input = np.concatenate([x_flat.reshape(1, -1), hidden_np], axis=1)
        xgb_corr  = self.xgb.predict(xgb_input)         # (1,)

        # Combine + inverse scale delta → raw streamflow
        hybrid_scaled = float(lstm_pred_np[0] + xgb_corr[0])
        raw_delta     = float(
            self.target_scaler.inverse_transform([[hybrid_scaled]])[0][0]
        )
        pred_raw = prev_raw_streamflow + raw_delta

        return {
            "pred_raw_streamflow"   : float(pred_raw),
            "pred_delta_raw"        : float(raw_delta),
            "lstm_pred_scaled"      : float(lstm_pred_np[0]),
            "xgb_correction_scaled" : float(xgb_corr[0]),
            "hybrid_delta_scaled"   : float(hybrid_scaled),
        }

    # ──────────────────────────────────────────────────────────
    def predict_from_raw(self, df_window: pd.DataFrame,
                         prev_raw_streamflow: float) -> dict:
        """
        Full pipeline: raw DataFrame → preprocess → predict.
        Use this in the backend API.

        Args:
            df_window           : pd.DataFrame (SEQ_LEN rows, raw feature cols)
            prev_raw_streamflow : float — actual observed flow at t-1 (m³/s)
        Returns:
            dict with pred_raw_streamflow, pred_delta_raw,
                       lstm_pred_scaled, xgb_correction_scaled,
                       hybrid_delta_scaled
        """
        x_dynamic, x_flat = self.preprocess(df_window)
        return self._forward(x_dynamic, x_flat, prev_raw_streamflow)

    # ──────────────────────────────────────────────────────────
    def predict(self, x_dynamic: np.ndarray, x_flat: np.ndarray,
                prev_raw_streamflow: float) -> dict:
        """
        Skip preprocessing — use when arrays are already scaled.
        Useful for testing against sample_io.json.

        Args:
            x_dynamic           : np.ndarray (SEQ_LEN, 32) — already preprocessed
            x_flat              : np.ndarray (42,)          — already preprocessed
            prev_raw_streamflow : float (m³/s)
        """
        return self._forward(x_dynamic, x_flat, prev_raw_streamflow)