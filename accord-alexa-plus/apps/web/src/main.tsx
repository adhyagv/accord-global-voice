import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import VoiceProvider from './voice/VoiceProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <VoiceProvider>
      <App />
    </VoiceProvider>
  </StrictMode>,
)
