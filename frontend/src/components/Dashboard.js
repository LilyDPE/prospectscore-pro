import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  Star,
  People,
  Assessment,
  ArrowForward,
} from '@mui/icons-material';
import { api } from '../utils/api';

function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [topProspects, setTopProspects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      // Récupérer les stats
      const statsResponse = await api.get('/stats/dashboard');
      setStats(statsResponse.data);
      
      // Récupérer les top prospects
      const prospectsResponse = await api.get('/prospects', {
        params: {
          priority: 'high',
          limit: 5,
        },
      });
      setTopProspects(prospectsResponse.data);
    } catch (err) {
      setError('Erreur lors du chargement du dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  const statCards = [
    {
      title: 'Total Prospects',
      value: stats?.total_prospects || 0,
      icon: <People fontSize="large" />,
      color: '#04264b',
    },
    {
      title: 'Haute Priorité',
      value: stats?.high_priority || 0,
      icon: <Star fontSize="large" />,
      color: '#b4e434',
    },
    {
      title: 'Nouveaux',
      value: stats?.new_prospects || 0,
      icon: <TrendingUp fontSize="large" />,
      color: '#04264b',
    },
    {
      title: 'Score Moyen',
      value: `${stats?.average_score || 0}/100`,
      icon: <Assessment fontSize="large" />,
      color: '#b4e434',
    },
  ];

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

  const getPriorityLabel = (priority) => {
    switch (priority) {
      case 'high':
        return 'Haute';
      case 'medium':
        return 'Moyenne';
      default:
        return 'Basse';
    }
  };

  return (
    <Box>
      <Typography variant="h4" fontWeight="bold" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" mb={4}>
        Vue d'ensemble de vos prospects vendeurs
      </Typography>

      {/* Stats Cards */}
      <Grid container spacing={3} mb={4}>
        {statCards.map((card, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <Card
              sx={{
                height: '100%',
                background: `linear-gradient(135deg, ${card.color}15 0%, ${card.color}05 100%)`,
                border: `1px solid ${card.color}30`,
              }}
            >
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <Box
                    sx={{
                      backgroundColor: card.color,
                      color: 'white',
                      borderRadius: 2,
                      p: 1,
                      mr: 2,
                    }}
                  >
                    {card.icon}
                  </Box>
                  <Typography variant="h4" fontWeight="bold">
                    {card.value}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {card.title}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Top Prospects */}
      <Card>
        <CardContent>
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            mb={3}
          >
            <Typography variant="h6" fontWeight="bold">
              Prospects Prioritaires
            </Typography>
            <Button
              endIcon={<ArrowForward />}
              onClick={() => navigate('/prospects')}
            >
              Voir tous
            </Button>
          </Box>

          {topProspects.length === 0 ? (
            <Alert severity="info">
              Aucun prospect prioritaire pour le moment.
              <Button
                sx={{ ml: 2 }}
                variant="outlined"
                size="small"
                onClick={() => navigate('/add-prospect')}
              >
                Ajouter un prospect
              </Button>
            </Alert>
          ) : (
            <Grid container spacing={2}>
              {topProspects.map((prospect) => (
                <Grid item xs={12} key={prospect.id}>
                  <Card
                    variant="outlined"
                    sx={{
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      '&:hover': {
                        boxShadow: 3,
                        borderColor: 'secondary.main',
                      },
                    }}
                    onClick={() => navigate(`/prospects/${prospect.id}`)}
                  >
                    <CardContent>
                      <Box
                        display="flex"
                        justifyContent="space-between"
                        alignItems="center"
                      >
                        <Box flex={1}>
                          <Typography variant="h6" gutterBottom>
                            {prospect.address}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            gutterBottom
                          >
                            {prospect.postal_code} {prospect.city}
                          </Typography>
                          <Box display="flex" gap={1} mt={1}>
                            <Chip
                              label={prospect.property_type}
                              size="small"
                              variant="outlined"
                            />
                            <Chip
                              label={`${prospect.surface}m² • ${prospect.rooms} pièces`}
                              size="small"
                              variant="outlined"
                            />
                            {prospect.dpe_score && (
                              <Chip
                                label={`DPE ${prospect.dpe_score}`}
                                size="small"
                                color={
                                  ['F', 'G'].includes(prospect.dpe_score)
                                    ? 'error'
                                    : 'default'
                                }
                              />
                            )}
                          </Box>
                        </Box>
                        <Box textAlign="right" ml={2}>
                          <Box
                            sx={{
                              backgroundColor: 'secondary.main',
                              color: 'primary.main',
                              borderRadius: 2,
                              px: 2,
                              py: 1,
                              mb: 1,
                            }}
                          >
                            <Typography variant="h5" fontWeight="bold">
                              {prospect.score}
                            </Typography>
                            <Typography variant="caption">/ 100</Typography>
                          </Box>
                          <Chip
                            label={getPriorityLabel(prospect.priority)}
                            color={getPriorityColor(prospect.priority)}
                            size="small"
                          />
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

export default Dashboard;
