import io
from pydub import AudioSegment
from elevenlabs.client import ElevenLabs
from elevenlabs import play, stream
import time
from typing import Union, Iterator

# Replace 'your_api_key' with your actual ElevenLabs API key
ELEVEN_LABS_API_KEY = 'your_api_key'

# Instantiate the ElevenLabs client with the API key
client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)


def speak(text):
    # Generate the audio using the ElevenLabs client
    audio = client.generate(
        text=text,
        voice="Daniel",
        model="eleven_monolingual_v1"
    )

    # Play the audio
    play(audio)

def stream_audio(text):
    audio_stream = client.generate(
    text=text,
    stream=True
    )

    stream(audio_stream)

if __name__ == '__main__':
    sentence = 'Save me, I am in danger!'
    #speak(sentence)
    stream_audio(sentence)
    print('Done')
