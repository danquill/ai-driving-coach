import {
  createRouter,
  createRootRoute,
  createRoute,
  Outlet,
} from '@tanstack/react-router'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { DashboardPage } from './pages/DashboardPage'
import { NewSessionPage } from './pages/NewSessionPage'
import { SessionDetailPage } from './pages/SessionDetailPage'
import { AdminCircuitsPage } from './pages/AdminCircuitsPage'
import { AdminUsersPage } from './pages/AdminUsersPage'
import { AdminPlatformPage } from './pages/AdminPlatformPage'
import { ProfilePage } from './pages/ProfilePage'

// ─── Root route ───────────────────────────────────────────────────────────────

const rootRoute = createRootRoute({
  component: Outlet,
})

// ─── Child routes ─────────────────────────────────────────────────────────────

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  component: RegisterPage,
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: DashboardPage,
})

const newSessionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sessions/new',
  component: NewSessionPage,
})

const sessionDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sessions/$sessionId',
  component: SessionDetailPage,
})

const adminCircuitsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/circuits',
  component: AdminCircuitsPage,
})

const adminUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/users',
  component: AdminUsersPage,
})

const adminPlatformRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin/platform',
  component: AdminPlatformPage,
})

const profileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/profile',
  component: ProfilePage,
})

// ─── Route tree ───────────────────────────────────────────────────────────────

const routeTree = rootRoute.addChildren([
  loginRoute,
  registerRoute,
  dashboardRoute,
  newSessionRoute,
  sessionDetailRoute,
  adminCircuitsRoute,
  adminUsersRoute,
  adminPlatformRoute,
  profileRoute,
])

// ─── Router instance ──────────────────────────────────────────────────────────

export const router = createRouter({ routeTree })

// ─── Type registration ────────────────────────────────────────────────────────

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
