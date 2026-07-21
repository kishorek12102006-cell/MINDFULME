import sounddevice as sd
import wave
import os
import time

def record_sample(name):
    # Setup directory
    folder = os.path.join('dataset', name)
    os.makedirs(folder, exist_ok=True)
    
    # Generate filename with timestamp
    filename = os.path.join(folder, f"{name}_{int(time.time())}.wav")
    
    print(f"\n🎙️ Recording for 5 seconds for '{name}'...")
    print("Speak clearly into the microphone...")
    
    # Record
    fs = 44100
    seconds = 5
    recording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    
    # Save
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(recording.tobytes())
        
    print(f"✅ Saved: {filename}")

if __name__ == "__main__":
    username = input("Enter the name of the person speaking: ")
    while True:
        record_sample(username)
        cont = input("Record another sample for this person? (y/n): ")
        if cont.lower() != 'y':
            break
