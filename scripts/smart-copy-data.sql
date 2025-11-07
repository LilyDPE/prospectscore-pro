-- ============================================
-- Script intelligent de copie des données
-- S'adapte automatiquement aux colonnes disponibles
-- ProspectScore Pro
-- ============================================

DO $$
DECLARE
    v_old_count INTEGER;
    v_new_count INTEGER;
    v_has_adresse BOOLEAN;
    v_has_zone_type BOOLEAN;
    v_has_propensity_score BOOLEAN;
    v_has_last_price BOOLEAN;
    v_copy_query TEXT;
BEGIN
    -- Vérifier si biens_univers_old existe
    IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'biens_univers_old') THEN
        RAISE NOTICE '❌ biens_univers_old n''existe pas';
        RETURN;
    END IF;

    -- Compter les enregistrements dans l'ancienne table
    EXECUTE 'SELECT COUNT(*) FROM biens_univers_old' INTO v_old_count;
    RAISE NOTICE '📊 % biens trouvés dans biens_univers_old', v_old_count;

    -- Vérifier quelles colonnes existent dans biens_univers_old
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'biens_univers_old' AND column_name = 'adresse'
    ) INTO v_has_adresse;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'biens_univers_old' AND column_name = 'zone_type'
    ) INTO v_has_zone_type;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'biens_univers_old' AND column_name = 'propensity_score'
    ) INTO v_has_propensity_score;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'biens_univers_old' AND column_name = 'last_price'
    ) INTO v_has_last_price;

    RAISE NOTICE '🔍 Colonnes détectées:';
    RAISE NOTICE '   - adresse: %', v_has_adresse;
    RAISE NOTICE '   - zone_type: %', v_has_zone_type;
    RAISE NOTICE '   - propensity_score: %', v_has_propensity_score;
    RAISE NOTICE '   - last_price: %', v_has_last_price;

    -- Vider la table destination
    TRUNCATE TABLE biens_univers RESTART IDENTITY CASCADE;
    RAISE NOTICE '✓ Table biens_univers vidée';

    -- Construire la requête de copie adaptée
    v_copy_query := 'INSERT INTO biens_univers (';

    -- Colonnes de base (toujours présentes normalement)
    v_copy_query := v_copy_query || 'code_postal, commune, departement, type_local, surface_reelle, nombre_pieces, latitude, longitude, geom';

    -- Ajouter adresse si elle existe
    IF v_has_adresse THEN
        v_copy_query := v_copy_query || ', adresse';
    END IF;

    -- Ajouter les colonnes ML si elles existent
    IF v_has_zone_type THEN
        v_copy_query := v_copy_query || ', zone_type';
    END IF;

    IF v_has_propensity_score THEN
        v_copy_query := v_copy_query || ', propensity_score, features_calculated';
    END IF;

    IF v_has_last_price THEN
        v_copy_query := v_copy_query || ', last_price';
    END IF;

    v_copy_query := v_copy_query || ', created_at, updated_at) SELECT ';

    -- Répéter les colonnes pour le SELECT
    v_copy_query := v_copy_query || 'code_postal, commune, departement, type_local, surface_reelle, nombre_pieces, latitude, longitude, geom';

    IF v_has_adresse THEN
        v_copy_query := v_copy_query || ', adresse';
    END IF;

    IF v_has_zone_type THEN
        v_copy_query := v_copy_query || ', zone_type';
    END IF;

    IF v_has_propensity_score THEN
        v_copy_query := v_copy_query || ', propensity_score, (propensity_score IS NOT NULL AND propensity_score > 0)';
    END IF;

    IF v_has_last_price THEN
        v_copy_query := v_copy_query || ', last_price';
    END IF;

    v_copy_query := v_copy_query || ', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM biens_univers_old';

    -- Exécuter la copie
    RAISE NOTICE '🔄 Exécution de la copie...';
    EXECUTE v_copy_query;

    -- Vérifier le résultat
    SELECT COUNT(*) FROM biens_univers INTO v_new_count;

    RAISE NOTICE '✅ Copie terminée: % / % biens', v_new_count, v_old_count;

    IF v_new_count = v_old_count THEN
        RAISE NOTICE '🎉 Tous les biens ont été copiés avec succès!';
    ELSE
        RAISE WARNING '⚠️  Seulement % biens copiés sur % disponibles', v_new_count, v_old_count;
    END IF;

END $$;

-- Afficher les statistiques finales
SELECT
    COUNT(*) as total_biens,
    COUNT(*) FILTER (WHERE latitude IS NOT NULL) as geolocalises,
    COUNT(*) FILTER (WHERE code_postal IS NOT NULL) as avec_code_postal,
    COUNT(*) FILTER (WHERE adresse IS NOT NULL) as avec_adresse,
    COUNT(*) FILTER (WHERE zone_type IS NOT NULL) as avec_zone_type,
    COUNT(*) FILTER (WHERE propensity_score IS NOT NULL AND propensity_score > 0) as avec_propensity_score,
    COUNT(*) FILTER (WHERE features_calculated = TRUE) as features_calculees
FROM biens_univers;

-- ============================================
-- FIN DU SCRIPT
-- ============================================
