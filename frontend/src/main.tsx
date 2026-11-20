import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../../backend/collector/static/theme.js'
import '../../backend/collector/static/theme.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
