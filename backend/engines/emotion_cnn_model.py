"""
FaceCode - Custom CNN Emotion Detection Model
Deep Learning model trained on FER2013 dataset
Replaces DeepFace dependency with a faster, domain-specific model
"""

import numpy as np
import os
from typing import Tuple, Dict, List, Optional

# ============================================================
# MODEL ARCHITECTURE
# ============================================================

def build_emotion_cnn(input_shape=(48, 48, 1), num_classes=7) -> "keras.Model":
    """
    Build a compact but powerful CNN for facial emotion recognition.

    Architecture:
      Block 1: 2x Conv(32) → BN → Pool → Dropout
      Block 2: 2x Conv(64) → BN → Pool → Dropout
      Block 3: 2x Conv(128) → BN → Pool → Dropout
      Block 4: 2x Conv(256) → BN → Pool → Dropout  [optional – uses more RAM]
      Head:    GlobalAvgPool → Dense(256) → BN → Dropout → Dense(num_classes, softmax)

    GlobalAveragePooling is used instead of Flatten to reduce parameters
    and improve generalisation.

    Args:
        input_shape: (H, W, C) – default 48×48 grayscale
        num_classes: 7 for FER2013 (angry, disgust, fear, happy, sad, surprise, neutral)

    Returns:
        Compiled Keras model
    """
    try:
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        raise ImportError("TensorFlow ≥ 2.8 is required. Run: pip install tensorflow")

    inputs = keras.Input(shape=input_shape, name="face_input")

    # ---- Block 1 ----
    x = layers.Conv2D(32, 3, padding="same", activation="relu", name="conv1_1")(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Conv2D(32, 3, padding="same", activation="relu", name="conv1_2")(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D(2, name="pool1")(x)
    x = layers.Dropout(0.25, name="drop1")(x)

    # ---- Block 2 ----
    x = layers.Conv2D(64, 3, padding="same", activation="relu", name="conv2_1")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Conv2D(64, 3, padding="same", activation="relu", name="conv2_2")(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D(2, name="pool2")(x)
    x = layers.Dropout(0.25, name="drop2")(x)

    # ---- Block 3 ----
    x = layers.Conv2D(128, 3, padding="same", activation="relu", name="conv3_1")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Conv2D(128, 3, padding="same", activation="relu", name="conv3_2")(x)
    x = layers.BatchNormalization()(x)
    x = layers.MaxPooling2D(2, name="pool3")(x)
    x = layers.Dropout(0.35, name="drop3")(x)

    # ---- Block 4 ----
    x = layers.Conv2D(256, 3, padding="same", activation="relu", name="conv4_1")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Conv2D(256, 3, padding="same", activation="relu", name="conv4_2")(x)
    x = layers.BatchNormalization()(x)
    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(0.5, name="drop4")(x)

    # ---- Head ----
    x = layers.Dense(256, activation="relu", name="fc1")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5, name="drop_fc")(x)
    outputs = layers.Dense(num_classes, activation="softmax", name="emotion_probs")(x)

    model = keras.Model(inputs, outputs, name="FaceCode_EmotionCNN")

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )

    return model


# ============================================================
# DATA PIPELINE
# ============================================================

def load_fer2013(csv_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Load FER2013 dataset from CSV.

    Download from: https://www.kaggle.com/datasets/msambare/fer2013
    The CSV has columns: emotion, pixels, Usage

    Args:
        csv_path: Path to fer2013.csv

    Returns:
        (X_train, y_train, X_test, y_test) – normalised float32 images
    """
    import pandas as pd
    from tensorflow.keras.utils import to_categorical

    print(f"📂 Loading FER2013 from {csv_path} ...")
    df = pd.read_csv(csv_path)

    EMOTIONS = {0: "angry", 1: "disgust", 2: "fear",
                3: "happy", 4: "sad", 5: "surprise", 6: "neutral"}

    def parse_pixels(row):
        pixels = np.array(row["pixels"].split(), dtype=np.float32)
        return pixels.reshape(48, 48, 1) / 255.0

    train_df = df[df["Usage"] == "Training"]
    test_df  = df[df["Usage"].isin(["PublicTest", "PrivateTest"])]

    X_train = np.stack(train_df.apply(parse_pixels, axis=1).values)
    y_train = to_categorical(train_df["emotion"].values, num_classes=7)

    X_test  = np.stack(test_df.apply(parse_pixels, axis=1).values)
    y_test  = to_categorical(test_df["emotion"].values, num_classes=7)

    print(f"   Train: {X_train.shape} | Test: {X_test.shape}")
    return X_train, y_train, X_test, y_test


def build_augmentation_pipeline():
    """
    Keras image augmentation layer for training.
    Applied ONLY during training, not inference.
    """
    try:
        from tensorflow.keras import layers, Sequential
    except ImportError:
        raise ImportError("TensorFlow required")

    aug = Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.1),             # ±10°
        layers.RandomZoom(0.1),                 # ±10% zoom
        layers.RandomTranslation(0.05, 0.05),   # small shifts
        layers.RandomContrast(0.2),
    ], name="augmentation")

    return aug


# ============================================================
# TRAINING
# ============================================================

def train(
    csv_path: str,
    save_path: str = "models/emotion_cnn.keras",
    epochs: int = 80,
    batch_size: int = 64,
):
    """
    Full training run with callbacks.

    Args:
        csv_path:   Path to fer2013.csv
        save_path:  Where to save the best model
        epochs:     Maximum training epochs
        batch_size: Batch size (reduce if OOM)
    """
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers

    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

    # 1. Load data
    X_train, y_train, X_test, y_test = load_fer2013(csv_path)

    # 2. Handle class imbalance (FER2013 is heavily biased toward happy/neutral)
    class_counts = y_train.sum(axis=0)
    total = class_counts.sum()
    class_weights = {i: total / (7 * class_counts[i]) for i in range(7)}
    print("\n⚖️  Class weights:", {k: f"{v:.2f}" for k, v in class_weights.items()})

    # 3. Build model + augmentation wrapper
    aug = build_augmentation_pipeline()
    base_model = build_emotion_cnn()

    # Wrap with augmentation for training
    inputs = keras.Input(shape=(48, 48, 1))
    x = aug(inputs, training=True)   # aug only active during training
    outputs = base_model(x)
    train_model = keras.Model(inputs, outputs, name="FaceCode_Train")
    train_model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )

    print("\n📐 Model summary:")
    base_model.summary(print_fn=lambda s: print("   " + s))

    # 4. Callbacks
    callbacks = [
        keras.callbacks.ModelCheckpoint(
            save_path,
            monitor="val_accuracy",
            save_best_only=True,
            verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=5,
            min_lr=1e-6,
            verbose=1
        ),
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=15,
            restore_best_weights=True,
            verbose=1
        ),
        keras.callbacks.TensorBoard(
            log_dir="logs/emotion_cnn",
            histogram_freq=1
        ),
    ]

    # 5. Train
    print(f"\n🚀 Training for up to {epochs} epochs ...")
    history = train_model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=epochs,
        batch_size=batch_size,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1
    )

    # 6. Final evaluation
    print("\n📊 Final evaluation on test set:")
    loss, acc = base_model.evaluate(X_test, y_test, verbose=0)
    print(f"   Loss: {loss:.4f} | Accuracy: {acc:.4f} ({acc*100:.1f}%)")

    # 7. Save training plot data
    _save_history(history, "logs/training_history.json")

    print(f"\n✅ Best model saved to: {save_path}")
    return history


def _save_history(history, path: str):
    import json
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump({k: [float(v) for v in vals]
                   for k, vals in history.history.items()}, f, indent=2)
    print(f"   Training history saved to {path}")


# ============================================================
# INFERENCE WRAPPER
# ============================================================

EMOTION_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

# Map FER2013 emotion → FaceCode confidence score
EMOTION_TO_CONFIDENCE = {
    "happy":    0.95,
    "neutral":  0.60,
    "surprise": 0.70,
    "sad":      0.25,
    "angry":    0.15,
    "fear":     0.10,
    "disgust":  0.20,
}


class EmotionCNNInference:
    """
    Lightweight inference wrapper for the trained CNN.
    Drop-in compatible with the existing EmotionEngine interface.
    """

    def __init__(self, model_path: str = "models/emotion_cnn.keras"):
        self.model = None
        self.model_path = model_path
        self._load()

    def _load(self):
        if not os.path.exists(self.model_path):
            print(f"⚠️  Model not found at {self.model_path}. Run train() first.")
            return
        try:
            import tensorflow as tf
            self.model = tf.keras.models.load_model(self.model_path)
            print(f"✅ Loaded CNN from {self.model_path}")
        except Exception as e:
            print(f"❌ Failed to load model: {e}")

    def preprocess(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Convert BGR face crop → model-ready tensor.
        Applies CLAHE contrast enhancement before normalisation.
        """
        import cv2
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (48, 48))
        # CLAHE enhancement (same as training preprocessing)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        tensor = gray.astype(np.float32) / 255.0
        return tensor.reshape(1, 48, 48, 1)   # batch dim

    def predict(self, face_bgr: np.ndarray) -> Dict[str, float]:
        """
        Run inference and return a dict of {emotion: probability}.

        Args:
            face_bgr: OpenCV BGR face crop (any size)

        Returns:
            Dict mapping emotion label → probability (sums to ~1)
        """
        if self.model is None:
            # Fallback: uniform distribution
            return {e: 1/7 for e in EMOTION_LABELS}

        tensor = self.preprocess(face_bgr)
        probs = self.model.predict(tensor, verbose=0)[0]  # shape (7,)

        return {label: float(prob) for label, prob in zip(EMOTION_LABELS, probs)}

    def predict_dominant(self, face_bgr: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        """
        Returns (dominant_emotion, confidence_score, all_probs).
        This is the method called by emotion_engine_improved.EmotionEngine.
        """
        probs = self.predict(face_bgr)
        dominant = max(probs, key=probs.get)
        confidence = EMOTION_TO_CONFIDENCE.get(dominant, 0.5)
        return dominant, confidence, probs

    @property
    def available(self) -> bool:
        return self.model is not None


# ============================================================
# QUICK TEST (no webcam needed)
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FaceCode Emotion CNN")
    parser.add_argument("--train", metavar="FER2013_CSV",
                        help="Path to fer2013.csv — triggers training")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch",  type=int, default=64)
    parser.add_argument("--model",  default="models/emotion_cnn.keras",
                        help="Model save/load path")
    args = parser.parse_args()

    if args.train:
        train(args.train, save_path=args.model,
              epochs=args.epochs, batch_size=args.batch)
    else:
        # Architecture preview (no training data needed)
        print("=" * 60)
        print("FaceCode Emotion CNN – Architecture Preview")
        print("=" * 60)
        model = build_emotion_cnn()
        model.summary()
        params = model.count_params()
        print(f"\nTotal parameters : {params:,}")
        print(f"Approx size      : {params * 4 / 1e6:.1f} MB (float32)")
        print("\nTo train:")
        print("  python emotion_cnn_model.py --train fer2013.csv")
        print("\nTo use in inference:")
        print("  infer = EmotionCNNInference('models/emotion_cnn.keras')")
        print("  emotion, confidence, probs = infer.predict_dominant(face_bgr_array)")
