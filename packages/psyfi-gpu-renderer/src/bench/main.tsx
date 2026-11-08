import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../styles/chrome.css'
import { BenchApp } from './BenchApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BenchApp />
  </StrictMode>,
)
