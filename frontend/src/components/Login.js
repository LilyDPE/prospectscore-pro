import React, { useState } from 'react';
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Tab,
  Tabs,
} from '@mui/material';
import { api } from '../utils/api';

function TabPanel({ children, value, index }) {
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

function Login({ onLogin }) {
  const [tab, setTab] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Login form
  const [loginData, setLoginData] = useState({
    email: '',
    password: '',
  });

  // Register form
  const [registerData, setRegisterData] = useState({
    email: '',
    password: '',
    full_name: '',
  });

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/auth/login', loginData);
      const { access_token } = response.data;
      
      // Récupérer les infos utilisateur
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      const userResponse = await api.get('/auth/me');
      
      onLogin(access_token, userResponse.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur de connexion');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/auth/register', registerData);
      const { access_token } = response.data;
      
      // Récupérer les infos utilisateur
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      const userResponse = await api.get('/auth/me');
      
      onLogin(access_token, userResponse.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur d\'inscription');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #04264b 0%, #1a3d5f 100%)',
      }}
    >
      <Container maxWidth="sm">
        <Paper elevation={3} sx={{ p: 4 }}>
          {/* Logo / Titre */}
          <Box textAlign="center" mb={3}>
            <Typography variant="h4" fontWeight="bold" color="primary" gutterBottom>
              ProspectScore Pro
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Scoring de vendeurs potentiels - 2A Immobilier
            </Typography>
          </Box>

          {/* Tabs */}
          <Tabs value={tab} onChange={(e, v) => setTab(v)} centered>
            <Tab label="Connexion" />
            <Tab label="Inscription" />
          </Tabs>

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}

          {/* Login Tab */}
          <TabPanel value={tab} index={0}>
            <form onSubmit={handleLogin}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={loginData.email}
                onChange={(e) =>
                  setLoginData({ ...loginData, email: e.target.value })
                }
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Mot de passe"
                type="password"
                value={loginData.password}
                onChange={(e) =>
                  setLoginData({ ...loginData, password: e.target.value })
                }
                margin="normal"
                required
              />
              <Button
                fullWidth
                type="submit"
                variant="contained"
                size="large"
                disabled={loading}
                sx={{ mt: 3 }}
              >
                {loading ? 'Connexion...' : 'Se connecter'}
              </Button>
            </form>
          </TabPanel>

          {/* Register Tab */}
          <TabPanel value={tab} index={1}>
            <form onSubmit={handleRegister}>
              <TextField
                fullWidth
                label="Nom complet"
                value={registerData.full_name}
                onChange={(e) =>
                  setRegisterData({ ...registerData, full_name: e.target.value })
                }
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={registerData.email}
                onChange={(e) =>
                  setRegisterData({ ...registerData, email: e.target.value })
                }
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Mot de passe"
                type="password"
                value={registerData.password}
                onChange={(e) =>
                  setRegisterData({ ...registerData, password: e.target.value })
                }
                margin="normal"
                required
                helperText="Minimum 6 caractères"
              />
              <Button
                fullWidth
                type="submit"
                variant="contained"
                size="large"
                disabled={loading}
                sx={{ mt: 3 }}
              >
                {loading ? 'Inscription...' : "S'inscrire"}
              </Button>
            </form>
          </TabPanel>
        </Paper>
      </Container>
    </Box>
  );
}

export default Login;
