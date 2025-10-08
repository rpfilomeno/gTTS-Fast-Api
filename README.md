# gTTS-Fast-Api

Good TTS Fast API is a TTS playback on your computer via API with queing, best use for AI agents that would update you automously. 

## Setup Kokoro-FastAPI

Quickest Start Kokoro (docker run)
### the `latest` tag can be used, though it may have some unexpected bonus features which impact stability.
 Named versions should be pinned for your regular usage.
 Feedback/testing is always welcome

docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest # CPU, or:
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:latest  #NVIDIA GPU
## Install Uv
See https://docs.astral.sh/

## Running the server with UV installed:

``bash
uv run tts-server.py

``
## APi request


``curl

curl --request POST \
  --url http://192.168.1.100:8000/queue \
  --header 'Content-Type: application/json' \
  --data '{"text": "Hello, this is a test message from a curl request."}'

``