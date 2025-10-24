import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  Divider,
} from '@mui/material';
import { ArrowBack, Edit, Save, Delete } from '@mui/icons-material';
import { api } from '../utils/api';

function ProspectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [prospect, setProspect] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({});

  useEffect(() => {
    fetchProspect();
  }, [id]);

  const fetchProspect = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/prospects/${id}`);
      setProspect(response.data);
      setFormData({
        status: response.data.status,
        notes: response.data.notes || '',
        owner_name: response.data.owner_name || '',
        owner_email: response.data.owner_email || '',
        owner_phone: response.data.owner_phone || '',
      });
    } catch (err) {
      setError('Erreur lors du chargement du prospect');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      const response = await api.put(`/prospects/${id}`, formData);
      setProspect(response.data);
      setEditMode(false);
    } catch (err) {
      alert('Erreur lors de la sauvegarde');
      console.error(err);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer ce prospect ?')) {
      return;
    }
    try {
      await api.delete(`/prospects/${id}`);
      navigate('/prospects');
    } catch (err) {
      alert('Erreur lors de la suppression');
      console.error(err);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !prospect) {
    return <Alert severity="error">{error || 'Prospect non trouvé'}</Alert>;
  }

  const scoreDetails = prospect.score_details || {};

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate('/prospects')}
        sx={{ mb: 3 }}
      >
        Retour
      </Button>

      <Grid container spacing={3}>
        {/* Informations principales */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h5" fontWeight="bold">
                  Détails du Prospect
                </Typography>
                <Box>
                  {editMode ? (
                    <>
                      <Button
                        startIcon={<Save />}
                        variant="contained"
                        onClick={handleSave}
                        sx={{ mr: 1 }}
                      >
                        Sauvegarder
                      </Button>
                      <Button onClick={() => setEditMode(false)}>Annuler</Button>
                    </>
                  ) : (
                    <>
                      <Button
                        startIcon={<Edit />}
                        onClick={() => setEditMode(true)}
                        sx={{ mr: 1 }}
                      >
                        Modifier
                      </Button>
                      <Button
                        startIcon={<Delete />}
                        color="error"
                        onClick={handleDelete}
                      >
                        Supprimer
                      </Button>
                    </>
                  )}
                </Box>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Adresse
                  </Typography>
                  <Typography variant="body1" fontWeight="500">
                    {prospect.address}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {prospect.postal_code} {prospect.city}
                  </Typography>
                </Grid>

                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Type
                  </Typography>
                  <Typography variant="body1">
                    {prospect.property_type === 'maison' ? 'Maison' : 'Appartement'}
                  </Typography>
                </Grid>

                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Surface
                  </Typography>
                  <Typography variant="body1">{prospect.surface} m²</Typography>
                </Grid>

                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Pièces
                  </Typography>
                  <Typography variant="body1">{prospect.rooms}</Typography>
                </Grid>

                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    DPE
                  </Typography>
                  <Chip
                    label={prospect.dpe_score || 'Non renseigné'}
                    color={['F', 'G'].includes(prospect.dpe_score) ? 'error' : 'default'}
                  />
                </Grid>

                <Grid item xs={12}>
                  <Divider sx={{ my: 2 }} />
                </Grid>

                {/* Informations éditables */}
                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel>Statut</InputLabel>
                    <Select
                      value={formData.status}
                      label="Statut"
                      disabled={!editMode}
                      onChange={(e) =>
                        setFormData({ ...formData, status: e.target.value })
                      }
                    >
                      <MenuItem value="new">Nouveau</MenuItem>
                      <MenuItem value="contacted">Contacté</MenuItem>
                      <MenuItem value="interested">Intéressé</MenuItem>
                      <MenuItem value="qualified">Qualifié</MenuItem>
                      <MenuItem value="lost">Perdu</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Nom propriétaire"
                    value={formData.owner_name}
                    disabled={!editMode}
                    onChange={(e) =>
                      setFormData({ ...formData, owner_name: e.target.value })
                    }
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Email"
                    type="email"
                    value={formData.owner_email}
                    disabled={!editMode}
                    onChange={(e) =>
                      setFormData({ ...formData, owner_email: e.target.value })
                    }
                  />
                </Grid>

                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Téléphone"
                    value={formData.owner_phone}
                    disabled={!editMode}
                    onChange={(e) =>
                      setFormData({ ...formData, owner_phone: e.target.value })
                    }
                  />
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Notes"
                    multiline
                    rows={4}
                    value={formData.notes}
                    disabled={!editMode}
                    onChange={(e) =>
                      setFormData({ ...formData, notes: e.target.value })
                    }
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Score et détails */}
        <Grid item xs={12} md={4}>
          <Card sx={{ mb: 2, background: 'linear-gradient(135deg, #04264b 0%, #1a3d5f 100%)' }}>
            <CardContent>
              <Typography variant="h6" color="white" gutterBottom>
                Score Total
              </Typography>
              <Box textAlign="center" py={2}>
                <Typography variant="h1" fontWeight="bold" color="secondary.main">
                  {prospect.score}
                </Typography>
                <Typography variant="body2" color="white">
                  / 100
                </Typography>
                <Chip
                  label={
                    prospect.priority === 'high'
                      ? 'Haute Priorité'
                      : prospect.priority === 'medium'
                      ? 'Priorité Moyenne'
                      : 'Basse Priorité'
                  }
                  color={
                    prospect.priority === 'high'
                      ? 'error'
                      : prospect.priority === 'medium'
                      ? 'warning'
                      : 'default'
                  }
                  sx={{ mt: 2 }}
                />
              </Box>
            </CardContent>
          </Card>

          {/* Détails du score */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Détails du Score
              </Typography>
              {Object.entries(scoreDetails).map(([key, detail]) => {
                if (key === 'total' || !detail.points) return null;
                return (
                  <Box key={key} mb={2}>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2" fontWeight="500">
                        {detail.reason?.split('=')[0] || key}
                      </Typography>
                      <Typography variant="body2" color="secondary.main" fontWeight="bold">
                        {detail.points}/{detail.max}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 6,
                        backgroundColor: '#e0e0e0',
                        borderRadius: 3,
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          height: '100%',
                          width: `${(detail.points / detail.max) * 100}%`,
                          backgroundColor: 'secondary.main',
                        }}
                      />
                    </Box>
                  </Box>
                );
              })}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default ProspectDetail;
