import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { Add } from '@mui/icons-material';
import { api } from '../utils/api';

function ProspectList() {
  const navigate = useNavigate();
  const [prospects, setProspects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Filtres
  const [filters, setFilters] = useState({
    priority: '',
    status: '',
    postal_code: '',
    min_score: '',
  });

  useEffect(() => {
    fetchProspects();
  }, [filters]);

  const fetchProspects = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filters.priority) params.priority = filters.priority;
      if (filters.status) params.status = filters.status;
      if (filters.postal_code) params.postal_code = filters.postal_code;
      if (filters.min_score) params.min_score = parseFloat(filters.min_score);

      const response = await api.get('/prospects', { params });
      setProspects(response.data);
    } catch (err) {
      setError('Erreur lors du chargement des prospects');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters({ ...filters, [field]: value });
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusLabel = (status) => {
    const labels = {
      new: 'Nouveau',
      contacted: 'Contacté',
      interested: 'Intéressé',
      qualified: 'Qualifié',
      lost: 'Perdu',
    };
    return labels[status] || status;
  };

  const columns = [
    {
      field: 'score',
      headerName: 'Score',
      width: 90,
      renderCell: (params) => (
        <Box
          sx={{
            backgroundColor: 'secondary.main',
            color: 'primary.main',
            borderRadius: 1,
            px: 1.5,
            py: 0.5,
            fontWeight: 'bold',
          }}
        >
          {params.value}
        </Box>
      ),
    },
    {
      field: 'priority',
      headerName: 'Priorité',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value === 'high' ? 'Haute' : params.value === 'medium' ? 'Moyenne' : 'Basse'}
          color={getPriorityColor(params.value)}
          size="small"
        />
      ),
    },
    {
      field: 'address',
      headerName: 'Adresse',
      width: 250,
      flex: 1,
    },
    {
      field: 'postal_code',
      headerName: 'Code Postal',
      width: 120,
    },
    {
      field: 'city',
      headerName: 'Ville',
      width: 150,
    },
    {
      field: 'property_type',
      headerName: 'Type',
      width: 120,
      valueFormatter: (params) =>
        params.value === 'maison' ? 'Maison' : 'Appartement',
    },
    {
      field: 'surface',
      headerName: 'Surface',
      width: 100,
      valueFormatter: (params) => `${params.value} m²`,
    },
    {
      field: 'dpe_score',
      headerName: 'DPE',
      width: 80,
      renderCell: (params) =>
        params.value ? (
          <Chip
            label={params.value}
            size="small"
            color={['F', 'G'].includes(params.value) ? 'error' : 'default'}
          />
        ) : (
          '-'
        ),
    },
    {
      field: 'status',
      headerName: 'Statut',
      width: 120,
      renderCell: (params) => (
        <Chip label={getStatusLabel(params.value)} size="small" variant="outlined" />
      ),
    },
  ];

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <div>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Prospects
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Liste de tous vos prospects vendeurs
          </Typography>
        </div>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => navigate('/add-prospect')}
        >
          Ajouter
        </Button>
      </Box>

      {/* Filtres */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Filtres
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Priorité</InputLabel>
                <Select
                  value={filters.priority}
                  label="Priorité"
                  onChange={(e) => handleFilterChange('priority', e.target.value)}
                >
                  <MenuItem value="">Toutes</MenuItem>
                  <MenuItem value="high">Haute</MenuItem>
                  <MenuItem value="medium">Moyenne</MenuItem>
                  <MenuItem value="low">Basse</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Statut</InputLabel>
                <Select
                  value={filters.status}
                  label="Statut"
                  onChange={(e) => handleFilterChange('status', e.target.value)}
                >
                  <MenuItem value="">Tous</MenuItem>
                  <MenuItem value="new">Nouveau</MenuItem>
                  <MenuItem value="contacted">Contacté</MenuItem>
                  <MenuItem value="interested">Intéressé</MenuItem>
                  <MenuItem value="qualified">Qualifié</MenuItem>
                  <MenuItem value="lost">Perdu</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Code postal"
                value={filters.postal_code}
                onChange={(e) => handleFilterChange('postal_code', e.target.value)}
                placeholder="75001"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label="Score minimum"
                value={filters.min_score}
                onChange={(e) => handleFilterChange('min_score', e.target.value)}
                placeholder="50"
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          
          {loading ? (
            <Box display="flex" justifyContent="center" p={4}>
              <CircularProgress />
            </Box>
          ) : (
            <div style={{ height: 600, width: '100%' }}>
              <DataGrid
                rows={prospects}
                columns={columns}
                pageSize={25}
                rowsPerPageOptions={[10, 25, 50, 100]}
                disableSelectionOnClick
                onRowClick={(params) => navigate(`/prospects/${params.id}`)}
                sx={{
                  '& .MuiDataGrid-row': {
                    cursor: 'pointer',
                    '&:hover': {
                      backgroundColor: 'rgba(180, 228, 52, 0.05)',
                    },
                  },
                }}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

export default ProspectList;
