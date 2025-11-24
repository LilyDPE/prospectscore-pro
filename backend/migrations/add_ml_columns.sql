-- Migration: Ajout des colonnes pour Auto-Learning ML
-- Date: 2025-11-24
-- Description: Ajoute les colonnes nécessaires pour le système d'auto-apprentissage

-- Colonnes pour validation et feedback
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS statut_final INTEGER;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS date_validation TIMESTAMP;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS source_validation VARCHAR(50);
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS prix_vente_reel FLOAT;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS delai_vente_jours INTEGER;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS precision_prediction FLOAT;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS feedback_agent TEXT;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS contacted_at TIMESTAMP;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS utilisé_pour_training BOOLEAN DEFAULT FALSE;
ALTER TABLE transactions_dvf ADD COLUMN IF NOT EXISTS date_ajout_training TIMESTAMP;

-- Commentaires pour documentation
COMMENT ON COLUMN transactions_dvf.statut_final IS '0=Pas vendu, 1=Vendu confirmé, 2=En négociation';
COMMENT ON COLUMN transactions_dvf.source_validation IS 'DVF_API (ground truth), AGENT_FEEDBACK (rapide), WEB_SCRAPING';
COMMENT ON COLUMN transactions_dvf.prix_vente_reel IS 'Prix réel de vente si différent de valeur_fonciere';
COMMENT ON COLUMN transactions_dvf.delai_vente_jours IS 'Jours entre prédiction et vente effective';
COMMENT ON COLUMN transactions_dvf.precision_prediction IS 'Score 0-1 de précision de notre prédiction';
COMMENT ON COLUMN transactions_dvf.feedback_agent IS 'Notes de l''agent (raison refus, commentaires)';
COMMENT ON COLUMN transactions_dvf.contacted_at IS 'Date du premier contact avec le prospect';
COMMENT ON COLUMN transactions_dvf.utilisé_pour_training IS 'Échantillon déjà utilisé dans un entraînement ML';
COMMENT ON COLUMN transactions_dvf.date_ajout_training IS 'Date d''ajout au dataset d''entraînement';

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_statut_final ON transactions_dvf(statut_final);
CREATE INDEX IF NOT EXISTS idx_source_validation ON transactions_dvf(source_validation);
CREATE INDEX IF NOT EXISTS idx_date_validation ON transactions_dvf(date_validation);
CREATE INDEX IF NOT EXISTS idx_utilisé_training ON transactions_dvf(utilisé_pour_training);

-- Vue pour les données validées (prêtes pour training)
CREATE OR REPLACE VIEW ml_training_data AS
SELECT
    id,
    adresse,
    code_postal,
    commune,
    type_local,
    surface_reelle,
    nombre_pieces,
    valeur_fonciere,
    classe_dpe,
    duree_detention_estimee,
    contraintes_convergentes,
    turnover_regulier,
    cohorte_vente_active,
    pic_marche_local,
    propensity_score,
    statut_final,
    source_validation,
    delai_vente_jours,
    precision_prediction,
    utilisé_pour_training,
    date_mutation,
    created_at
FROM transactions_dvf
WHERE statut_final IS NOT NULL  -- Statut connu
  AND propensity_score IS NOT NULL;  -- On avait fait une prédiction

-- Vue pour les metrics ML
CREATE OR REPLACE VIEW ml_performance_metrics AS
SELECT
    source_validation,
    COUNT(*) as total_echantillons,
    COUNT(*) FILTER (WHERE statut_final = 1) as vendus,
    COUNT(*) FILTER (WHERE statut_final = 0) as pas_vendus,
    ROUND(AVG(precision_prediction), 3) as precision_moyenne,
    ROUND(AVG(delai_vente_jours) FILTER (WHERE statut_final = 1), 1) as delai_moyen_vente,
    COUNT(*) FILTER (WHERE utilisé_pour_training = true) as deja_utilisé_training,
    COUNT(*) FILTER (WHERE utilisé_pour_training = false) as nouveau_disponible
FROM transactions_dvf
WHERE statut_final IS NOT NULL
GROUP BY source_validation;

-- Fonction pour calculer l'accuracy du modèle actuel
CREATE OR REPLACE FUNCTION calculate_model_accuracy()
RETURNS TABLE (
    total_predictions INTEGER,
    true_positives INTEGER,
    false_positives INTEGER,
    true_negatives INTEGER,
    false_negatives INTEGER,
    accuracy FLOAT,
    precision FLOAT,
    recall FLOAT,
    f1_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH predictions AS (
        SELECT
            CASE
                WHEN propensity_score >= 75 THEN 1  -- Prédiction: Va vendre
                ELSE 0  -- Prédiction: Ne va pas vendre
            END as predicted,
            statut_final as actual
        FROM transactions_dvf
        WHERE statut_final IS NOT NULL
          AND propensity_score IS NOT NULL
    ),
    metrics AS (
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE predicted = 1 AND actual = 1) as tp,
            COUNT(*) FILTER (WHERE predicted = 1 AND actual = 0) as fp,
            COUNT(*) FILTER (WHERE predicted = 0 AND actual = 0) as tn,
            COUNT(*) FILTER (WHERE predicted = 0 AND actual = 1) as fn
        FROM predictions
    )
    SELECT
        total::INTEGER,
        tp::INTEGER,
        fp::INTEGER,
        tn::INTEGER,
        fn::INTEGER,
        ROUND((tp + tn)::NUMERIC / NULLIF(total, 0), 3) as accuracy,
        ROUND(tp::NUMERIC / NULLIF(tp + fp, 0), 3) as precision,
        ROUND(tp::NUMERIC / NULLIF(tp + fn, 0), 3) as recall,
        ROUND(2.0 * tp / NULLIF(2 * tp + fp + fn, 0), 3) as f1_score
    FROM metrics;
END;
$$ LANGUAGE plpgsql;

-- Logs
INSERT INTO migration_logs (migration_name, applied_at)
VALUES ('add_ml_columns', NOW())
ON CONFLICT DO NOTHING;

-- Afficher un résumé
SELECT 'Migration terminée!' as status,
       COUNT(*) as total_transactions,
       COUNT(*) FILTER (WHERE statut_final IS NOT NULL) as transactions_validées,
       COUNT(*) FILTER (WHERE utilisé_pour_training = true) as deja_en_training
FROM transactions_dvf;
