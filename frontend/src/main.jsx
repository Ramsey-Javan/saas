import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import BrandingProvider from '@/components/BrandingProvider'
import { registerServiceWorker } from '@/lib/pushNotifications'
import { useAuthStore } from '@/store/authStore'

const queryClient = new QueryClient()

registerServiceWorker()

// zustand's persist() with sessionStorage rehydrates synchronously during
// store creation (the import above), so by this point `user`/`accessToken`
// already reflect whatever was in this tab's sessionStorage, if anything.
// We flip isHydrated so route guards know it's safe to make a decision
// instead of assuming a reload always means "logged out."
useAuthStore.getState().setHydrated(true)

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrandingProvider>
        <App />
      </BrandingProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)