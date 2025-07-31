# Frontend Service - Reddit Scraper Bot UI

Modern React frontend application for the Reddit Scraper Bot system, providing an intuitive interface for bot management, session monitoring, and user administration.

## 🚀 Features

### Core Functionality
- **User Authentication**: Complete login/register flow with password reset
- **Bot Management**: Create, configure, and manage Reddit scraping bots
- **Session Monitoring**: Real-time tracking of scraping sessions with detailed analytics
- **Content Browsing**: View and analyze scraped Reddit posts and comments
- **User Administration**: Admin panel for user management and system oversight

### UI/UX Features
- **Responsive Design**: Mobile-first approach with Material-UI components
- **Real-time Updates**: Live status updates and notifications
- **Multi-language Support**: Chinese language interface with i18n structure
- **Dark/Light Theme**: Consistent theming across all components
- **Advanced Components**: Data grids, charts, dialogs, and filtering systems

### Technical Features
- **TypeScript**: Full type safety throughout the application
- **State Management**: Zustand for lightweight and efficient state management
- **API Integration**: Centralized API client with automatic token refresh
- **Route Protection**: Automatic authentication and authorization handling
- **Error Handling**: Unified error management with user-friendly messages

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/                # Reusable React components
│   │   ├── Layout/
│   │   │   └── MainLayout.tsx            # Main application layout
│   │   ├── Scraper/                      # Scraper-specific components
│   │   │   ├── BotConfigCard.tsx         # Bot configuration display
│   │   │   ├── BotConfigDialog.tsx       # Bot creation/edit dialog
│   │   │   ├── BotConfigForm.tsx         # Bot configuration form
│   │   │   ├── ScraperLayout.tsx         # Scraper section layout
│   │   │   ├── SessionCard.tsx           # Session information card
│   │   │   ├── SessionDetailDialog.tsx   # Session details popup
│   │   │   ├── SessionFilterBar.tsx      # Session filtering controls
│   │   │   └── SessionStatsPanel.tsx     # Session statistics panel
│   │   ├── ProtectedRoute.tsx            # Route authentication wrapper
│   │   └── TokenExpiryDialog.tsx         # Token expiry notification
│   ├── pages/                     # Page components
│   │   ├── BotManagementPage.tsx         # Bot configuration management
│   │   ├── DashboardPage.tsx             # Main dashboard
│   │   ├── DemoPage.tsx                  # Demo/testing page
│   │   ├── ForgotPasswordPage.tsx        # Password reset request
│   │   ├── LoginPage.tsx                 # User login
│   │   ├── ProfilePage.tsx               # User profile management
│   │   ├── RegisterPage.tsx              # User registration
│   │   ├── ResetPasswordPage.tsx         # Password reset form
│   │   ├── SessionManagementPage.tsx     # Session monitoring
│   │   └── UserPage.tsx                  # User administration
│   ├── services/                  # API and service layer
│   │   ├── api.ts                        # Main API client
│   │   ├── authManager.ts                # Authentication service
│   │   ├── interceptors.ts               # Axios interceptors
│   │   ├── uiManager.ts                  # UI state management
│   │   └── index.ts                      # Service exports
│   ├── stores/                    # Zustand state management
│   │   ├── auth-store.ts                 # Authentication state
│   │   ├── api-store.ts                  # API call state management
│   │   ├── ui-store.ts                   # UI state (dialogs, notifications)
│   │   └── index.ts                      # Store exports
│   ├── types/                     # TypeScript type definitions
│   │   ├── api.ts                        # API response types
│   │   ├── auth.ts                       # Authentication types
│   │   ├── bot.ts                        # Bot configuration types
│   │   ├── session.ts                    # Session types
│   │   └── index.ts                      # Type exports
│   ├── utils/                     # Utility functions
│   │   └── errorHandler.ts               # Error handling utilities
│   ├── routes.tsx                 # Application routing
│   ├── main.tsx                   # Application entry point
│   └── index.css                  # Global styles
├── public/                        # Static assets
│   └── vite.svg                   # Vite logo
├── dist/                          # Build output (generated)
├── node_modules/                  # Dependencies (generated)
├── Dockerfile                     # Docker configuration
├── package.json                   # Dependencies and scripts
├── package-lock.json              # Dependency lock file
├── tsconfig.json                  # TypeScript configuration
├── tsconfig.app.json              # App-specific TypeScript config
├── tsconfig.node.json             # Node-specific TypeScript config
├── vite.config.ts                 # Vite build configuration
├── eslint.config.js               # ESLint configuration
└── README.md                      # This file
```

## 🛠️ Technology Stack

### Core Dependencies
- **React 18**: Latest React with concurrent features and hooks
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Fast build tool and development server
- **Material-UI (MUI)**: Comprehensive React component library

### State Management
- **Zustand**: Lightweight state management solution
- **React Router**: Client-side routing with protected routes
- **Axios**: HTTP client with interceptors and automatic retries

### UI Components & Styling
- **@mui/material**: Core Material-UI components
- **@mui/icons-material**: Material Design icons
- **@emotion/react**: CSS-in-JS styling engine
- **@emotion/styled**: Styled components for Material-UI

### Development Tools
- **ESLint**: Code linting and formatting
- **TypeScript ESLint**: TypeScript-specific linting rules
- **Vite SWC**: Fast TypeScript/JSX transformation

## 🚀 Development Setup

### Prerequisites
- Node.js 20+
- npm or yarn package manager

### Local Development

1. **Install dependencies:**
```bash
cd frontend
npm install
```

2. **Set up environment variables:**
```bash
# Copy environment template (if exists)
cp ../.env.example ../.env
# Or create .env.local with:
echo "VITE_API_URL=http://localhost:8000" > .env.local
```

3. **Start development server:**
```bash
npm run dev
```

4. **Access the application:**
- Frontend: http://localhost:3000
- Hot reloading is enabled for instant updates

### Docker Development

This service is part of a Docker Compose setup. See the root directory's README.md for complete setup instructions.

```bash
# Start all services
docker compose up --build

