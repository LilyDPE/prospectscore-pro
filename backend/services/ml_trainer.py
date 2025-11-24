"""
Service d'Entraînement ML Auto-Apprenant
Utilise les données validées (DVF + feedback agents) pour améliorer le modèle de prédiction
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.dvf import TransactionDVF
from datetime import datetime
import logging
import numpy as np
import pickle
import os
from typing import Dict, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Vérifier si sklearn est disponible
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ scikit-learn non installé. Installer avec: pip install scikit-learn")
    SKLEARN_AVAILABLE = False

# Vérifier si xgboost est disponible
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ xgboost non installé (optionnel). Installer avec: pip install xgboost")
    XGBOOST_AVAILABLE = False


class MLTrainer:
    """
    Entraîne et améliore le modèle de propension à vendre
    """

    def __init__(self, db: Session):
        self.db = db
        self.model = None
        self.scaler = StandardScaler()
        self.model_dir = Path("/app/models")  # Docker volume path
        self.model_dir.mkdir(exist_ok=True)

        # Features utilisées pour la prédiction
        self.feature_names = [
            'duree_detention_estimee',
            'surface_reelle',
            'valeur_fonciere',
            'nombre_pieces',
            'classe_dpe_numeric',
            'contraintes_convergentes',
            'turnover_regulier_numeric',
            'cohorte_vente_active_numeric',
            'pic_marche_local_numeric',
            'valeur_m2',
            'age_transaction_jours'
        ]

    def load_latest_model(self) -> bool:
        """Charge le dernier modèle entraîné"""
        model_path = self.model_dir / "propensity_model_latest.pkl"
        scaler_path = self.model_dir / "scaler_latest.pkl"

        if model_path.exists() and scaler_path.exists():
            try:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info(f"✅ Modèle chargé depuis {model_path}")
                return True
            except Exception as e:
                logger.error(f"❌ Erreur chargement modèle: {e}")
                return False
        else:
            logger.warning("⚠️ Aucun modèle existant trouvé")
            return False

    def encode_dpe(self, dpe: str) -> int:
        """Convertit une classe DPE en valeur numérique"""
        mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7}
        return mapping.get(dpe, 4)  # Défaut = D

    def extract_features(self, transaction: TransactionDVF) -> np.array:
        """Extrait les features d'une transaction pour le ML"""
        age_jours = (datetime.now() - transaction.created_at).days if transaction.created_at else 0

        valeur_m2 = 0
        if transaction.surface_reelle and transaction.surface_reelle > 0:
            valeur_m2 = transaction.valeur_fonciere / transaction.surface_reelle

        features = [
            transaction.duree_detention_estimee or 0,
            transaction.surface_reelle or 0,
            transaction.valeur_fonciere or 0,
            transaction.nombre_pieces or 0,
            self.encode_dpe(transaction.classe_dpe),
            transaction.contraintes_convergentes or 0,
            1 if transaction.turnover_regulier else 0,
            1 if transaction.cohorte_vente_active else 0,
            1 if transaction.pic_marche_local else 0,
            valeur_m2,
            age_jours
        ]

        return np.array(features)

    def prepare_training_data(self) -> Tuple[np.array, np.array, List[TransactionDVF]]:
        """
        Prépare les données d'entraînement à partir des transactions validées

        Returns:
            (X, y, transactions) : Features, labels, et transactions sources
        """
        # Récupérer toutes les transactions avec statut validé
        validated = self.db.query(TransactionDVF).filter(
            and_(
                TransactionDVF.statut_final.isnot(None),  # Statut connu (0 ou 1)
                TransactionDVF.propensity_score.isnot(None),  # On avait fait une prédiction
            )
        ).all()

        logger.info(f"📚 {len(validated)} échantillons validés trouvés")

        if len(validated) < 50:
            raise ValueError(
                f"Pas assez de données validées pour entraîner ({len(validated)}). "
                "Minimum : 50 échantillons"
            )

        X_list = []
        y_list = []
        valid_transactions = []

        for trans in validated:
            try:
                features = self.extract_features(trans)
                X_list.append(features)
                y_list.append(trans.statut_final)  # 0 = pas vendu, 1 = vendu
                valid_transactions.append(trans)
            except Exception as e:
                logger.warning(f"⚠️ Erreur extraction features pour {trans.id}: {e}")
                continue

        X = np.array(X_list)
        y = np.array(y_list)

        # Distribution des classes
        vendus = np.sum(y == 1)
        pas_vendus = np.sum(y == 0)
        logger.info(
            f"📊 Distribution : {vendus} vendus ({vendus/len(y)*100:.1f}%), "
            f"{pas_vendus} pas vendus ({pas_vendus/len(y)*100:.1f}%)"
        )

        return X, y, valid_transactions

    def train_model(self, model_type: str = "random_forest") -> Dict:
        """
        Entraîne le modèle ML avec les données validées

        Args:
            model_type: 'random_forest', 'gradient_boosting', ou 'xgboost'

        Returns:
            Dict avec métriques de performance
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn n'est pas installé")

        logger.info("🧠 Début de l'entraînement du modèle ML...")

        # 1. Préparer les données
        X, y, transactions = self.prepare_training_data()

        # 2. Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"📊 Train: {len(X_train)} échantillons, Test: {len(X_test)} échantillons")

        # 3. Normalisation
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # 4. Choisir le modèle
        if model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                class_weight='balanced'  # Important pour données déséquilibrées
            )
        elif model_type == "gradient_boosting":
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
        elif model_type == "xgboost" and XGBOOST_AVAILABLE:
            scale_pos_weight = np.sum(y_train == 0) / np.sum(y_train == 1)
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                scale_pos_weight=scale_pos_weight,  # Balance classes
                random_state=42
            )
        else:
            logger.warning(f"⚠️ Modèle '{model_type}' non disponible, fallback sur RandomForest")
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)

        # 5. Entraînement
        logger.info(f"🎯 Entraînement du modèle {model_type}...")
        self.model.fit(X_train_scaled, y_train)

        # 6. Évaluation
        y_pred = self.model.predict(X_test_scaled)
        y_proba = self.model.predict_proba(X_test_scaled)[:, 1]  # Probabilités pour classe 1

        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5, scoring='f1')

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()

        logger.info(f"✅ Entraînement terminé !")
        logger.info(f"  Accuracy: {accuracy:.3f}")
        logger.info(f"  Precision: {precision:.3f}")
        logger.info(f"  Recall: {recall:.3f}")
        logger.info(f"  F1-Score: {f1:.3f}")
        logger.info(f"  CV F1 moyen: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
        logger.info(f"  True Positives: {tp}, False Positives: {fp}")
        logger.info(f"  True Negatives: {tn}, False Negatives: {fn}")

        # 7. Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            feature_importance = list(zip(self.feature_names, importances))
            feature_importance.sort(key=lambda x: x[1], reverse=True)

            logger.info("📊 Top 5 features importantes:")
            for name, importance in feature_importance[:5]:
                logger.info(f"  {name}: {importance:.4f}")

        # 8. Sauvegarder le modèle
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.model_dir / f"propensity_model_{timestamp}.pkl"
        scaler_path = self.model_dir / f"scaler_{timestamp}.pkl"

        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)

        # Copie en tant que "latest"
        latest_model = self.model_dir / "propensity_model_latest.pkl"
        latest_scaler = self.model_dir / "scaler_latest.pkl"
        with open(latest_model, 'wb') as f:
            pickle.dump(self.model, f)
        with open(latest_scaler, 'wb') as f:
            pickle.dump(self.scaler, f)

        logger.info(f"💾 Modèle sauvegardé : {model_path}")

        # 9. Marquer les transactions comme utilisées pour training
        for trans in transactions:
            trans.utilisé_pour_training = True
            trans.date_ajout_training = datetime.now()
        self.db.commit()

        return {
            'model_type': model_type,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'accuracy': round(accuracy, 3),
            'precision': round(precision, 3),
            'recall': round(recall, 3),
            'f1_score': round(f1, 3),
            'cv_f1_mean': round(cv_scores.mean(), 3),
            'cv_f1_std': round(cv_scores.std(), 3),
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'model_path': str(model_path),
            'timestamp': timestamp
        }

    def predict_propensity(self, transaction: TransactionDVF) -> Tuple[float, int]:
        """
        Prédit la propension à vendre avec le modèle ML

        Returns:
            (probabilité, score_0_100)
        """
        if self.model is None:
            raise RuntimeError("Aucun modèle chargé. Appelez load_latest_model() ou train_model()")

        features = self.extract_features(transaction)
        features_scaled = self.scaler.transform([features])

        proba = self.model.predict_proba(features_scaled)[0][1]  # Probabilité classe 1 (vendu)
        score = int(proba * 100)  # Convertir en score 0-100

        return proba, score


if __name__ == "__main__":
    """Test de l'entraînement ML"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        trainer = MLTrainer(db)

        # Entraîner le modèle
        result = trainer.train_model(model_type="random_forest")

        print("\n🎯 Résultats de l'entraînement:")
        for key, value in result.items():
            print(f"  {key}: {value}")

    finally:
        db.close()
