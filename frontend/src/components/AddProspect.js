import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
} from '@mui/material';
import { ArrowBack, Save } from '@mui/icons-material';
import { api } from '../utils/api';

function AddProspect() {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    address: '',
    postal_code: '',
    city: '',
    property_type: 'maison',
    surface: '',
    rooms: '',
    dpe_score: '',
    dpe_value: '',
    owner_name: '',
    owner_email: '',
    owner_phone: '',
  });

  const handleChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Validation
      if (!formData.address || !formData.postal_code || !formData.city) {
        setError('Veuillez remplir tous les champs obligatoires');
        setLoading(false);
        return;
      }

      const dataToSend = {
        ...formData,
        surface: parseFloat(formData.surface),
        rooms: parseInt(formData.rooms),
        dpe_value: formData.dpe_value ? parseFloat(formData.dpe_value) : null,
      };

      const response = await api.post('/prospects', dataToSend);
      navigate(`/prospects/${response.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la création du prospect');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate('/prospects')}
        sx={{ mb: 3 }}
      >
        Retour
      </Button>

      <Card sx={{ maxWidth: 900, mx: 'auto' }}>
        <CardContent>
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            Ajouter un Prospect
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            Remplissez les informations du bien pour calculer automatiquement le score
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Informations du bien
                </Typography>
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  required
                  label="Adresse complète"
                  value={formData.address}
                  onChange={(e) => handleChange('address', e.target.value)}
                  placeholder="123 Rue de la République"
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  required
                  label="Code postal"
                  value={formData.postal_code}
                  onChange={(e) => handleChange('postal_code', e.target.value)}
                  placeholder="75001"
                  inputProps={{ maxLength: 5 }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  required
                  label="Ville"
                  value={formData.city}
                  onChange={(e) => handleChange('city', e.target.value)}
                  placeholder="Paris"
                />
              </Grid>

              <Grid item xs={12} sm={4}>
                <FormControl fullWidth required>
                  <InputLabel>Type de bien</InputLabel>
                  <Select
                    value={formData.property_type}
                    label="Type de bien"
                    onChange={(e) => handleChange('property_type', e.target.value)}
                  >
                    <MenuItem value="maison">Maison</MenuItem>
                    <MenuItem value="appartement">Appartement</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  required
                  type="number"
                  label="Surface (m²)"
                  value={formData.surface}
                  onChange={(e) => handleChange('surface', e.target.value)}
                  placeholder="80"
                  inputProps={{ min: 0, step: 0.1 }}
                />
              </Grid>

              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  required
                  type="number"
                  label="Nombre de pièces"
                  value={formData.rooms}
                  onChange={(e) => handleChange('rooms', e.target.value)}
                  placeholder="3"
                  inputProps={{ min: 1 }}
                />
              </Grid>

              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>Classe DPE</InputLabel>
                  <Select
                    value={formData.dpe_score}
                    label="Classe DPE"
                    onChange={(e) => handleChange('dpe_score', e.target.value)}
                  >
                    <MenuItem value="">Non renseigné</MenuItem>
                    <MenuItem value="A">A (Excellent)</MenuItem>
                    <MenuItem value="B">B (Bon)</MenuItem>
                    <MenuItem value="C">C (Assez bon)</MenuItem>
                    <MenuItem value="D">D (Moyen)</MenuItem>
                    <MenuItem value="E">E (Médiocre)</MenuItem>
                    <MenuItem value="F">F (Mauvais)</MenuItem>
                    <MenuItem value="G">G (Très mauvais)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  type="number"
                  label="Valeur DPE (kWh/m²/an)"
                  value={formData.dpe_value}
                  onChange={(e) => handleChange('dpe_value', e.target.value)}
                  placeholder="250"
                  inputProps={{ min: 0 }}
                  helperText="Optionnel"
                />
              </Grid>

              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                  Informations propriétaire (optionnel)
                </Typography>
              </Grid>

              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  label="Nom"
                  value={formData.owner_name}
                  onChange={(e) => handleChange('owner_name', e.target.value)}
                  placeholder="Jean Dupont"
                />
              </Grid>

              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  type="email"
                  label="Email"
                  value={formData.owner_email}
                  onChange={(e) => handleChange('owner_email', e.target.value)}
                  placeholder="jean.dupont@email.com"
                />
              </Grid>

              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  type="tel"
                  label="Téléphone"
                  value={formData.owner_phone}
                  onChange={(e) => handleChange('owner_phone', e.target.value)}
                  placeholder="06 12 34 56 78"
                />
              </Grid>

              <Grid item xs={12}>
                <Box display="flex" gap={2} justifyContent="flex-end" mt={2}>
                  <Button onClick={() => navigate('/prospects')}>
                    Annuler
                  </Button>
                  <Button
                    type="submit"
                    variant="contained"
                    startIcon={<Save />}
                    disabled={loading}
                  >
                    {loading ? 'Enregistrement...' : 'Créer le prospect'}
                  </Button>
                </Box>
              </Grid>
            </Grid>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}

export default AddProspect;
