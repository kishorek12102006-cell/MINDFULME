import os
import glob
import wave
import librosa
import numpy as np
import sounddevice as sd
from sklearn.metrics.pairwise import cosine_similarity
import modules.db_manager as db_manager
from config import AUDIO_DEVICE_INDEX

PROFILES_DIR = os.path.join(os.path.dirname(__file__), '../voice_profiles')
os.makedirs(PROFILES_DIR, exist_ok=True)

CONFIDENCE_THRESHOLD = 0.80  # Strict 80% similarity threshold
MIN_ENERGY_THRESHOLD = 0.002 # Calibrated energy floor for noise gating on USB mic

class AudioProcessor:
    def __init__(self):
        self.sample_rate = 44100
        self.channels = 1
        self.device_index = AUDIO_DEVICE_INDEX
        self.speaker_centroids = {}
        self.reload_profiles()

    def record_audio(self, filename="temp_scan.wav", duration=6):
        """Records an audio clip cleanly from the USB PnP Sound Device with fallback routing."""
        filepath = os.path.join(os.path.dirname(__file__), '../', filename)
        try:
            # Primary recording attempt using target device index
            try:
                recording = sd.rec(int(duration * self.sample_rate),
                                   samplerate=self.sample_rate,
                                   channels=self.channels,
                                   device=self.device_index,
                                   dtype='int16')
                sd.wait()
            except Exception as e:
                print(f"⚠️ Primary mic capture (index {self.device_index}) failed: {e}. Falling back to default system device...")
                recording = sd.rec(int(duration * self.sample_rate),
                                   samplerate=self.sample_rate,
                                   channels=self.channels,
                                   device=None,
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

    def extract_features(self, filepath):
        """Extracts 39-dim MFCC + Delta + Delta-Delta dynamic speech features."""
        try:
            y, sr = librosa.load(filepath, sr=16000, duration=6)

            # Noise Gate Validation
            rms = librosa.feature.rms(y=y)[0]
            if np.mean(rms) < MIN_ENERGY_THRESHOLD:
                print("🔍 Audio signal too quiet or silent.")
                return None

            # Trim silent edges
            y_trimmed, _ = librosa.effects.trim(y, top_db=20)
            if len(y_trimmed) < sr * 0.5:
                return None

            # Extract MFCCs + Velocity + Acceleration
            mfcc = librosa.feature.mfcc(y=y_trimmed, sr=sr, n_mfcc=13)
            delta = librosa.feature.delta(mfcc)
            delta2 = librosa.feature.delta(mfcc, order=2)

            feature_vec = np.hstack([
                np.mean(mfcc, axis=1),
                np.mean(delta, axis=1),
                np.mean(delta2, axis=1)
            ])
            return feature_vec
        except Exception as e:
            print(f"❌ Feature Extraction Error: {e}")
            return None

    def reload_profiles(self):
        """Re-syncs loaded profiles in memory with active SQLite records."""
        self.speaker_centroids = {}
        db_staff_rows = db_manager.get_all_staff()
        active_names = [s['name'].lower() for s in db_staff_rows]

        # Scan profile directory
        for profile_file in glob.glob(os.path.join(PROFILES_DIR, "*.npy")):
            speaker_name = os.path.splitext(os.path.basename(profile_file))[0].lower()
            if speaker_name in active_names:
                try:
                    self.speaker_centroids[speaker_name] = np.load(profile_file)
                except Exception as e:
                    print(f"❌ Error loading profile file for {speaker_name}: {e}")
            else:
                # Purge orphaned files from disk
                try:
                    os.remove(profile_file)
                    print(f"🧹 Purged orphaned voice profile: {profile_file}")
                except Exception:
                    pass

    def save_speaker_centroid(self, name, audio_paths):
        """Processes enrollment samples, averages their feature vectors, and saves .npy."""
        vectors = []
        for path in audio_paths:
            vec = self.extract_features(path)
            if vec is not None:
                vectors.append(vec)

        if not vectors:
            print(f"❌ Failed to enroll {name}: All audio samples invalid.")
            return False

        centroid = np.mean(vectors, axis=0)
        profile_path = os.path.join(PROFILES_DIR, f"{name.lower()}.npy")
        np.save(profile_path, centroid)
        self.reload_profiles()
        print(f"✅ Successfully created centroid model for '{name}' with {len(vectors)} samples.")
        return True

    def identify_speaker(self, filepath):
        """Performs dynamic speaker verification against active SQLite staff."""
        # Safeguard 1: Always force sync memory with database
        self.reload_profiles()

        # Safeguard 2: Zero registered staff in DB
        if not self.speaker_centroids:
            print("🔍 0 active staff members registered. Direct return: Unknown")
            return "Unknown", 0.0

        test_vec = self.extract_features(filepath)
        if test_vec is None:
            return "Unknown", 0.0

        best_match = "Unknown"
        highest_sim = 0.0

        # Cosine similarity matching
        for speaker_name, centroid in self.speaker_centroids.items():
            sim = cosine_similarity(test_vec.reshape(1, -1), centroid.reshape(1, -1))[0][0]
            if sim > highest_sim:
                highest_sim = float(sim)
                best_match = speaker_name

        # Safeguard 3: Enforce strict 80% confidence threshold
        if highest_sim >= CONFIDENCE_THRESHOLD:
            print(f"🔍 AI identified: {best_match.capitalize()} (Confidence: {highest_sim:.2f})")
            return best_match.capitalize(), highest_sim
        else:
            print(f"🔍 Rejected: Closest '{best_match}' with score {highest_sim:.2f} < {CONFIDENCE_THRESHOLD}")
            return "Unknown", highest_sim

audio_sys = AudioProcessor()
