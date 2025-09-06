import os
import io
import sys
import time
import threading
from gtts import gTTS
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from requests.exceptions import RequestException
import logging
from pygame import mixer




# A global queue to hold the text strings to be spoken.
text_queue = []
# A lock to ensure thread-safe access to the queue.
queue_lock = threading.Lock()

# create logger with 'spam_application'
logger = logging.getLogger("gtts.api")
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

mixer.init() # Initialize the pygame mixer


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
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during audio generation.")
    




def play_text_to_speech(text: str, max_retries=120, delay_seconds=30):

    for attempt in range(max_retries):

        try:
            mp3_fp = io.BytesIO() # Create an in-memory binary stream

            start_time = time.perf_counter()
  
            tts = gTTS(text=text, lang='en')
            tts.write_to_fp(mp3_fp) # Write the audio data to the BytesIO object
            mp3_fp.seek(0) # Rewind the stream to the beginning

            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            logger.debug(f"gtts generation took: {elapsed_time:.4f} seconds")

            speaker = mixer.Sound(mp3_fp)
            logger.debug(f"Playing audio: {speaker.get_length()} seconds")

            channel=speaker.play()
            while channel.get_busy():
                time.sleep(0.1)


            return True  # Indicate success

        except RequestException as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.error(f"Retrying in {delay_seconds} seconds...")
                time.sleep(delay_seconds)
            else:
                logger.error("Max retries reached. Failed to convert text to speech.")
                return False  # Indicate failure
        except Exception as e:
            logger.critical(f"An error occurred while playing audio: {e}")
            
        finally:
            logger.debug(f"Audio playback completed.")
                


def playback_worker():
    """
    The worker function that runs in a separate thread.
    It continuously checks the queue and plays the audio for any queued text.
    """
    while True:
        try:
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
        except Exception as e:
            logger.critical(f"Worker thread caught an unexpected error: {e}. Exiting thread.")
            exit(-1)
            #break # Exit the loop if a critical, unhandled exception occurs


def add_to_queue(text: str):
    """
    Adds a new text string to the playback queue.

    Args:
        text (str): The text to be added.
    """
    # Acquire the lock to safely add a new item to the queue.
    with queue_lock:
        text_queue.append(text)
    logger.debug(f"Added to queue: '{text}'")

if __name__ == "__main__":
    # Start the playback worker thread. The `daemon=True` flag
    # ensures the thread will exit when the main program exits.
    worker_thread = threading.Thread(target=playback_worker, daemon=True)
    worker_thread.start()

    # The `uvicorn.run()` function is used to start the server.
    # The `app` argument refers to the FastAPI application instance.
    # The `--reload` flag enables auto-reloading when code changes are detected.
    uvicorn.run(app, host="0.0.0.0", port=8000)


