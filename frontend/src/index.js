import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App';

// Thème 2A Immobilier
const theme = createTheme({
  palette: {
    primary: {
      main: '#04264b', // Navy
      light: '#1a3d5f',
      dark: '#001a33',
    },
    secondary: {
      main: '#b4e434', // Yellow-green
      light: '#c7ec5f',
      dark: '#95be2a',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
    text: {
      primary: '#04264b',
      secondary: '#666666',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 700,
      color: '#04264b',
    },
    h2: {
      fontWeight: 600,
      color: '#04264b',
    },
    h3: {
      fontWeight: 600,
      color: '#04264b',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
          fontWeight: 500,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 8px rgba(4, 38, 75, 0.2)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        },
      },
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
