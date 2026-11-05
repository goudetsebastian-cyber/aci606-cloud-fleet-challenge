"""Load the trusted, versioned artifact once; share its read-only pipeline."""
from pathlib import Path
from time import perf_counter
import joblib
import numpy as np
from app.schemas import Prediction, Telemetry


class Predictor:
    def __init__(self, path: Path):
        if not path.is_file():
            raise RuntimeError("Modelo ausente. Ejecutar python ml/train_model.py antes de iniciar.")
        artifact = joblib.load(path)
        self.pipeline = artifact["pipeline"]
        self.features = artifact["features"]
        self.version = artifact["model_version"]
        self.evaluation = artifact["evaluation"]
        self.name = artifact["selected_model"]

    def predict(self, sample: Telemetry) -> Prediction:
        start = perf_counter()
        values = np.array([[getattr(sample, name) for name in self.features]], dtype=float)
        probabilities = self.pipeline.predict_proba(values)[0]
        index = int(np.argmax(probabilities))
        return Prediction(
            robot_id=sample.robot_id, predicted_status=str(self.pipeline.classes_[index]),
            confidence=round(float(probabilities[index]), 6), model_version=self.version,
            inference_ms=round((perf_counter() - start) * 1000, 4),
        )
