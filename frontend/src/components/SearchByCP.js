/**
 * SearchByCP.jsx
 * Page principale : saisie code postal → carte Leaflet + tableau MUI DataGrid
 * Triée par prob_sell_6m (P6) décroissant.
 *
 * Leaflet chargé via CDN (aucune dépendance npm supplémentaire).
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Chip,
  CircularProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Paper,
  Slider,
  Alert,
  Tooltip,
  Divider,
  Collapse,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import axios from 'axios';
import ScoreExplanationPanel from './ScoreExplanationPanel';

// ─── Config ────────────────────────────────────────────────────────────────────
const API_BASE = process.env.REACT_APP_API_URL || '';

const PRIORITY_CONFIG = {
  URGENT: { color: '#c62828', bg: '#ffebee', label: '🔴 URGENT' },
  HIGH:   { color: '#e65100', bg: '#fff3e0', label: '🟠 HIGH' },
  MEDIUM: { color: '#f9a825', bg: '#fffde7', label: '🟡 MEDIUM' },
  LOW:    { color: '#2e7d32', bg: '#e8f5e9', label: '🟢 LOW' },
  NONE:   { color: '#757575', bg: '#f5f5f5', label: '⚪ NONE' },
};

// ─── Hook : charge Leaflet depuis CDN ─────────────────────────────────────────
function useLeaflet() {
  const [L, setL] = useState(null);

  useEffect(() => {
    // Déjà chargé ?
    if (window.L) { setL(window.L); return; }

    // CSS Leaflet
    if (!document.getElementById('leaflet-css')) {
      const link = document.createElement('link');
      link.id = 'leaflet-css';
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }

    // JS Leaflet
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => setL(window.L);
    script.onerror = () => console.error('Impossible de charger Leaflet');
    document.head.appendChild(script);
  }, []);

  return L;
}

// ─── Composant Carte ──────────────────────────────────────────────────────────
function ProspectMap({ biens, L, onSelectBien }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);

  // Initialiser la carte une seule fois
  useEffect(() => {
    if (!L || !mapRef.current || mapInstanceRef.current) return;
    const map = L.map(mapRef.current, { zoomControl: true }).setView([46.8, 2.3], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);
    mapInstanceRef.current = map;
    // Nettoyage
    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [L]);

  // Mettre à jour les marqueurs quand les données changent
  useEffect(() => {
    if (!L || !mapInstanceRef.current) return;
    const map = mapInstanceRef.current;

    // Supprimer anciens marqueurs
    markersRef.current.forEach(m => map.removeLayer(m));
    markersRef.current = [];

    const withCoords = (biens || []).filter(b => b.latitude && b.longitude);
    if (withCoords.length === 0) return;

    // Recentrer la carte
    const latlngs = withCoords.map(b => [b.latitude, b.longitude]);
    map.fitBounds(L.latLngBounds(latlngs), { padding: [30, 30], maxZoom: 14 });

    withCoords.forEach(bien => {
      const cfg = PRIORITY_CONFIG[bien.contact_priority] || PRIORITY_CONFIG.NONE;
      const pct = Math.round((bien.prob_sell_6m || 0) * 100);

      const icon = L.divIcon({
        className: '',
        html: `<div style="
          width:16px;height:16px;border-radius:50%;
          background:${cfg.color};border:2.5px solid white;
          box-shadow:0 1px 5px rgba(0,0,0,0.45);
          cursor:pointer;
        " title="${pct}%"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      });

      const marker = L.marker([bien.latitude, bien.longitude], { icon })
        .addTo(map)
        .bindPopup(`
          <div style="font-family:sans-serif;min-width:180px">
            <b style="font-size:0.95rem">${bien.adresse || '—'}</b><br/>
            <span style="color:#555">${bien.commune || ''}</span><br/>
            <hr style="margin:4px 0"/>
            <b>P6 : </b><span style="color:${cfg.color};font-weight:700">${pct}%</span>
            &nbsp;<span style="font-size:0.8rem">${cfg.label}</span><br/>
            <b>Type : </b>${bien.type_local || '—'}<br/>
            <b>Surface : </b>${bien.surface ? bien.surface + ' m²' : '—'}<br/>
            <b>Dernière vente : </b>${bien.date_mutation || '—'}<br/>
            ${bien.prix ? `<b>Prix : </b>${(bien.prix / 1000).toFixed(0)}k€<br/>` : ''}
            ${bien.propensity_timeframe ? `<i style="color:#777;font-size:0.8rem">${bien.propensity_timeframe}</i>` : ''}
          </div>
        `);

      marker.on('click', () => onSelectBien && onSelectBien(bien));
      markersRef.current.push(marker);
    });
  }, [biens, L, onSelectBien]);

  if (!L) {
    return (
      <Box sx={{ height: 380, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#f5f5f5', borderRadius: 2 }}>
        <CircularProgress size={28} />
        <Typography sx={{ ml: 2, color: '#888' }}>Chargement de la carte…</Typography>
      </Box>
    );
  }

  return <div ref={mapRef} style={{ height: 380, width: '100%', borderRadius: 8 }} />;
}

// ─── Colonnes DataGrid ────────────────────────────────────────────────────────
const buildColumns = () => [
  {
    field: 'prob_sell_6m',
    headerName: 'P6',
    width: 80,
    sortable: true,
    renderCell: (p) => {
      const pct = Math.round((p.value || 0) * 100);
      const cfg = PRIORITY_CONFIG[p.row.contact_priority] || PRIORITY_CONFIG.NONE;
      return (
        <Box sx={{ fontWeight: 800, color: cfg.color, fontSize: '1.05rem', lineHeight: 1 }}>
          {pct}%
        </Box>
      );
    },
  },
  {
    field: 'contact_priority',
    headerName: 'Priorité',
    width: 115,
    renderCell: (p) => {
      const cfg = PRIORITY_CONFIG[p.value] || PRIORITY_CONFIG.NONE;
      return (
        <Chip
          label={cfg.label}
          size="small"
          sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 700, fontSize: '0.68rem', height: 22 }}
        />
      );
    },
  },
  { field: 'adresse', headerName: 'Adresse', flex: 1, minWidth: 180 },
  { field: 'type_local', headerName: 'Type', width: 115 },
  {
    field: 'surface',
    headerName: 'Surface',
    width: 90,
    renderCell: (p) => p.value ? `${p.value} m²` : '—',
  },
  {
    field: 'prix',
    headerName: 'Dernier prix',
    width: 120,
    renderCell: (p) => p.value ? `${(p.value / 1000).toFixed(0)}k€` : '—',
  },
  {
    field: 'prix_m2',
    headerName: '€/m²',
    width: 85,
    renderCell: (p) => p.value ? `${Number(p.value).toFixed(0)}€` : '—',
  },
  { field: 'date_mutation', headerName: 'Dernière vente', width: 130 },
  {
    field: 'duree_detention',
    headerName: 'Détention',
    width: 100,
    renderCell: (p) => p.value != null ? `${p.value} ans` : '—',
  },
  { field: 'classe_dpe', headerName: 'DPE', width: 65 },
  {
    field: 'propensity_timeframe',
    headerName: 'Horizon',
    width: 210,
    renderCell: (p) => (
      <span style={{ fontSize: '0.78rem', color: '#555' }}>{p.value || '—'}</span>
    ),
  },
];

// ─── Composant principal ───────────────────────────────────────────────────────
export default function SearchByCP() {
  // Filtres
  const [cp, setCp] = useState('');
  const [typeLocal, setTypeLocal] = useState('');
  const [priorite, setPriorite] = useState('');
  const [surfaceMin, setSurfaceMin] = useState('');
  const [surfaceMax, setSurfaceMax] = useState('');
  const [minP6, setMinP6] = useState(0);

  // État
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [selectedBien, setSelectedBien] = useState(null);
  const [recomputing, setRecomputing] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const L = useLeaflet();
  const columns = buildColumns();

  // ── Recherche ──────────────────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    const cpTrimmed = cp.trim();
    if (!cpTrimmed) { setError('Veuillez saisir un code postal.'); return; }

    setLoading(true);
    setError('');
    setData(null);
    setSelectedBien(null);

    try {
      const params = new URLSearchParams({ limit: 300, min_p6: minP6 });
      if (typeLocal) params.append('type_local', typeLocal);
      if (priorite) params.append('priorite', priorite);
      if (surfaceMin) params.append('surface_min', surfaceMin);
      if (surfaceMax) params.append('surface_max', surfaceMax);

      const token = localStorage.getItem('token');
      const res = await axios.get(`${API_BASE}/analyze/${cpTrimmed}?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 10000,
      });

      setData(res.data);
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Erreur lors de la recherche.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [cp, typeLocal, priorite, surfaceMin, surfaceMax, minP6]);

  // ── Recalcul modèle ────────────────────────────────────────────────────────
  const handleRecompute = async () => {
    if (!window.confirm('Lancer le recalcul P6 sur toute la base ?\n(Peut prendre plusieurs minutes)')) return;
    setRecomputing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${API_BASE}/recompute-model?limit=5000`, {}, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 300000, // 5 min max
      });
      alert(`✅ ${res.data.message}`);
      if (data) handleSearch(); // Rafraîchir les résultats
    } catch (e) {
      alert(`❌ Erreur : ${e.response?.data?.detail || e.message}`);
    } finally {
      setRecomputing(false);
    }
  };

  // ── Export CSV ─────────────────────────────────────────────────────────────
  const handleExportCSV = () => {
    if (!data?.biens?.length) return;
    const headers = [
      'Adresse', 'Commune', 'CP', 'Type', 'Surface (m²)',
      'Prix (€)', '€/m²', 'Date vente', 'Détention (ans)',
      'P6 (%)', 'Priorité', 'Horizon', 'DPE', 'Latitude', 'Longitude',
    ];
    const rows = data.biens.map(b => [
      b.adresse, b.commune, b.code_postal, b.type_local, b.surface,
      b.prix, b.prix_m2, b.date_mutation, b.duree_detention,
      Math.round((b.prob_sell_6m || 0) * 100),
      b.contact_priority, b.propensity_timeframe, b.classe_dpe,
      b.latitude, b.longitude,
    ]);
    const csv = [headers, ...rows]
      .map(r => r.map(v => `"${v ?? ''}"`).join(','))
      .join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prospects_${cp}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1400, mx: 'auto' }}>

      {/* ── En-tête ── */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h5" fontWeight={800} gutterBottom>
            🎯 Prospection par code postal
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Identifiez les biens les plus susceptibles d'être remis en vente dans les 6 prochains mois.
          </Typography>
        </Box>
        <Box sx={{ ml: 'auto' }}>
          <Tooltip title="Recalculer le score P6 sur toute la base (quelques minutes)">
            <Button
              variant="outlined"
              size="small"
              color="warning"
              startIcon={recomputing ? <CircularProgress size={14} /> : <RefreshIcon />}
              onClick={handleRecompute}
              disabled={recomputing}
            >
              {recomputing ? 'Calcul en cours…' : 'Recalculer P6'}
            </Button>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Barre de recherche ── */}
      <Paper sx={{ p: 2, mb: 2 }} elevation={2}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={3} md={2}>
            <TextField
              fullWidth
              label="Code postal"
              value={cp}
              onChange={e => setCp(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              size="small"
              placeholder="76260"
              inputProps={{ maxLength: 5 }}
            />
          </Grid>
          <Grid item xs={12} sm={2} md={1.5}>
            <Button
              fullWidth
              variant="contained"
              size="medium"
              onClick={handleSearch}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <SearchIcon />}
              sx={{ height: 40 }}
            >
              {loading ? 'Recherche…' : 'Analyser'}
            </Button>
          </Grid>
          <Grid item xs={12} sm="auto">
            <Button
              size="small"
              variant="text"
              color="inherit"
              endIcon={showFilters ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              onClick={() => setShowFilters(v => !v)}
              sx={{ color: '#666' }}
            >
              {showFilters ? 'Masquer filtres' : 'Filtres avancés'}
            </Button>
          </Grid>
        </Grid>

        {/* Filtres avancés */}
        <Collapse in={showFilters}>
          <Divider sx={{ my: 2 }} />
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={6} sm={3} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Type de bien</InputLabel>
                <Select value={typeLocal} label="Type de bien" onChange={e => setTypeLocal(e.target.value)}>
                  <MenuItem value="">Tous</MenuItem>
                  <MenuItem value="Maison">Maison</MenuItem>
                  <MenuItem value="Appartement">Appartement</MenuItem>
                  <MenuItem value="Local industriel. commercial ou assimilé">Local commercial</MenuItem>
                  <MenuItem value="Dépendance">Dépendance</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6} sm={3} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Priorité</InputLabel>
                <Select value={priorite} label="Priorité" onChange={e => setPriorite(e.target.value)}>
                  <MenuItem value="">Toutes</MenuItem>
                  <MenuItem value="URGENT">🔴 URGENT</MenuItem>
                  <MenuItem value="HIGH">🟠 HIGH</MenuItem>
                  <MenuItem value="MEDIUM">🟡 MEDIUM</MenuItem>
                  <MenuItem value="LOW">🟢 LOW</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6} sm={2} md={1.5}>
              <TextField
                fullWidth label="Surface min (m²)" value={surfaceMin}
                onChange={e => setSurfaceMin(e.target.value)}
                size="small" type="number" inputProps={{ min: 0 }}
              />
            </Grid>
            <Grid item xs={6} sm={2} md={1.5}>
              <TextField
                fullWidth label="Surface max (m²)" value={surfaceMax}
                onChange={e => setSurfaceMax(e.target.value)}
                size="small" type="number" inputProps={{ min: 0 }}
              />
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <Typography variant="caption" color="text.secondary" display="block">
                P6 minimum : <b>{Math.round(minP6 * 100)}%</b>
              </Typography>
              <Slider
                value={minP6}
                onChange={(_, v) => setMinP6(v)}
                min={0} max={0.9} step={0.05}
                size="small"
                marks={[{ value: 0, label: '0%' }, { value: 0.5, label: '50%' }, { value: 0.9, label: '90%' }]}
              />
            </Grid>
          </Grid>
        </Collapse>
      </Paper>

      {/* ── Erreur ── */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* ── Résultats ── */}
      {data && (
        <>
          {/* Chips stats */}
          <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            <Chip
              label={`${data.total} biens`}
              color="primary" variant="outlined" sx={{ fontWeight: 700 }}
            />
            {data.stats.urgent > 0 && (
              <Chip
                label={`🔴 ${data.stats.urgent} URGENT`}
                sx={{ bgcolor: '#ffebee', color: '#c62828', fontWeight: 700 }}
              />
            )}
            {data.stats.high > 0 && (
              <Chip
                label={`🟠 ${data.stats.high} HIGH`}
                sx={{ bgcolor: '#fff3e0', color: '#e65100', fontWeight: 700 }}
              />
            )}
            <Chip
              label={`📍 ${data.stats.avec_coords} géolocalisés`}
              variant="outlined" size="small"
            />
            {data.stats.scoring_ok < data.total && (
              <Chip
                label={`⚠️ ${data.total - data.stats.scoring_ok} sans score → lancez un Recalcul P6`}
                color="warning" variant="outlined" size="small"
              />
            )}
            <Button
              variant="outlined" size="small"
              startIcon={<DownloadIcon />}
              onClick={handleExportCSV}
              sx={{ ml: 'auto' }}
            >
              Export CSV
            </Button>
          </Box>

          {/* Carte */}
          <Paper elevation={2} sx={{ mb: 2, overflow: 'hidden', borderRadius: 2 }}>
            <ProspectMap
              biens={data.biens}
              L={L}
              onSelectBien={setSelectedBien}
            />
            <Box sx={{ px: 2, py: 0.8, bgcolor: '#fafafa', borderTop: '1px solid #eee', display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {Object.entries(PRIORITY_CONFIG).filter(([k]) => k !== 'NONE').map(([k, v]) => (
                <Box key={k} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.75rem' }}>
                  <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: v.color, border: '1.5px solid white', boxShadow: '0 0 2px rgba(0,0,0,0.3)' }} />
                  <span style={{ color: '#555' }}>{v.label}</span>
                </Box>
              ))}
            </Box>
          </Paper>

          {/* Layout principal : tableau + panneau d'explication côte à côte */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>

            {/* Tableau — rétrécit quand le panneau est ouvert */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Paper elevation={2} sx={{ borderRadius: 2 }}>
                <DataGrid
                  rows={data.biens}
                  columns={columns}
                  pageSize={25}
                  rowsPerPageOptions={[25, 50, 100]}
                  autoHeight
                  disableSelectionOnClick
                  onRowClick={(params) => setSelectedBien(params.row)}
                  getRowClassName={(params) =>
                    selectedBien && params.row.id === selectedBien.id ? 'selected-row' : ''
                  }
                  initialState={{
                    sorting: {
                      sortModel: [{ field: 'prob_sell_6m', sort: 'desc' }],
                    },
                  }}
                  sx={{
                    border: 'none',
                    '& .MuiDataGrid-row:hover': {
                      backgroundColor: '#eef2ff',
                      cursor: 'pointer',
                    },
                    '& .MuiDataGrid-row.selected-row': {
                      backgroundColor: '#eff6ff',
                      borderLeft: '3px solid #1976d2',
                    },
                    '& .MuiDataGrid-columnHeaders': {
                      backgroundColor: '#f5f5f5',
                      fontWeight: 700,
                    },
                    '& .MuiDataGrid-cell': {
                      borderBottom: '1px solid #f0f0f0',
                    },
                  }}
                />
              </Paper>
            </Box>

            {/* Panneau d'explication du score */}
            {selectedBien && (
              <Paper
                elevation={3}
                sx={{
                  borderRadius: 2,
                  overflow: 'hidden',
                  width: 380,
                  flexShrink: 0,
                  position: { xs: 'static', lg: 'sticky' },
                  top: { lg: 16 },
                  maxHeight: { lg: 'calc(100vh - 180px)' },
                  overflowY: 'auto',
                }}
              >
                <ScoreExplanationPanel
                  bien={selectedBien}
                  secteurStats={data?.stats}
                  onClose={() => setSelectedBien(null)}
                />
              </Paper>
            )}
          </Box>
        </>
      )}

      {/* État vide */}
      {!data && !loading && !error && (
        <Box sx={{ textAlign: 'center', mt: 8, color: '#aaa' }}>
          <Typography variant="h2" sx={{ mb: 2 }}>🔍</Typography>
          <Typography variant="h6" color="text.secondary">
            Saisissez un code postal pour analyser les biens du secteur
          </Typography>
          <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
            Les biens sont triés par probabilité de revente dans les 6 prochains mois
          </Typography>
        </Box>
      )}
    </Box>
  );
}
