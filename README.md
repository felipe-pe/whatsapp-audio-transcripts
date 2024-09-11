# WhatsApp Audio Transcripts

This Flask application provides a simple API for transcribing audio files, specifically designed for WhatsApp audio messages. It utilizes the powerful "Faster Whisper" model to convert audio into text, with support for the Portuguese language.

## Features:

Audio Transcription: Converts audio files (e.g., .wav, .mp3) to text using the Faster Whisper model.
Portuguese Language Support: Optimized for Portuguese audio.
Multiple Configurations: Allows fine-tuning through configurable parameters such as model size, beam search, and chunk length.
Flexible Output: Generates both .srt files and HTML outputs.



## Installation:

Before running the project, make sure to install all dependencies by following these steps:

1. **Clone the repository:**
    ```bash
    git clone https://github.com/felipe-pe/whatsapp-audio-transcripts.git
    cd whatsapp-audio-transcripts
    ```


## Setup the environment and dependencies:

Run the setup script to install necessary dependencies, including PyTorch, Flask, and other libraries.

  ```bash
  python setup.py
  Running the API:
  ```

To run the Flask API, use:
  ```bash
  python transcribe_basic.py
  ```
or for the version with timing:
  ```bash
  python transcribe_with_timing.py
  ```
or for the configurable version:
  ```bash
  python transcribe_configurable.py
  ```
This will start the Flask application on http://127.0.0.1:5502.

## API Endpoints:

Upload Audio for Transcription: This endpoint allows you to upload an audio file and receive the transcription as both .srt and .html formats.
Request:

### Method: POST
  URL: /upload
  Parameters:
  file: The audio file (e.g., .wav, .mp3).
  user_id: Unique identifier for the user.
  request_id: Unique identifier for the request.
  model (optional): Choose model size (small, medium, large-v2). Default is medium.
  beam_size (optional): The number of beams for beam search. Default is 5.
  chunk_length (optional): Length of the audio chunk in seconds. Default is 30.
  torch_dtype (optional): Set the precision type for torch, e.g., float32, float16.


#### cURL Examples:

##### Single-line cURL for basic use (no custom config):

  ```bash
  curl -X POST "http://127.0.0.1:5502/upload" \
    -F "file=@C:/path/to/audio.wav" \
    -F "user_id=123" \
    -F "request_id=abc123"
  ```
##### Multi-line cURL for advanced use (with custom configurations):

  ```bash
  curl -X POST "http://127.0.0.1:5502/upload" \
    -F "file=@C:/path/to/audio.wav" \
    -F "user_id=123" \
    -F "request_id=abc123" \
    -F "model=large-v2" \
    -F "beam_size=5" \
    -F "chunk_length=30" \
    -F "torch_dtype=float16"
  ```
###### Windows (PowerShell) cURL command:


  ```bash
  Invoke-RestMethod -Uri "http://127.0.0.1:5502/upload" -Method Post -FormData @{
    file = Get-Item -Path "C:\path\to\audio.wav"
    user_id = "123"
    request_id = "abc123"
    model = "large-v2"
    beam_size = "5"
    chunk_length = "30"
    torch_dtype = "float16"
  }
  ```
###### Get Transcriptions: To retrieve the transcription files (.srt, .html) for a given request:
###### Request:

  ```bash
  Method: GET
  URL: /transcriptions/<user_id>/<request_id>
  ```
###### Example:

  ```bash
  curl -X GET "http://127.0.0.1:5502/transcriptions/123/abc123"
  ```
This will return the transcription files in both .srt and .html formats.

List Transcriptions: To list all transcriptions for a user request:

###### Request:

Method: GET
  ```bash
  URL: /list_transcriptions/<user_id>/<request_id>
  ```
Example:

  ```bash
  curl -X GET "http://127.0.0.1:5502/list_transcriptions/123/abc123"
  ```
This will list all transcription files generated for the specified request.

#####Custom Configurations:

When using the configurable script (transcribe_configurable.py), you can fine-tune the transcription process by providing additional parameters such as:

Model Size: Select different models (small, medium, large-v2) based on accuracy and performance needs.
Beam Search: Set the number of beams for more accurate transcription.
Chunk Length: Define the length of audio chunks processed at a time.
Torch Data Type: Adjust precision to float16 for faster performance or float32 for higher accuracy.
Example cURL for Large Model with Advanced Settings:


  ```bash
  curl -X POST "http://127.0.0.1:5502/upload" \
    -F "file=@C:/path/to/audio.wav" \
    -F "user_id=456" \
    -F "request_id=xyz789" \
    -F "model=large-v2" \
    -F "beam_size=10" \
    -F "chunk_length=60" \
    -F "torch_dtype=float16"
  ```
This example demonstrates how to use the larger model (large-v2) with a higher beam size and chunk length for more accuracy.

## Example Workflow:

### Start the Flask server:

  ```bash
  python transcribe_configurable.py
  ```


### Upload an audio file for transcription:

  ```bash
  curl -X POST "http://127.0.0.1:5502/upload" \
    -F "file=@C:/path/to/audio.wav" \
    -F "user_id=123" \
    -F "request_id=abc123"
  ```
### Retrieve transcription files:

  ```bash
  curl -X GET "http://127.0.0.1:5502/transcriptions/123/abc123"
  ```
### List all transcriptions for a specific request:

  ```bash
  curl -X GET "http://127.0.0.1:5502/list_transcriptions/123/abc123"
  ```
