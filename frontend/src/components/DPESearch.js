import React, { useState } from 'react';
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
  CircularProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { Search, Add } from '@mui/icons-material';
import { api } from '../utils/api';

function DPESearch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);
  const [filters, setFilters] = useState({
    postal_code: '',
    dpe_min: 'E',
  });

  const handleSearch = async () => {
    if (!filters.postal_code || filters.postal_code.length !== 5) {
      setError('Veuillez entrer un code postal valide (5 chiffres)');
      return;
    }

    setError('');
    setLoading(true);

    try {
      const response = await api.get('/dpe/search', {
        params: {
          postal_code: filters.postal_code,
          dpe_min: filters.dpe_min,
          limit: 100,
        },
      });
      setResults(response.data);
      
      if (response.data.length === 0) {
        setError('Aucun résultat trouvé pour ce code postal');
      }
    } catch (err) {
      setError('Erreur lors de la recherche');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async (dpe) => {
    try {
      const prospectData = {
        address: dpe.adresse,
        postal_code: dpe.code_postal,
        city: dpe.commune,
        property_type: dpe.type_batiment?.toLowerCase().includes('maison')
          ? 'maison'
          : 'appartement',
        surface: dpe.surface_habitable || 80,
        rooms: dpe.nb_pieces || 3,
        dpe_score: dpe.classe_consommation_energie,
        dpe_value: dpe.consommation_energie,
      };

      const response = await api.post('/prospects', prospectData);
      alert('Prospect importé avec succès !');
      
      // Retirer de la liste des résultats
      setResults(results.filter(r => r.id !== dpe.id));
    } catch (err) {
      alert('Erreur lors de l\'import du prospect');
      console.error(err);
    }
  };

  return (
    <Box>
      <Typography variant="h4" fontWeight="bold" gutterBottom>
        Recherche DPE ADEME
      </Typography>
      <Typography variant="body1" color="text.secondary" mb={4}>
        Recherchez des biens avec de mauvaises performances énergétiques dans la base ADEME
      </Typography>

      {/* Filtres */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Code postal"
                value={filters.postal_code}
                onChange={(e) =>
                  setFilters({ ...filters, postal_code: e.target.value })
                }
                placeholder="75001"
                inputProps={{ maxLength: 5 }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Classe DPE minimale</InputLabel>
                <Select
                  value={filters.dpe_min}
                  label="Classe DPE minimale"
                  onChange={(e) =>
                    setFilters({ ...filters, dpe_min: e.target.value })
                  }
                >
                  <MenuItem value="D">D ou pire</MenuItem>
                  <MenuItem value="E">E ou pire</MenuItem>
                  <MenuItem value="F">F ou pire</MenuItem>
                  <MenuItem value="G">G uniquement</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Button
                fullWidth
                variant="contained"
                size="large"
                startIcon={<Search />}
                onClick={handleSearch}
                disabled={loading}
              >
                {loading ? 'Recherche...' : 'Rechercher'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Erreur */}
      {error && (
        <Alert severity="info" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Résultats */}
      {loading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : results.length > 0 ? (
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">
                {results.length} résultat{results.length > 1 ? 's' : ''} trouvé{results.length > 1 ? 's' : ''}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Cliquez sur "Importer" pour créer un prospect
              </Typography>
            </Box>

            <TableContainer component={Paper} variant="outlined">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Adresse</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell align="center">Surface</TableCell>
                    <TableCell align="center">Pièces</TableCell>
                    <TableCell align="center">DPE</TableCell>
                    <TableCell align="center">Consommation</TableCell>
                    <TableCell align="right">Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results.map((dpe) => (
                    <TableRow key={dpe.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight="500">
                          {dpe.adresse}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {dpe.code_postal} {dpe.commune}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {dpe.type_batiment?.toLowerCase().includes('maison')
                          ? 'Maison'
                          : 'Appartement'}
                      </TableCell>
                      <TableCell align="center">
                        {dpe.surface_habitable ? `${dpe.surface_habitable} m²` : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {dpe.nb_pieces || '-'}
                      </TableCell>
                      <TableCell align="center">
                        <Chip
                          label={dpe.classe_consommation_energie || '?'}
                          size="small"
                          color={
                            ['F', 'G'].includes(dpe.classe_consommation_energie)
                              ? 'error'
                              : ['D', 'E'].includes(dpe.classe_consommation_energie)
                              ? 'warning'
                              : 'default'
                          }
                        />
                      </TableCell>
                      <TableCell align="center">
                        {dpe.consommation_energie
                          ? `${Math.round(dpe.consommation_energie)} kWh/m²/an`
                          : '-'}
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<Add />}
                          onClick={() => handleImport(dpe)}
                        >
                          Importer
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      ) : null}
    </Box>
  );
}

export default DPESearch;
