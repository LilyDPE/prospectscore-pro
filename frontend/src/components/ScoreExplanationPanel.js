/**
 * ScoreExplanationPanel.js
 * Panneau latéral affiché au clic sur un bien dans SearchByCP.
 * Explique visuellement pourquoi un bien a un score élevé ou faible.
 *
 * Props:
 *   bien       — objet bien sélectionné (depuis l'API /analyze/{cp})
 *   secteurStats — objet stats du secteur retourné par l'API (optionnel)
 *   onClose    — callback fermeture
 */

import React from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Divider,
  LinearProgress,
  Tooltip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

// URL de l'observatoire DPE officiel ADEME — recherche par bien
const ADEME_DPE_URL = 'https://observatoire-dpe-audit.ademe.fr/pub/recherche-bien';

// URL de l'app 2A Immo Prospection — boîtage & prospection terrain
const SMARTBOITAGE_URL = 'https://lilydpe.github.io/2A-Immo-Prospection/';

// ─── Config priorité ────────────────────────────────────────────────────────
const PRIORITY_CONFIG = {
  URGENT: { color: '#c62828', bg: '#ffebee', label: 'URGENT', barColor: '#c62828' },
  HIGH:   { color: '#e65100', bg: '#fff3e0', label: 'HIGH',   barColor: '#e65100' },
  MEDIUM: { color: '#f9a825', bg: '#fffde7', label: 'MEDIUM', barColor: '#f9a825' },
  LOW:    { color: '#2e7d32', bg: '#e8f5e9', label: 'LOW',    barColor: '#2e7d32' },
  NONE:   { color: '#757575', bg: '#f5f5f5', label: '—',      barColor: '#9e9e9e' },
};

// ─── Catégorisation des raisons ──────────────────────────────────────────────
// Transforme une chaîne de raison (ex: "DPE G → Interdiction location 2025")
// en un objet signal { icon, label, desc, type: 'positive'|'negative'|'neutral' }
function categorizeRaison(raison) {
  const r = raison.toLowerCase();

  // Signaux positifs — augmentent la probabilité de vente
  if (r.includes('pic statistique') || r.includes('sweet spot') || r.includes('cohorte') && r.includes('revente')) {
    return { icon: '⏳', type: 'positive', label: 'Cycle de revente', desc: raison };
  }
  if (r.includes('pic de marché') || r.includes('arbitrage optimal') || r.includes('fenêtre d\'arbitrage')) {
    return { icon: '📈', type: 'positive', label: 'Pic de marché', desc: raison.replace(/^📈\s*/, '') };
  }
  if (r.includes('cohorte active') || r.includes('propriétés similaires vendent') || r.includes('jumeaux')) {
    return { icon: '📊', type: 'positive', label: 'Effet cohorte', desc: raison.replace(/^📊\s*/, '') };
  }
  if (r.includes('investisseur actif') || r.includes('turnover régulier')) {
    return { icon: '🔄', type: 'positive', label: 'Investisseur actif', desc: raison.replace(/^🔄\s*/, '') };
  }
  if (r.includes('cycle de revente tardif') || r.includes('fenêtre active')) {
    return { icon: '⏳', type: 'positive', label: 'Fenêtre active', desc: raison };
  }
  if (r.includes('entrée dans cycle')) {
    return { icon: '⏳', type: 'neutral', label: 'Début de cycle', desc: raison };
  }
  if (r.includes('hausse') && r.includes('momentum')) {
    return { icon: '📈', type: 'positive', label: 'Marché en hausse', desc: raison.replace(/^📈\s*/, '') };
  }
  if (r.includes('propriétaire professionnel') || r.includes('sci') || r.includes('société probable')) {
    return { icon: '🏢', type: 'positive', label: 'Propriétaire professionnel', desc: raison.replace(/^🏢\s*/, '') };
  }
  if (r.includes('transmission patrimoniale') || r.includes('succession probable')) {
    return { icon: '📜', type: 'neutral', label: 'Succession probable', desc: raison };
  }

  // Signaux négatifs / contraintes
  if (r.includes('dpe') && (r.includes('interdiction') || r.includes('f') || r.includes('g'))) {
    return { icon: '⚠️', type: 'negative', label: 'Passoire thermique', desc: raison };
  }
  if (r.includes('taxe foncière') || r.includes('charge lourde')) {
    return { icon: '💸', type: 'negative', label: 'Charge fiscale élevée', desc: raison };
  }
  if (r.includes('travaux') && r.includes('nécessaires')) {
    return { icon: '🔧', type: 'negative', label: 'Vétusté probable', desc: raison };
  }
  if (r.includes('marché restreint') || r.includes('prix') && r.includes('difficulté')) {
    return { icon: '🏷️', type: 'negative', label: 'Prix élevé', desc: raison };
  }

  // Signaux neutres / contraintes convergentes
  if (r.includes('contraintes convergentes') || r.includes('⚠️')) {
    return { icon: '⚠️', type: 'negative', label: 'Contraintes multiples', desc: raison.replace(/^⚠️\s*/, '') };
  }
  if (r.includes('hors standard') || r.includes('difficile à commercialiser') || r.includes('atypique')) {
    return { icon: '🏠', type: 'neutral', label: 'Surface atypique', desc: raison };
  }
  if (r.includes('marché stable')) {
    return { icon: '📈', type: 'neutral', label: 'Marché stable', desc: raison.replace(/^📈\s*/, '') };
  }

  // Fallback générique
  return { icon: '•', type: 'neutral', label: 'Signal détecté', desc: raison };
}

