from openai import OpenAI
import os
import datetime
from playsound import playsound

import pyaudio
import wave


client = OpenAI()

# helper functions
def get_completion_from_messages(messages, model="gpt-3.5-turbo", temperature=0):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature, # this is the degree of randomness of the model's output
    )
    return response.choices[0].message.content

def speech_to_text(audio_file_path):
    audio_file = open(audio_file_path, "rb")
    transcript = client.audio.transcriptions.create(
    model="whisper-1", 
    file=audio_file, 
    response_format="text"
    )
    return transcript

def text_to_speech(text, output_file_path, voice="onyx"):
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text
    )
    response.stream_to_file(output_file_path)
    return output_file_path

def record_audio(file_name, duration=5, rate=44100, chunk=1024, format=pyaudio.paInt16, channels=1):
    audio = pyaudio.PyAudio()

    stream = audio.open(format=format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk)

    print("Recording...")
    frames = []

    for i in range(0, int(rate / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    print("Finished recording.")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    wave_file = wave.open(file_name, 'wb')
    wave_file.setnchannels(channels)
    wave_file.setsampwidth(audio.get_sample_size(format))
    wave_file.setframerate(rate)
    wave_file.writeframes(b''.join(frames))
    wave_file.close()
# END helper functions

# System prompt for the AI model
system_prompt = "You are Francois, an AI assistant living inside a vintage telephone. Be short an concise in your answer.\
                 Talk like a butler from the 18th century. Your master is a nobleman who is very busy and needs your help."



def main():

    # Create the directories to store the recordings
    dir_assistant = "recordings/assistant"
    if not os.path.exists(dir_assistant):
        os.makedirs(dir_assistant)

    dir_user = "recordings/user"
    if not os.path.exists(dir_user):
        os.makedirs(dir_user)

    # Initialize the conversation with the system prompt
    context = [ {'role':'system', 'content':system_prompt} ]

    # Continue the conversation
    while True:
        current_time = datetime.datetime.now()

        # Get the user's query
        # user_query_text = input("user: ")

        # Record audio to the file
        filename = current_time.strftime("%Y%m%d-%H%M%S") + ".wav"
        rec_full_path = os.path.join(dir_user, filename)
        record_audio(rec_full_path, duration=5)

        # Transcribe the audio
        user_query_text = speech_to_text(rec_full_path)
        print("user:", user_query_text)

        context.append({'role':'user', 'content':user_query_text})

        # If the user types "exit", then exit the conversation
        if user_query_text.lower() == "exit":
            break

        # Get the AI's response
        llm_response_text = get_completion_from_messages(context)
        context.append({'role':'assistant', 'content':llm_response_text})
        print("Francois: " + llm_response_text)

        # Convert the response to speech
        response_assitant_filename = current_time.strftime("%Y%m%d-%H%M%S") + ".mp3"
        response_assistant_full_path = os.path.join(dir_assistant, response_assitant_filename)

        audio_response_assistant = text_to_speech(llm_response_text, response_assistant_full_path)

        # Play the response
        playsound(audio_response_assistant)



if __name__ == "__main__":
    main()