# Frontend Service

React + Vite + Material-UI frontend application.

## Structure

```
frontend/
├── src/                    # Source files
│   ├── components/        # React components
│   ├── hooks/            # Custom React hooks
│   ├── pages/            # Page components
│   ├── services/         # API services
│   ├── types/            # TypeScript type definitions
│   ├── utils/            # Utility functions
│   ├── App.tsx          # Root component
│   ├── main.tsx         # Entry point
│   └── vite-env.d.ts    # Vite type definitions
├── public/               # Static files
├── Dockerfile           # Docker configuration
├── package.json         # Dependencies and scripts
├── tsconfig.json        # TypeScript configuration
└── vite.config.ts       # Vite configuration
```

## Development

This service is part of a Docker Compose setup. Please refer to the root directory's README.md for setup instructions.

### Dependencies

- Node.js 20+
- React 18
- Material-UI
- TypeScript
- Vite

### Environment Variables

All environment variables are managed in the root directory's `.env` file. See `.env.example` for available options.

### Available Scripts

In the development environment (via Docker Compose):
- The application will automatically reload when you make changes
- The development server runs on http://localhost:3000
- API requests are automatically proxied to the backend

### Code Style

- TypeScript for type safety
- ESLint for code linting
- Material-UI for consistent styling
- React hooks for state management
