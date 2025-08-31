# gTTS-Fast-Api

gTTS playback on your computer via API with queing, best use for AI agents that would update you automously. 


Design consideration: Not using concurrent requst to google to avoid being blocked.

``curl

curl --request POST \
  --url http://192.168.1.100:8000/queue \
  --header 'Content-Type: application/json' \
  --data '{"text": "Hello, this is a test message from a curl request."}'

``