Mobile Responsiveness Guide (React + Vite + MUI)

This guide explains how to adapt the current frontend for mobile devices (e.g., iPhone) with concrete changes, file locations, and example code. It is tailored to this project’s structure and Material UI (MUI) usage.

Goals
- Make all views usable on small screens (≤ 414px width).
- Keep desktop layouts intact.
- Ensure navigation and content don’t overflow or become unreadable.

Quick Wins (Do These First)
- Viewport: Already set in `frontend/index.html` (OK).
- Global CSS: Ensure images and long content don’t break layouts.
  - Edit `frontend/src/index.css` and add:
    - `img, video { max-width: 100%; height: auto; }`
    - `.scroll-x { overflow-x: auto; }`
    - `:root { color-scheme: light dark; }` (optional)
- Responsive fonts: Wrap theme with `responsiveFontSizes` to scale typography.

Theme and Typography
File: `frontend/src/main.tsx`
- Add MUI responsive fonts:

```
import { ThemeProvider, createTheme, CssBaseline, responsiveFontSizes } from '@mui/material'

let theme = createTheme({
  palette: { /* existing */ },
  typography: { /* existing */ }
});
theme = responsiveFontSizes(theme);
```

Global CSS Additions
File: `frontend/src/index.css`
- Append these rules:

```
/* Media scales and horizontal safety */
img, video { max-width: 100%; height: auto; }
table { width: 100%; border-collapse: collapse; }
.scroll-x { overflow-x: auto; -webkit-overflow-scrolling: touch; }

/* Use modern viewport unit to avoid iOS 100vh bugs */
html, body, #root { min-height: 100dvh; }
```

Layout Components (Most Impactful)
1) Main Layout
File: `frontend/src/components/Layout/MainLayout.tsx`
- Ensure padding is responsive and container doesn’t force desktop spacing on phones:

```
<Box sx={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
  <Container component="main" sx={{ flex: 1, py: { xs: 2, md: 4 }, px: { xs: 2, md: 3 } }}>
    {children}
  </Container>
</Box>
```

2) Management Layout (Drawer + AppBar)
File: `frontend/src/components/Layout/ManagementLayout.tsx`
- Problem: `Drawer` is always `permanent` and widths are fixed, so content is cramped on mobile.
- Fix: Switch to a temporary drawer on small screens and use a menu button to toggle it. Remove width subtraction on mobile.

Minimal, drop-in changes:

```
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText,
  Typography, Toolbar, AppBar, Container, Button, Divider, IconButton,
  useMediaQuery, useTheme
} from '@mui/material';
import { Menu as MenuIcon, ArrowBack as ArrowBackIcon, Schedule as TaskIcon, Dashboard as DashboardIcon, Settings as SettingsIcon } from '@mui/icons-material';

const DRAWER_WIDTH = 240;

const ManagementLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const toggleDrawer = () => setMobileOpen(v => !v);

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={isMobile ? undefined : { width: `calc(100% - ${DRAWER_WIDTH}px)`, ml: `${DRAWER_WIDTH}px` }}
      >
        <Toolbar>
          {isMobile && (
            <IconButton edge="start" color="inherit" onClick={toggleDrawer} sx={{ mr: 1 }} aria-label="open menu">
              <MenuIcon />
            </IconButton>
          )}
          <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/dashboard')} sx={{ mr: 2, color: 'white', display: { xs: 'none', sm: 'inline-flex' } }}>
            返回仪表板
          </Button>
          <Typography variant="h6" noWrap component="div">综合管理系统</Typography>
        </Toolbar>
      </AppBar>

      <Drawer
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? mobileOpen : true}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
          display: { xs: 'block', md: 'block' }
        }}
        anchor="left"
      >
        {/* ... existing drawer content ... */}
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, bgcolor: 'background.default', p: { xs: 2, md: 3 }, width: isMobile ? '100%' : `calc(100% - ${DRAWER_WIDTH}px)` }}>
        <Toolbar />
        <Container maxWidth="xl">{children}</Container>
      </Box>
    </Box>
  );
};
```

