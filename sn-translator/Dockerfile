# Multi-arch base — python:3.12-slim ships arm64/v8 manifests, so this image
# builds cleanly on the A1.Flex (aarch64) nodes without a buildx detour.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

RUN mkdir -p /app/data

EXPOSE 8091

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8091"]
