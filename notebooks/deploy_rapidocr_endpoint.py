# Databricks notebook source
# Package RapidOCR as a Model Serving endpoint (defpredict-rapidocr).
# The app renders scanned pages to PNG images, base64-encodes them, and calls this
# endpoint to get back the recognized text regions WITH their bounding boxes.
# RapidOCR lives here only -- never in the app.
#
# The boxes are the whole point: parse.layout in the app uses them to restore spaces
# and rebuild tables. Returning only joined text (the old behaviour) collapsed every
# table cell onto its own line and dropped empty cells, shifting numbers into the
# wrong columns. Re-run this notebook to redeploy the endpoint after this change.

# COMMAND ----------

import mlflow
import mlflow.pyfunc
from mlflow.models.signature import ModelSignature
from mlflow.types.schema import ColSpec, Schema

MIN_CONFIDENCE = 0.5  # drop shaky reads so a bad guess never leaves the API


class RapidOCRModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        from rapidocr_onnxruntime import RapidOCR

        self.engine = RapidOCR()

    def predict(self, context, model_input):
        # all imports live inside the method so the pickled model is self-contained,
        # and RapidOCR/cv2 are only needed at serving time, not when logging
        import base64
        import json

        import cv2
        import numpy as np

        out = []
        for image_b64 in model_input["image_b64"]:
            raw = base64.b64decode(image_b64)
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            result, _ = self.engine(img)

            # Keep each region's bounding box, not just its text -- the app needs the
            # geometry to rebuild lines and tables. RapidOCR gives box as four corner
            # points; collapse to an axis-aligned rectangle the client can cluster on.
            regions = []
            for box, text, score in (result or []):
                if not text or score < MIN_CONFIDENCE:
                    continue
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                regions.append(
                    {
                        "text": text,
                        "x0": min(xs),
                        "y0": min(ys),
                        "x1": max(xs),
                        "y1": max(ys),
                        "score": float(score),
                    }
                )
            out.append(json.dumps(regions, ensure_ascii=False))
        return out


# COMMAND ----------

signature = ModelSignature(
    inputs=Schema([ColSpec("string", "image_b64")]),
    outputs=Schema([ColSpec("string")]),
)

mlflow.set_registry_uri("databricks-uc")
UC_MODEL = "defpredict.main.rapidocr"

with mlflow.start_run(run_name="rapidocr"):
    info = mlflow.pyfunc.log_model(
        artifact_path="rapidocr",
        python_model=RapidOCRModel(),
        registered_model_name=UC_MODEL,
        pip_requirements=["rapidocr-onnxruntime", "opencv-python-headless", "numpy", "pandas"],
        signature=signature,
    )
print("logged + registered:", info.model_uri)

# COMMAND ----------

# stand up (or update) the serving endpoint from the newest registered version
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
from mlflow.tracking import MlflowClient

mc = MlflowClient(registry_uri="databricks-uc")
latest = max(int(v.version) for v in mc.search_model_versions(f"name='{UC_MODEL}'"))

w = WorkspaceClient()
entity = ServedEntityInput(
    entity_name=UC_MODEL,
    entity_version=str(latest),
    workload_size="Small",
    scale_to_zero_enabled=True,  # no cost when idle
)
existing = [e.name for e in w.serving_endpoints.list()]
if "defpredict-rapidocr" in existing:
    w.serving_endpoints.update_config("defpredict-rapidocr", served_entities=[entity])
else:
    w.serving_endpoints.create(
        name="defpredict-rapidocr",
        config=EndpointCoreConfigInput(served_entities=[entity]),
    )
print("endpoint defpredict-rapidocr build kicked off on version", latest)
