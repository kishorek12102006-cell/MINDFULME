import os
import librosa
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib

def extract_features(file_path):
    # Load audio and extract MFCCs (the 'voiceprint')
    y, sr = librosa.load(file_path, duration=5)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
    # Average the MFCCs to get a single vector representing the voice
    return np.mean(mfcc.T, axis=0)

def train():
    X, y = [], []
    print("🚀 Starting training...")
    
    # Loop through the folders in the dataset directory
    dataset_dir = 'dataset'
    for person in os.listdir(dataset_dir):
        person_dir = os.path.join(dataset_dir, person)
        if os.path.isdir(person_dir):
            for file in os.listdir(person_dir):
                if file.endswith('.wav'):
                    path = os.path.join(person_dir, file)
                    print(f"Processing: {path}")
                    X.append(extract_features(path))
                    y.append(person)
    
    if not X:
        print("❌ No audio files found in dataset folder!")
        return

    # Train the "Brain"
    clf = RandomForestClassifier(n_estimators=100)
    clf.fit(X, y)
    
    # Save the model
    joblib.dump(clf, 'voice_model.pkl')
    print("✅ Model trained and saved as voice_model.pkl")

if __name__ == "__main__":
    train()