# View frontend logs
docker compose logs frontend

# Execute commands in frontend container
docker compose exec frontend npm run build
```

## 🌐 Application Pages

### Public Pages
- **`/login`** - User authentication
- **`/register`** - User registration
- **`/forgot-password`** - Password reset request
- **`/reset-password`** - Password reset form (with token)

### Protected Pages (Require Authentication)
- **`/dashboard`** - Main dashboard with user overview
- **`/profile`** - User profile management
- **`/user`** - User administration (admin only)
- **`/scraper/bots`** - Bot configuration management
- **`/scraper/sessions`** - Session monitoring and analytics
- **`/demo`** - Demo page for testing features

## 🏗️ Architecture

### Component Architecture
- **Page Components**: Top-level route components
- **Layout Components**: Shared layout structures
- **Feature Components**: Domain-specific components (Scraper, Auth)
- **UI Components**: Reusable interface elements

### State Management Pattern
```typescript
// Zustand stores provide clean state management
const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  login: async (credentials) => { /* ... */ },
  logout: async () => { /* ... */ }
}))

// Components consume state reactively
const Component = () => {
  const { user, login } = useAuthStore()
  // Component updates automatically when state changes
}
```

### API Integration
```typescript
// Centralized API store manages all HTTP requests
const useApiStore = create<ApiState>((set, get) => ({
  fetchData: async (url) => { /* ... */ },
  postData: async (url, data) => { /* ... */ },
  // Automatic loading states and error handling
}))
```

### Route Protection
```typescript
// ProtectedRoute handles authentication automatically
<Route path="/dashboard" element={
  <ProtectedRoute>
    <DashboardPage />
  </ProtectedRoute>
} />
```

## 🎨 UI Components

### Key Component Features

#### Bot Management
- **BotConfigCard**: Displays bot configuration with status indicators
- **BotConfigDialog**: Modal for creating/editing bot configurations
- **BotConfigForm**: Form with validation for bot settings

#### Session Monitoring
- **SessionCard**: Real-time session status and metrics
- **SessionDetailDialog**: Detailed session information and logs
- **SessionFilterBar**: Advanced filtering and search capabilities
- **SessionStatsPanel**: Charts and statistics for session analytics

#### Layout & Navigation
- **MainLayout**: Consistent header, navigation, and footer
- **ScraperLayout**: Specialized layout for scraper-related pages
- **ProtectedRoute**: Authentication wrapper for secure pages

## 🔧 Configuration

### Environment Variables
```env
# API Configuration
VITE_API_URL=http://localhost:8000

# Build Configuration (optional)
VITE_BUILD_MODE=development
```

### Vite Configuration
```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