Pages: Common Patterns to Apply
- Prefer mobile-first props in MUI Grid:
  - Use `Grid item xs={12} md={6}` instead of fixed widths.
  - For flex boxes, use responsive direction: `flexDirection: { xs: 'column', md: 'row' }`.
- Replace manual `maxWidth: 1200` wrappers with MUI `Container` where possible. If keeping, ensure it doesn’t force overflow on small screens.
- Top bars of pages (title + actions) should wrap:

```
<Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 3, flexWrap: 'wrap', justifyContent: 'space-between' }}>
  <Typography variant="h4" sx={{ fontSize: { xs: 20, sm: 24, md: 28 } }}>标题</Typography>
  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
    {/* buttons */}
  </Box>
\</Box>
```

Forms
- Use `fullWidth` on inputs and buttons (already done in Login/Register).
- Consider `size="small"` on dense forms; make it conditional with `useMediaQuery` if needed.
- Group actions vertically on mobile:

```
<Box sx={{ display: 'flex', gap: 1, flexDirection: { xs: 'column', sm: 'row' } }}>
  <Button fullWidth variant="contained">Save</Button>
  <Button fullWidth variant="outlined">Cancel</Button>
</Box>
```

Tables and Wide Content
- Wrap tables/long lists in a horizontally scrollable container to avoid cramping:

```
<Box className="scroll-x">
  {/* table or wide content */}
</Box>
```

Images and Media
- Always render media with fluid sizing (global CSS above). Avoid hard-coded pixel widths.

Navigation Considerations (Optional Enhancements)
- Consider showing fewer sidebar items or moving secondary actions to a menu on mobile.
- If you have persistent actions, consider a bottom action bar on mobile-only: `display: { xs: 'flex', md: 'none' }`.

iOS Safari Notes
- Use `100dvh` instead of `100vh` to avoid the URL bar collapsing issue.
- Enable momentum scrolling for scroll containers: `-webkit-overflow-scrolling: touch;` (included in `.scroll-x`).

Verification & Testing
- Dev Tools → Toggle Device Toolbar → iPhone 14/SE widths.
- Run locally: `cd frontend && npm run dev` and check:
  - Login/Register pages render edge-to-edge with proper padding.
  - Dashboard cards stack vertically at `xs`, 2-column at `md`.
  - Management pages: drawer is hidden by default, toggled by the menu icon.
  - No horizontal scroll on the whole page; scroll confined to `.scroll-x` containers.

Rollout Plan
1) Add global CSS and responsive fonts.
2) Update `ManagementLayout` to use temporary drawer on small screens.
3) Audit each page top bar and grids to ensure `xs={12}` and responsive flex directions.
4) Wrap any tables or wide lists in `.scroll-x`.
5) Smoke test on iPhone widths and Android mid-range device widths.

File-by-File Checklist
- `frontend/src/main.tsx`
  - Add `responsiveFontSizes` to theme.
- `frontend/src/index.css`
  - Add media, table, scroll helpers, and `100dvh` rule.
- `frontend/src/components/Layout/MainLayout.tsx`
  - Use responsive paddings.
- `frontend/src/components/Layout/ManagementLayout.tsx`
  - Add `useMediaQuery`, menu button, and temporary drawer behavior.
- `frontend/src/pages/*`
  - Ensure `Grid` uses `xs={12}` and responsive breakpoints.
  - Adjust flex layouts with responsive `flexDirection`.
  - Wrap tables/lists in `.scroll-x` when they overflow.

Notes for This Codebase
- You already use MUI Grid with `xs`/`md` in most pages, which is good. The main blocker for mobile is the permanent sidebar and width-calc in `ManagementLayout`. Fixing that plus small spacing tweaks will make the app comfortable on iPhone sizes.

