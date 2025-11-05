"""Dynamic ML-based false positive filter that learns from past audits."""

import json
import pathlib
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class DynamicMLFilter:
    """Self-improving false positive filter using ML."""
    
    def __init__(
        self,
        model_path: Optional[pathlib.Path] = None,
        training_data_path: Optional[pathlib.Path] = None
    ):
        """Initialize ML filter.
        
        Args:
            model_path: Path to saved model (load if exists)
            training_data_path: Path to training data directory
        """
        if not ML_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for ML filter. "
                "Install with: pip install scikit-learn joblib"
            )
        
        if model_path is None:
            model_path = pathlib.Path.home() / ".config" / "ollmcp" / "ml_filter.pkl"
        
        if training_data_path is None:
            training_data_path = pathlib.Path.home() / ".config" / "ollmcp" / "training_data"
        
        self.model_path = pathlib.Path(model_path)
        self.training_data_path = pathlib.Path(training_data_path)
        self.training_data_path.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = [
            "ai_intent_score",
            "embedding_similarity",
            "static_confirmed",
            "business_logic_validated",
            "confidence_score",
            "severity_numeric"  # Critical=5, High=4, etc.
        ]
        
        self._load_model()
    
    def _load_model(self) -> None:
        """Load saved model if exists."""
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                print(f"✓ Loaded ML model from {self.model_path}")
            except Exception as e:
                print(f"Warning: Could not load model: {e}")
                self._init_default_model()
        else:
            self._init_default_model()
    
    def _init_default_model(self) -> None:
        """Initialize default model."""
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
    
    def extract_features(self, finding: Dict[str, Any]) -> np.ndarray:
        """Extract features from finding.
        
        Args:
            finding: Finding dictionary
            
        Returns:
            Feature vector
        """
        severity_map = {
            "Critical": 5,
            "High": 4,
            "Medium": 3,
            "Low": 2,
            "Info": 1
        }
        
        features = [
            finding.get("ai_intent_score", 0.0),
            finding.get("max_embedding_similarity", 0.0),
            1.0 if finding.get("static_confirmed", False) else 0.0,
            1.0 if finding.get("business_logic_validated", False) else 0.0,
            finding.get("confidence", 0.0),
            severity_map.get(finding.get("severity", "Info"), 1)
        ]
        
        return np.array(features).reshape(1, -1)
    
    def predict(self, finding: Dict[str, Any]) -> Tuple[bool, float]:
        """Predict if finding is false positive.
        
        Args:
            finding: Finding to classify
            
        Returns:
            (is_false_positive, confidence)
        """
        if self.model is None:
            # Fallback to rule-based if no model
            confidence = finding.get("confidence", 0.0)
            return (confidence < 0.7, 1.0 - confidence)
        
        features = self.extract_features(finding)
        features_scaled = self.scaler.transform(features)
        
        prediction = self.model.predict(features_scaled)[0]
        probability = self.model.predict_proba(features_scaled)[0]
        
        is_false_positive = prediction == 1  # 1 = false positive
        confidence = probability[1] if is_false_positive else probability[0]
        
        return (is_false_positive, float(confidence))
    
    def add_training_example(
        self,
        finding: Dict[str, Any],
        is_false_positive: bool
    ) -> None:
        """Add training example from human feedback.
        
        Args:
            finding: Finding dictionary
            is_false_positive: Human-labeled false positive status
        """
        features = self.extract_features(finding)
        label = 1 if is_false_positive else 0
        
        # Save to training data
        example = {
            "features": features.flatten().tolist(),
            "label": label,
            "finding": finding
        }
        
        # Append to training file
        training_file = self.training_data_path / "examples.jsonl"
        with open(training_file, 'a') as f:
            f.write(json.dumps(example) + '\n')
    
    def train(self) -> Dict[str, Any]:
        """Train model on collected training data.
        
        Returns:
            Training metrics
        """
        training_file = self.training_data_path / "examples.jsonl"
        
        if not training_file.exists():
            return {
                "error": "No training data found",
                "status": "no_data"
            }
        
        # Load training data
        X = []
        y = []
        
        with open(training_file, 'r') as f:
            for line in f:
                example = json.loads(line)
                X.append(example["features"])
                y.append(example["label"])
        
        if len(X) < 10:
            return {
                "error": f"Not enough training data ({len(X)} examples, need at least 10)",
                "status": "insufficient_data",
                "examples": len(X)
            }
        
        X = np.array(X)
        y = np.array(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        # Save model
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)
        
        return {
            "status": "success",
            "train_accuracy": float(train_score),
            "test_accuracy": float(test_score),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "model_path": str(self.model_path)
        }
    
    def filter_findings(
        self,
        findings: List[Dict[str, Any]],
        confidence_threshold: float = 0.7
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Filter findings using ML model.
        
        Args:
            findings: List of findings
            confidence_threshold: Minimum confidence to filter
            
        Returns:
            (valid_findings, false_positives)
        """
        valid = []
        false_positives = []
        
        for finding in findings:
            is_fp, confidence = self.predict(finding)
            
            finding["ml_filter_confidence"] = confidence
            finding["ml_predicted_fp"] = is_fp
            
            if is_fp and confidence >= confidence_threshold:
                false_positives.append(finding)
            else:
                valid.append(finding)
        
        return valid, false_positives

