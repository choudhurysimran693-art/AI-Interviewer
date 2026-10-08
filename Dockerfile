# Download the pinned q8 model separately so source changes reuse this layer.
# The other model variants are not used by the browser's WASM detector.
FROM python:3.11-slim AS detector
WORKDIR /model
RUN python -c "import hashlib, urllib.request; url='https://huggingface.co/onnx-community/grounding-dino-tiny-ONNX/resolve/ff690b0a8050566c290287545bd059350f3e9096/onnx/model_quantized.onnx'; urllib.request.urlretrieve(url, 'model_quantized.onnx'); actual=hashlib.file_digest(open('model_quantized.onnx', 'rb'), 'sha256').hexdigest(); expected='70bf2d3310d1ae73769c96a71e00cbf2861eb33a1f4d97d84a108a7bf02c03c9'; assert actual == expected, 'Detector model checksum mismatch'"

FROM node:22-bookworm-slim AS web
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY --from=detector /model/model_quantized.onnx ./public/models/grounding-dino/onnx/model_quantized.onnx
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --chown=user backend ./backend
COPY --from=web --chown=user /build/frontend/dist ./frontend/dist
USER user
ENV PYTHONPATH=/home/user/app/backend PORT=7860 DATA_DIR=/home/user/app/data
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "7860", "--no-access-log"]
