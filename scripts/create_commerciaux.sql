-- ============================================
-- Tables pour la gestion des commerciaux
-- ProspectScore Pro - Système d'assignation
-- ============================================

-- ==================== TABLE COMMERCIAUX ====================

CREATE TABLE IF NOT EXISTS commerciaux (
    id SERIAL PRIMARY KEY,

    -- Informations personnelles
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    telephone VARCHAR(20),

    -- Lien vers table users (optionnel)
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Zones géographiques assignées
    codes_postaux_assignes TEXT[] DEFAULT '{}',
    departements_assignes TEXT[] DEFAULT '{}',
    communes_assignees TEXT[] DEFAULT '{}',

    -- Configuration
    actif BOOLEAN DEFAULT TRUE,
    capacite_max_prospects INTEGER DEFAULT 100,
    min_propensity_score INTEGER DEFAULT 60,

    -- Statistiques
    nombre_prospects_assignes INTEGER DEFAULT 0,
    nombre_prospects_contactes INTEGER DEFAULT 0,
    nombre_rdv_obtenus INTEGER DEFAULT 0,
    nombre_mandats_obtenus INTEGER DEFAULT 0,

    -- Performance
    taux_conversion_contact FLOAT DEFAULT 0.0,
    taux_conversion_rdv FLOAT DEFAULT 0.0,
    taux_conversion_mandat FLOAT DEFAULT 0.0,

    -- Dernière activité
    derniere_assignation TIMESTAMP,
    dernier_contact TIMESTAMP,

    -- Métadonnées
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== TABLE PROSPECT_ASSIGNMENTS ====================

CREATE TABLE IF NOT EXISTS prospect_assignments (
    id SERIAL PRIMARY KEY,

    -- Références
    commercial_id INTEGER NOT NULL REFERENCES commerciaux(id) ON DELETE CASCADE,
    bien_id INTEGER NOT NULL REFERENCES biens_univers(id_bien) ON DELETE CASCADE,

    -- Score au moment de l'assignation
    propensity_score_at_assignment INTEGER,
    zone_type VARCHAR(20),

    -- Statut du prospect
    statut VARCHAR(50) DEFAULT 'NOUVEAU',
    -- NOUVEAU, EN_COURS, CONTACTE, RDV_PRIS, INTERESSE, MANDAT_OBTENU, PERDU, ABANDONNE

    priorite VARCHAR(20) DEFAULT 'MOYENNE',  -- HAUTE, MOYENNE, BASSE

    -- Actions commerciales
    date_assignation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_premier_contact TIMESTAMP,
    date_dernier_contact TIMESTAMP,
    nombre_tentatives_contact INTEGER DEFAULT 0,

    -- Résultats
    date_rdv TIMESTAMP,
    date_mandat TIMESTAMP,
    valeur_mandat FLOAT,

    -- Suivi
    notes_commercial TEXT,
    historique_actions JSONB DEFAULT '[]'::jsonb,

    -- Raison de perte
    raison_perte VARCHAR(255),

    -- Métadonnées
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== INDEX ====================

-- Index commerciaux
CREATE INDEX IF NOT EXISTS idx_commerciaux_email ON commerciaux(email);
CREATE INDEX IF NOT EXISTS idx_commerciaux_actif ON commerciaux(actif);
CREATE INDEX IF NOT EXISTS idx_commerciaux_codes_postaux ON commerciaux USING GIN(codes_postaux_assignes);
CREATE INDEX IF NOT EXISTS idx_commerciaux_departements ON commerciaux USING GIN(departements_assignes);

-- Index assignments
CREATE INDEX IF NOT EXISTS idx_assignments_commercial_id ON prospect_assignments(commercial_id);
CREATE INDEX IF NOT EXISTS idx_assignments_bien_id ON prospect_assignments(bien_id);
CREATE INDEX IF NOT EXISTS idx_assignments_statut ON prospect_assignments(statut);
CREATE INDEX IF NOT EXISTS idx_assignments_priorite ON prospect_assignments(priorite);
CREATE INDEX IF NOT EXISTS idx_assignments_date_assignation ON prospect_assignments(date_assignation);
CREATE INDEX IF NOT EXISTS idx_assignments_date_rdv ON prospect_assignments(date_rdv);
CREATE INDEX IF NOT EXISTS idx_assignments_propensity_score ON prospect_assignments(propensity_score_at_assignment);

-- Index composite pour recherches fréquentes
CREATE INDEX IF NOT EXISTS idx_assignments_commercial_statut ON prospect_assignments(commercial_id, statut);
CREATE INDEX IF NOT EXISTS idx_assignments_commercial_priorite ON prospect_assignments(commercial_id, priorite);

-- ==================== TRIGGERS ====================

-- Trigger pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_commerciaux_updated_at ON commerciaux;
CREATE TRIGGER trigger_update_commerciaux_updated_at
    BEFORE UPDATE ON commerciaux
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_assignments_updated_at ON prospect_assignments;
CREATE TRIGGER trigger_update_assignments_updated_at
    BEFORE UPDATE ON prospect_assignments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== VUES ====================

-- Vue statistiques globales
CREATE OR REPLACE VIEW v_commerciaux_stats AS
SELECT
    COUNT(*) as total_commerciaux,
    COUNT(*) FILTER (WHERE actif = TRUE) as commerciaux_actifs,
    COUNT(*) FILTER (WHERE actif = FALSE) as commerciaux_inactifs,
    SUM(nombre_prospects_assignes) as total_prospects_assignes,
    SUM(nombre_prospects_contactes) as total_prospects_contactes,
    SUM(nombre_rdv_obtenus) as total_rdv_obtenus,
    SUM(nombre_mandats_obtenus) as total_mandats_obtenus,
    AVG(taux_conversion_contact) as avg_taux_conversion_contact,
    AVG(taux_conversion_rdv) as avg_taux_conversion_rdv,
    AVG(taux_conversion_mandat) as avg_taux_conversion_mandat
FROM commerciaux;

-- Vue prospects par statut
CREATE OR REPLACE VIEW v_prospects_par_statut AS
SELECT
    statut,
    COUNT(*) as nombre,
    COUNT(*) FILTER (WHERE priorite = 'HAUTE') as priorite_haute,
    COUNT(*) FILTER (WHERE priorite = 'MOYENNE') as priorite_moyenne,
    COUNT(*) FILTER (WHERE priorite = 'BASSE') as priorite_basse,
    AVG(propensity_score_at_assignment) as avg_propensity_score
FROM prospect_assignments
GROUP BY statut
ORDER BY
    CASE statut
        WHEN 'NOUVEAU' THEN 1
        WHEN 'EN_COURS' THEN 2
        WHEN 'CONTACTE' THEN 3
        WHEN 'RDV_PRIS' THEN 4
        WHEN 'INTERESSE' THEN 5
        WHEN 'MANDAT_OBTENU' THEN 6
        WHEN 'PERDU' THEN 7
        WHEN 'ABANDONNE' THEN 8
    END;

-- Vue performance par commercial
CREATE OR REPLACE VIEW v_performance_commerciaux AS
SELECT
    c.id,
    c.prenom || ' ' || c.nom as nom_complet,
    c.actif,
    c.nombre_prospects_assignes,
    c.nombre_prospects_contactes,
    c.nombre_rdv_obtenus,
    c.nombre_mandats_obtenus,
    c.taux_conversion_contact,
    c.taux_conversion_rdv,
    c.taux_conversion_mandat,
    COUNT(pa.id) as total_assignments,
    COUNT(pa.id) FILTER (WHERE pa.statut = 'MANDAT_OBTENU') as mandats_obtenus,
    SUM(pa.valeur_mandat) as valeur_totale_mandats,
    AVG(pa.propensity_score_at_assignment) as avg_propensity_score
FROM commerciaux c
LEFT JOIN prospect_assignments pa ON c.id = pa.commercial_id
GROUP BY c.id, c.prenom, c.nom, c.actif, c.nombre_prospects_assignes,
         c.nombre_prospects_contactes, c.nombre_rdv_obtenus, c.nombre_mandats_obtenus,
         c.taux_conversion_contact, c.taux_conversion_rdv, c.taux_conversion_mandat
ORDER BY c.actif DESC, c.taux_conversion_mandat DESC;

-- ==================== FONCTIONS HELPER ====================

-- Fonction pour assigner automatiquement des prospects
CREATE OR REPLACE FUNCTION assign_prospects_automatique(
    p_commercial_id INTEGER,
    p_nombre_prospects INTEGER DEFAULT 10
)
RETURNS TABLE (
    bien_id INTEGER,
    adresse VARCHAR,
    code_postal VARCHAR,
    propensity_score INTEGER
) AS $$
DECLARE
    v_commercial RECORD;
    v_capacite_restante INTEGER;
BEGIN
    -- Récupérer le commercial
    SELECT * INTO v_commercial FROM commerciaux WHERE id = p_commercial_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Commercial % non trouvé', p_commercial_id;
    END IF;

    IF NOT v_commercial.actif THEN
        RAISE EXCEPTION 'Commercial % est inactif', p_commercial_id;
    END IF;

    -- Calculer la capacité restante
    v_capacite_restante := v_commercial.capacite_max_prospects - v_commercial.nombre_prospects_assignes;

    IF v_capacite_restante <= 0 THEN
        RAISE EXCEPTION 'Commercial % a atteint sa capacité maximale', p_commercial_id;
    END IF;

    -- Limiter le nombre à assigner
    p_nombre_prospects := LEAST(p_nombre_prospects, v_capacite_restante);

    -- Retourner les meilleurs prospects disponibles
    RETURN QUERY
    SELECT
        bu.id_bien,
        bu.adresse,
        bu.code_postal,
        bu.propensity_score
    FROM biens_univers bu
    WHERE
        bu.features_calculated = TRUE
        AND bu.propensity_score >= v_commercial.min_propensity_score
        AND (
            bu.code_postal = ANY(v_commercial.codes_postaux_assignes)
            OR bu.departement = ANY(v_commercial.departements_assignes)
        )
        AND NOT EXISTS (
            SELECT 1 FROM prospect_assignments pa
            WHERE pa.bien_id = bu.id_bien
            AND pa.statut IN ('NOUVEAU', 'EN_COURS', 'CONTACTE', 'RDV_PRIS', 'INTERESSE')
        )
    ORDER BY bu.propensity_score DESC
    LIMIT p_nombre_prospects;
END;
$$ LANGUAGE plpgsql;

-- ==================== GRANTS ====================

GRANT ALL PRIVILEGES ON commerciaux TO prospectscore;
GRANT ALL PRIVILEGES ON prospect_assignments TO prospectscore;
GRANT USAGE, SELECT ON SEQUENCE commerciaux_id_seq TO prospectscore;
GRANT USAGE, SELECT ON SEQUENCE prospect_assignments_id_seq TO prospectscore;
GRANT SELECT ON v_commerciaux_stats TO prospectscore;
GRANT SELECT ON v_prospects_par_statut TO prospectscore;
GRANT SELECT ON v_performance_commerciaux TO prospectscore;

-- ==================== COMMENTAIRES ====================

COMMENT ON TABLE commerciaux IS 'Commerciaux immobiliers avec zones assignées';
COMMENT ON TABLE prospect_assignments IS 'Assignation des prospects aux commerciaux';
COMMENT ON COLUMN commerciaux.codes_postaux_assignes IS 'Liste des codes postaux assignés au commercial';
COMMENT ON COLUMN prospect_assignments.statut IS 'NOUVEAU, EN_COURS, CONTACTE, RDV_PRIS, INTERESSE, MANDAT_OBTENU, PERDU, ABANDONNE';
COMMENT ON COLUMN prospect_assignments.priorite IS 'HAUTE, MOYENNE, BASSE';

-- ==================== AFFICHER LES STATS ====================

SELECT * FROM v_commerciaux_stats;

-- ==================== FIN DU SCRIPT ====================
