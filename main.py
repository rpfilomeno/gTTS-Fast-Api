import os
import io
import time
import threading
from gtts import gTTS
from playsound import playsound
import uvicorn
from fastapi import FastAPI, HTTPException, Request



# Create a FastAPI application instance.
app = FastAPI(
    title="Text-to-Speech API",
    description="A simple API that converts text to speech using gTTS."
)

@app.post("/queue")
async def queue(request: Request):

    data = await request.json()
    text = data.get("text")

    
    if not text:
        raise HTTPException(status_code=400, detail="json is required.")
    

    try:
        add_to_queue(text)
        position = len(text_queue)
        return { "message": f"Text added to queue position: {position} " }


    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during audio generation.")
    


from playsound import playsound

# A global queue to hold the text strings to be spoken.
text_queue = []
# A lock to ensure thread-safe access to the queue.
queue_lock = threading.Lock()

def play_text_to_speech(text: str):
    """
    Converts text to speech and plays the audio directly on the speaker.

    Args:
        text (str): The text to be converted and played.
    """
    # Use an in-memory buffer to store the audio data.
    audio_buffer = io.BytesIO()
    
    try:
        # Create a gTTS object.
        tts = gTTS(text=text, lang='en')
        tts.write_to_fp(audio_buffer)

        # To play the audio, we need to save it to a temporary file.
        temp_file_path = os.path.join(os.path.realpath(os.path.dirname(__file__)), 'temp_audio.mp3') 
        
        # Rewind the buffer to the beginning.
        audio_buffer.seek(0)

        # Save the audio data to the temporary file.
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(audio_buffer.read())
        
        print(f"Playing audio: '{text}'")
        
        # Play the audio file.
        playsound(temp_file_path,block=True)
        
    except Exception as e:
        print(f"An error occurred while playing audio: {e}")
        
    finally:
        # Clean up the temporary file after playback.
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print("Temporary audio file removed.")


def playback_worker():
    """
    The worker function that runs in a separate thread.
    It continuously checks the queue and plays the audio for any queued text.
    """
    while True:
        text_to_play = None
        
        # Acquire the lock to safely access the queue.
        with queue_lock:
            if text_queue:
                # Pop the first item from the queue.
                text_to_play = text_queue.pop(0)

        if text_to_play:
            play_text_to_speech(text_to_play)
        
        # Sleep for a short duration to prevent a busy-wait loop.
        time.sleep(0.5)


def add_to_queue(text: str):
    """
    Adds a new text string to the playback queue.

    Args:
        text (str): The text to be added.
    """
    # Acquire the lock to safely add a new item to the queue.
    with queue_lock:
        text_queue.append(text)
    print(f"Added to queue: '{text}'")

if __name__ == "__main__":
    # Start the playback worker thread. The `daemon=True` flag
    # ensures the thread will exit when the main program exits.
    worker_thread = threading.Thread(target=playback_worker, daemon=True)
    worker_thread.start()

    # The `uvicorn.run()` function is used to start the server.
    # The `app` argument refers to the FastAPI application instance.
    # The `--reload` flag enables auto-reloading when code changes are detected.
    uvicorn.run(app, host="0.0.0.0", port=8000)