### TypeScript Configuration
- **Strict Mode**: Enabled for maximum type safety
- **Path Mapping**: Clean imports with absolute paths
- **Module Resolution**: Node-style module resolution

## 📱 Responsive Design

### Breakpoint Strategy
- **Mobile First**: Base styles target mobile devices
- **Progressive Enhancement**: Features added for larger screens
- **Material-UI Grid**: Responsive grid system for layouts

### Key Responsive Features
- **Navigation**: Collapsible sidebar on mobile
- **Tables**: Horizontal scrolling and column hiding
- **Dialogs**: Full-screen on mobile, modal on desktop
- **Charts**: Responsive sizing and touch-friendly interactions

## 🔐 Authentication Flow

### Token Management
```typescript
// Automatic token refresh with Axios interceptors
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Automatically refresh token and retry request
      await refreshToken()
      return axios.request(error.config)
    }
    return Promise.reject(error)
  }
)
```

### Protected Routes
- **Automatic Redirects**: Unauthenticated users redirected to login
- **Token Validation**: Real-time token expiry handling
- **Seamless UX**: No page flashes or loading interruptions

## 🧪 Testing

### Available Scripts
```bash
# Development server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint

# Type checking
npx tsc --noEmit
```

### Testing Strategy
- **Component Testing**: Test individual components in isolation
- **Integration Testing**: Test component interactions and data flow
- **E2E Testing**: Test complete user workflows
- **API Testing**: Test API integration and error handling

## 🚀 Build & Deployment

### Development Build
```bash
# Start development server with hot reloading
npm run dev
```

### Production Build
```bash
# Create optimized production build
npm run build

# Preview production build locally
npm run preview
```

### Docker Deployment
```bash
# Build production Docker image
docker build -t reddit-scraper-frontend .

# Run container
docker run -p 3000:3000 reddit-scraper-frontend
```

### Deployment Considerations
- **Environment Variables**: Configure API URLs for different environments
- **Asset Optimization**: Vite automatically optimizes images and code
- **CDN Integration**: Static assets can be served from CDN
- **Caching Strategy**: Configure proper cache headers for assets

## 🔍 Performance Optimization

### Key Optimizations
- **Code Splitting**: Automatic route-based code splitting
- **Tree Shaking**: Unused code elimination
- **Bundle Analysis**: Use `npm run build -- --analyze` to analyze bundle size
- **Lazy Loading**: Component lazy loading for better initial load times

### State Management Efficiency
- **Selective Updates**: Components only re-render when relevant state changes
- **Computed Values**: Derived state is computed efficiently
- **Memory Management**: Automatic cleanup of unused state

## 📝 Development Guidelines

### Code Style
- **TypeScript**: Use strict typing throughout
- **Component Structure**: Consistent component organization
- **Naming Conventions**: Clear and descriptive naming
- **Error Boundaries**: Proper error handling at component level

### Best Practices
- **State Management**: Use appropriate store for different types of state
- **API Calls**: Always use api-store methods for consistent error handling
- **Loading States**: Show loading indicators for better UX
- **Error Handling**: Display user-friendly error messages
- **Accessibility**: Follow WCAG guidelines for inclusive design

### Component Development
```typescript
// Example component structure
interface ComponentProps {
  data: DataType
  onAction: (id: string) => void
}

const Component: React.FC<ComponentProps> = ({ data, onAction }) => {
  const { loading, error } = useApiStore()
  
  if (loading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  
  return (
    <Card>
      {/* Component content */}
    </Card>
  )
}

export default Component
```

## 🤝 Contributing

### Development Workflow
1. Create feature branch from main
2. Implement changes with proper TypeScript types
3. Test components and functionality
4. Ensure ESLint passes without errors
5. Update documentation if needed
6. Submit pull request with clear description

### Code Review Checklist
- [ ] TypeScript types are properly defined
- [ ] Components are responsive and accessible
- [ ] Error handling is implemented
- [ ] Loading states are shown appropriately
- [ ] Code follows established patterns

## 🔗 Related Documentation

- [React Documentation](https://react.dev/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [Material-UI Documentation](https://mui.com/)
- [Zustand Documentation](https://github.com/pmndrs/zustand)
- [Vite Documentation](https://vitejs.dev/)
- [Axios Documentation](https://axios-http.com/)