# SaaS Frontend

React + Vite frontend for multi-tenant school management system.

## Features

- React 18 with Vite
- Zustand for state management
- React Query for server state
- React Router for navigation
- shadcn/ui components
- Tailwind CSS

## Installation

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## Environment Variables

```
VITE_API_URL=http://localhost:8000/api
```

## Project Structure

- `/src/api` - API clients and endpoints
- `/src/components` - Reusable React components
- `/src/pages` - Page components organized by feature
- `/src/store` - Zustand stores
- `/src/hooks` - Custom React hooks
