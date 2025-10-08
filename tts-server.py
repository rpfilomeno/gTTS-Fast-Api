#!/usr/bin/env -S uv run --script
# /// script
#dependencies = ["uvicorn","fastapi","openai", "pygame"]
# ///
import io
import re
import sys
import time
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from requests.exceptions import RequestException
import logging
from pygame import mixer
from openai import OpenAI




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
        return { "message": f"Added to queue position: {position}." }


    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during audio generation.")
    




def play_text_to_speech(text: str, max_retries=120, delay_seconds=30):

    for attempt in range(max_retries):

        try:
            mp3_fp = io.BytesIO() # Create an in-memory binary stream

            start_time = time.perf_counter()
  
            #tts = gTTS(text=text, lang='en')
            #tts.write_to_fp(mp3_fp) # Write the audio data to the BytesIO object


            text_chunks = split_text_smartly(text, max_len=1000)
        
            for chunk in text_chunks:

                client = OpenAI(
                    base_url="http://localhost:8880/v1", api_key="not-needed"
                )

                with client.audio.speech.with_streaming_response.create(
                    model="kokoro",
                    voice="af_sky+af_bella", #single or multiple voicepack combo
                    input=chunk,
                ) as response:
                    for chunk in response.iter_bytes():
                        mp3_fp.write(chunk)
                
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





def split_text_smartly(text, max_len=1000):
    """
    Splits long text into chunks under a maximum length, prioritizing
    paragraph breaks and then natural sentence-ending punctuation.

    Args:
        text (str): The long string of text to be split.
        max_len (int): The maximum desired length for each chunk.

    Returns:
        list: A list of text chunks (strings).
    """
    if not text:
        return []

    chunks = []
    current_text = text

    while len(current_text) > max_len:
        # 1. Search for a good splitting point within the max_len limit.
        #    The range to search is from the end of the max_len down to 80% of max_len,
        #    to avoid making chunks unnecessarily short.
        search_end = max_len
        search_start = int(max_len * 0.8) # Look for a break in the last 20% of the chunk

        # Get the sub-string to examine for a break
        sub_string = current_text[:search_end]

        # Priority 1: Paragraph break (two or more newlines)
        # We look for the *last* occurrence of a paragraph break (\n\n or \r\n\r\n etc.)
        # within the valid search range.
        # re.compile(r'(\n{2,}|\r\n\r\n|\r{2,})', re.DOTALL) is robust for various newlines
        paragraph_breaks = list(re.finditer(r'(\n{2,}|\r\n\r\n|\r{2,})', sub_string))
        
        split_index = -1
        
        # Check paragraph breaks in reverse to find the latest one within the window
        for match in reversed(paragraph_breaks):
            if match.start() >= search_start:
                # Found a paragraph break within the preferred window
                # Use the end of the break as the split point to include the break in the chunk
                split_index = match.end()
                break
        
        if split_index != -1:
            # Found a good paragraph break
            chunk = current_text[:split_index]
            # Strip trailing whitespace and newlines, but preserve internal ones
            chunks.append(chunk.rstrip())
            current_text = current_text[split_index:].lstrip()
            continue

        # Priority 2: Natural stop word/Sentence-ending punctuation
        # If no paragraph break is found, look for the last period, question mark,
        # or exclamation mark followed by a space, newline, or end-of-string.
        # This regex looks for: [.?!] followed by optional quote/paren, and then [space/newline/end]
        sentence_breaks = list(re.finditer(r'([.?!]["\'\)]*(\s+|$))', sub_string))

        split_index = -1
        
        # Check sentence breaks in reverse to find the latest one within the window
        for match in reversed(sentence_breaks):
            if match.start() >= search_start:
                # Found a sentence break within the preferred window
                # Use the end of the match as the split point (includes the space/newline)
                split_index = match.end()
                break

        if split_index != -1:
            # Found a good sentence break
            chunk = current_text[:split_index]
            chunks.append(chunk.rstrip())
            current_text = current_text[split_index:].lstrip()
            continue
            
        # Fallback: If no natural break is found in the preferred window (rare for text > 1000)
        # split at the max_len boundary. This should only happen for extremely long,
        # unpunctuated runs of text.
        chunk = current_text[:max_len]
        chunks.append(chunk.rstrip())
        current_text = current_text[max_len:].lstrip()

    # Add the remainder if it's left
    if current_text:
        chunks.append(current_text.rstrip())

    return chunks


def convert_streamed_response_to_bytesio(streamed_response):
    """
    Converts a streamed binary API response to an io.BytesIO object.

    Args:
        streamed_response: An iterable object representing the streamed binary response,
                           e.g., the result of requests.get(url, stream=True).iter_content().

    Returns:
        An io.BytesIO object containing the full binary content of the response.
    """
    buffer = io.BytesIO()
    for chunk in streamed_response:
        buffer.write(chunk)
    buffer.seek(0)  # Reset the buffer's position to the beginning
    return buffer

if __name__ == "__main__":
    # Start the playback worker thread. The `daemon=True` flag
    # ensures the thread will exit when the main program exits.
    worker_thread = threading.Thread(target=playback_worker, daemon=True)
    worker_thread.start()

    # The `uvicorn.run()` function is used to start the server.
    # The `app` argument refers to the FastAPI application instance.
    # The `--reload` flag enables auto-reloading when code changes are detected.
    uvicorn.run(app, host="0.0.0.0", port=7070)


