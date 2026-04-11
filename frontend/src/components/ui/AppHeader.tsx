import { useNavigate } from '@tanstack/react-router'
import { useStore } from '../../store'
import { Button } from './Button'

interface NavItem {
  label: string
  to: string
}

interface AppHeaderProps {
  subtitle: string
  /** Nav links shown in the middle section (separated from username by a divider). */
  navItems?: NavItem[]
  /** Label and handler for the right-hand action (separated by a divider). Defaults to Dashboard link. */
  rightAction?: { label: string; onClick: () => void }
}

export function AppHeader({ subtitle, navItems, rightAction }: AppHeaderProps) {
  const navigate = useNavigate()
  const user = useStore((s) => s.user)
  const clearAuth = useStore((s) => s.clearAuth)

  const defaultRight = {
    label: 'Sign Out',
    onClick: () => { clearAuth(); navigate({ to: '/login' }) },
  }
  const right = rightAction ?? defaultRight

  return (
    <header className="border-b border-[#1e1e2e] bg-[#12121a] flex-shrink-0">
      <div className="px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate({ to: '/' })}
            className="text-xl font-black tracking-[0.2em] text-white hover:opacity-80 transition-opacity"
          >
            TR<span className="text-[#e63946]">A</span>CK
          </button>
          <span className="text-[#1e1e2e]">|</span>
          <span className="text-sm text-[#6b7280]">{subtitle}</span>
        </div>

        <div className="flex items-center">
          {user && (
            <span className="text-xs text-[#4b5563] pr-4">{user.display_name}</span>
          )}
          {navItems && navItems.length > 0 && (
            <div className="flex items-center gap-1 border-l border-[#1e1e2e] pl-4">
              {navItems.map((item) => (
                <Button key={item.to} variant="ghost" size="sm" onClick={() => navigate({ to: item.to as never })}>
                  {item.label}
                </Button>
              ))}
            </div>
          )}
          <div className={`border-l border-[#1e1e2e] pl-4 ${navItems && navItems.length > 0 ? 'ml-4' : ''}`}>
            <Button variant="ghost" size="sm" onClick={right.onClick}>
              {right.label}
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}
