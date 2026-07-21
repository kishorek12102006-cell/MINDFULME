import os
import sounddevice as sd
import wave
import librosa
import numpy as np
import joblib
from config import AUDIO_DEVICE_INDEX

# Load your trained AI brain (Note: .. goes up one folder from 'modules' to root)
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../voice_model.pkl')
model = joblib.load(MODEL_PATH)

class AudioProcessor:
    def __init__(self):
        self.sample_rate = 44100
        self.channels = 1
        self.device_index = AUDIO_DEVICE_INDEX

    def record_audio(self, filename="temp_scan.wav", duration=5):
        """Records a short audio clip."""
        # Save directly to root or a temp folder
        filepath = os.path.join(os.path.dirname(__file__), '../', filename)
        try:
            recording = sd.rec(int(duration * self.sample_rate), 
                               samplerate=self.sample_rate, 
                               channels=self.channels, 
                               device=self.device_index,
                               dtype='int16')
            sd.wait()
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(recording.tobytes())
            return filepath
        except Exception as e:
            print(f"❌ Microphone Error: {e}")
            return None

    def identify_speaker(self, filepath):
        """
        Uses the trained AI model to identify the speaker with a strict confidence threshold.
        """
        try:
            # Load and extract features
            y, sr = librosa.load(filepath, duration=5)
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
            features = np.mean(mfcc.T, axis=0).reshape(1, -1)
            
            # Predict
            prediction = model.predict(features)[0]
            confidence = np.max(model.predict_proba(features))
            
            # THE FIX: If the model isn't at least 80% sure, OR if it's just background, reject it.
            if confidence < 0.80 or prediction == "Background":
                print(f"🔍 AI detected noise/unknown: {prediction} (Confidence: {confidence:.2f})")
                return "Unknown", confidence
            
            print(f"🔍 AI identified: {prediction} (Confidence: {confidence:.2f})")
            return prediction, confidence
        except Exception as e:
            print(f"❌ AI Prediction Error: {e}")
            return "Unknown", 0.0

audio_sys = AudioProcessor()
