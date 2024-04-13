# Upcycled Vintage Telephone Project

This project aims to repurpose an old rotary dial telephone to be a more natural, non-intrusive and stylish interface to the digital world. Microphone is mechanically disconnected if handset is not in use.



## Dream use cases
### Smart home control

Pick up the phone-> Say turn off all the lights -> Hang up phone while smiling -> (light are turning off)

### Voice Assistant

Ask any random question you desperately want the answer -> it tells you the answer-> deep exhale

## Running the AI Voice Assistant

To run the `talk_with_an_ai.py` script, follow these steps:

1. Ensure you have Python installed on your system.
2. Install the required dependencies by running `pip install -r requirements.txt`.
3. Run the script using the command `python talk_with_an_ai.py` or using Docker as described below.
4. Speak into the microphone after the "Recording..." prompt.
5. The AI will respond to your query with a voice message.

### Using Docker

To build the Docker image and run the container, follow these steps:

1. Build the Docker image:
   ```
   docker build -t upcycled-telephone .
   ```
2. Run the container from the image:
   ```
   docker run -it --rm --name upcycled-telephone-instance upcycled-telephone
   ```
   Note: The `-it` flag is used to run the container in interactive mode and allocate a pseudo-TTY, which is necessary for the script to accept audio input.

Ask about the temperature outside -> it tells you that it is X degrees -> happiness

## Useful resources


## Useful resources

* Two part breakdown series on the mechanical and electronic parts of the original telephone [[1]](https://dodlithr.blogspot.com/2015/04/how-dial-phone-works.html#more), [[2]](https://dodlithr.blogspot.com/2015/05/how-dial-phone-works-22.html)

* Similar open-source projects

    * [Rotary-gpt:](https://github.com/tcz/rotary-gpt) Rotary phone is connected to a VoIP converter(Grandstream HT801), which feeds the data to a Raspberry Pi.
    * [RaspberryPi-DialTelephone:](https://github.com/CrazyRobMiles/RaspberryPi-DialTelephone) A Raspberry Pi Zero 2 is used to receive messages or control the bell through a web interface.