// ─── Couleurs par type de signal ─────────────────────────────────────────────
const SIGNAL_STYLE = {
  positive: { border: '#a7f3d0', bg: '#f0fdf4', valueBg: '#dcfce7', valueColor: '#15803d' },
  negative: { border: '#fca5a5', bg: '#fef2f2', valueBg: '#fee2e2', valueColor: '#b91c1c' },
  neutral:  { border: '#e5e7eb', bg: '#f9fafb', valueBg: '#e5e7eb', valueColor: '#4b5563' },
};

// ─── Composant SignalCard ─────────────────────────────────────────────────────
function SignalCard({ signal }) {
  const style = SIGNAL_STYLE[signal.type] || SIGNAL_STYLE.neutral;
  return (
    <Box sx={{
      display: 'flex',
      gap: 1.5,
      alignItems: 'flex-start',
      border: `1px solid ${style.border}`,
      bgcolor: style.bg,
      borderRadius: 2,
      p: 1.5,
    }}>
      <Typography sx={{ fontSize: '1.25rem', lineHeight: 1.2, mt: '1px' }}>{signal.icon}</Typography>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" fontWeight={700} color="text.primary" sx={{ lineHeight: 1.3 }}>
          {signal.label}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.3, lineHeight: 1.4 }}>
          {signal.desc}
        </Typography>
      </Box>
    </Box>
  );
}

// ─── Composant principal ──────────────────────────────────────────────────────
export default function ScoreExplanationPanel({ bien, secteurStats, onClose }) {
  if (!bien) return null;

  const cfg = PRIORITY_CONFIG[bien.contact_priority] || PRIORITY_CONFIG.NONE;
  const pct = Math.round((bien.prob_sell_6m || 0) * 100);

  // Catégoriser toutes les raisons
  const raisons = Array.isArray(bien.propensity_raisons) ? bien.propensity_raisons : [];
  const signals = raisons.map(categorizeRaison);
  const positives = signals.filter(s => s.type === 'positive').length;
  const negatives = signals.filter(s => s.type === 'negative').length;

  const urgenceLabel = {
    URGENT: 'Probabilité très élevée de mise en vente dans les 6 mois',
    HIGH:   'Probabilité élevée de mise en vente dans les 6 mois',
    MEDIUM: 'Probabilité modérée de mise en vente',
    LOW:    'Faible probabilité de mise en vente à court terme',
    NONE:   'Aucun signal de vente détecté',
  }[bien.contact_priority] || '';

  return (
    <Box sx={{
      width: { xs: '100%', md: 380 },
      flexShrink: 0,
      bgcolor: 'white',
      borderLeft: { md: '1px solid #e5e7eb' },
      borderTop: { xs: '1px solid #e5e7eb', md: 'none' },
      display: 'flex',
      flexDirection: 'column',
      overflowY: 'auto',
      maxHeight: { xs: 'none', md: '100%' },
    }}>
      {/* ── En-tête ── */}
      <Box sx={{ p: 2, pb: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}>
          <Box sx={{ flex: 1, pr: 1 }}>
            <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.25 }}>
              {bien.adresse}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {bien.type_local}
              {bien.surface ? ` · ${bien.surface} m²` : ''}
              {bien.pieces ? ` · ${bien.pieces} pièces` : ''}
              {bien.commune ? ` · ${bien.commune}` : ''}
            </Typography>
          </Box>
          <IconButton size="small" onClick={onClose} sx={{ mt: -0.5, mr: -0.5 }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      <Divider />

      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>

        {/* ── Jauge de score ── */}
        <Box sx={{
          background: 'linear-gradient(135deg, #1a1a2e 0%, #2d3561 100%)',
          borderRadius: 2,
          p: 2,
          color: 'white',
          display: 'flex',
          gap: 2,
          alignItems: 'center',
        }}>
          <Box sx={{ textAlign: 'center', minWidth: 60 }}>
            <Typography sx={{ fontSize: '2.4rem', fontWeight: 900, lineHeight: 1, color: cfg.barColor }}>
              {pct}
            </Typography>
            <Typography sx={{ fontSize: '0.7rem', opacity: 0.6, letterSpacing: 1 }}>%</Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Chip
              label={cfg.label}
              size="small"
              sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 800, fontSize: '0.7rem', mb: 0.5 }}
            />
            <Typography sx={{ fontSize: '0.75rem', opacity: 0.75, lineHeight: 1.35, mb: 1 }}>
              {urgenceLabel}
            </Typography>
            <Tooltip title={`Score P6 : ${pct}%`} placement="bottom" arrow>
              <LinearProgress
                variant="determinate"
                value={pct}
                sx={{
                  height: 5,
                  borderRadius: 99,
                  bgcolor: 'rgba(255,255,255,0.2)',
                  '& .MuiLinearProgress-bar': { bgcolor: cfg.barColor, borderRadius: 99 },
                }}
              />
            </Tooltip>
          </Box>
        </Box>

        {/* ── Signaux explicatifs ── */}
        {signals.length > 0 ? (
          <Box>
            <Typography variant="caption" fontWeight={700} color="text.secondary"
              sx={{ display: 'block', textTransform: 'uppercase', letterSpacing: 0.5, mb: 1 }}>
              Pourquoi ce score ?
              {positives > 0 && (
                <Box component="span" sx={{ ml: 1, color: '#15803d' }}>
                  {positives} signal{positives > 1 ? 's' : ''} positif{positives > 1 ? 's' : ''}
                </Box>
              )}
              {negatives > 0 && (
                <Box component="span" sx={{ ml: 1, color: '#b91c1c' }}>
                  · {negatives} contrainte{negatives > 1 ? 's' : ''}
                </Box>
              )}
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
              {signals.map((signal, i) => (
                <SignalCard key={i} signal={signal} />
              ))}
            </Box>
          </Box>
        ) : (
          <Box sx={{ p: 2, bgcolor: '#f9fafb', borderRadius: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" fontStyle="italic">
              Aucun signal disponible — lancez un Recalcul P6 pour générer les explications.
            </Typography>
          </Box>
        )}

        {/* ── Contexte marché ── */}
        {secteurStats && (
          <Box sx={{ bgcolor: '#f8f9fb', borderRadius: 2, p: 1.5 }}>
            <Typography variant="caption" fontWeight={700} color="text.secondary"
              sx={{ display: 'block', textTransform: 'uppercase', letterSpacing: 0.5, mb: 1 }}>
              Contexte secteur
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              {[
                { label: 'Ventes 12 mois', value: secteurStats.ventes_12m ?? '—' },
                { label: 'Détention moy.', value: secteurStats.detention_moy ? `${secteurStats.detention_moy} ans` : '—' },
                { label: 'URGENT', value: secteurStats.urgent ?? '—' },
                { label: 'HIGH', value: secteurStats.high ?? '—' },
              ].map(({ label, value }) => (
                <Box key={label}>
                  <Typography variant="caption" color="text.disabled" sx={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                    {label}
                  </Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {value}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        )}

        {/* ── Infos supplémentaires ── */}
        <Box sx={{ bgcolor: '#f8f9fb', borderRadius: 2, p: 1.5 }}>
          <Typography variant="caption" fontWeight={700} color="text.secondary"
            sx={{ display: 'block', textTransform: 'uppercase', letterSpacing: 0.5, mb: 1 }}>
            Informations du bien
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0.75 }}>
            {[
              { label: 'Dernière vente', value: bien.date_mutation || '—' },
              { label: 'Détention', value: bien.duree_detention != null ? `${bien.duree_detention} ans` : '—' },
              { label: "Prix d'achat", value: bien.prix ? `${(bien.prix / 1000).toFixed(0)}k€` : '—' },
              { label: '€/m²', value: bien.prix_m2 ? `${Number(bien.prix_m2).toFixed(0)} €` : '—' },
              { label: 'Score brut', value: bien.propensity_score != null ? `${bien.propensity_score}/100` : '—' },
            ].map(({ label, value }) => (
              <Box key={label}>
                <Typography variant="caption" color="text.disabled" sx={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                  {label}
                </Typography>
                <Typography variant="body2" fontWeight={600} sx={{ lineHeight: 1.3 }}>
                  {value}
                </Typography>
              </Box>
            ))}

            {/* DPE avec lien vers l'observatoire ADEME */}
            <Box sx={{ gridColumn: '1 / -1' }}>
              <Typography variant="caption" color="text.disabled" sx={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                DPE
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.25 }}>
                {bien.classe_dpe ? (
                  <Chip
                    label={`Classe ${bien.classe_dpe}`}
                    size="small"
                    sx={{
                      fontWeight: 700,
                      fontSize: '0.7rem',
                      height: 20,
                      bgcolor: ['F', 'G'].includes(bien.classe_dpe) ? '#fee2e2' : ['D', 'E'].includes(bien.classe_dpe) ? '#fef9c3' : '#dcfce7',
                      color:   ['F', 'G'].includes(bien.classe_dpe) ? '#b91c1c' : ['D', 'E'].includes(bien.classe_dpe) ? '#854d0e' : '#15803d',
                    }}
                  />
                ) : (
                  <Typography variant="body2" fontWeight={600} color="text.secondary">Non renseigné</Typography>
                )}
                <Tooltip title="Recherche pré-remplie sur l'observatoire ADEME" placement="top" arrow>
                  <Box
                    component="a"
                    href={`${ADEME_DPE_URL}?adresse=${encodeURIComponent(
                      [bien.adresse, bien.code_postal, bien.commune].filter(Boolean).join(' ')
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 0.25,
                      fontSize: '0.7rem',
                      color: '#1976d2',
                      textDecoration: 'none',
                      fontWeight: 500,
                      '&:hover': { textDecoration: 'underline' },
                    }}
                  >
                    Voir DPE ADEME
                    <OpenInNewIcon sx={{ fontSize: '0.75rem' }} />
                  </Box>
                </Tooltip>
                <Tooltip title="Copier l'adresse" placement="top" arrow>
                  <Box
                    component="span"
                    onClick={() => navigator.clipboard.writeText(
                      [bien.adresse, bien.code_postal, bien.commune].filter(Boolean).join(' ')
                    )}
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      fontSize: '0.7rem',
                      color: '#9ca3af',
                      cursor: 'pointer',
                      ml: 0.5,
                      '&:hover': { color: '#374151' },
                    }}
                  >
                    📋
                  </Box>
                </Tooltip>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* ── Horizon ── */}
        {bien.propensity_timeframe && (
          <Box sx={{
            border: `1px solid ${cfg.barColor}40`,
            bgcolor: `${cfg.barColor}08`,
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}>
            <Typography sx={{ fontSize: '1.1rem' }}>🎯</Typography>
            <Typography variant="body2" fontWeight={600} sx={{ color: cfg.color }}>
              {bien.propensity_timeframe}
            </Typography>
          </Box>
        )}

        {/* ── Lien SmartBoitage ── */}
        <Box
          component="a"
          href={SMARTBOITAGE_URL}
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1,
            p: 1.5,
            bgcolor: '#0f172a',
            color: 'white',
            borderRadius: 2,
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '0.82rem',
            transition: 'background 0.15s',
            '&:hover': { bgcolor: '#1e293b' },
          }}
        >
          <Typography sx={{ fontSize: '1rem', lineHeight: 1 }}>📬</Typography>
          Ouvrir 2A Immo Prospection
          <OpenInNewIcon sx={{ fontSize: '0.8rem', opacity: 0.7 }} />
        </Box>

        {/* ── Date dernière analyse ── */}
        {bien.derniere_analyse && (
          <Typography variant="caption" color="text.disabled" textAlign="center">
            Score calculé le {new Date(bien.derniere_analyse).toLocaleDateString('fr-FR', {
              day: '2-digit', month: 'long', year: 'numeric'
            })}
          </Typography>
        )}

      </Box>
    </Box>
  );
}
