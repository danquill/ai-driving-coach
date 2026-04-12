import { useState } from 'react'
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
  const [menuOpen, setMenuOpen] = useState(false)

  const defaultRight = {
    label: 'Sign Out',
    onClick: () => { clearAuth(); navigate({ to: '/login' }) },
  }
  const right = rightAction ?? defaultRight

  function closeMenu() {
    setMenuOpen(false)
  }

  return (
    <header className="border-b border-[#1e1e2e] bg-[#12121a] flex-shrink-0 relative">
      <div className="px-4 md:px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate({ to: '/' })}
            className="text-xl font-black tracking-[0.2em] text-white hover:opacity-80 transition-opacity"
          >
            TR<span className="text-[#e63946]">A</span>CK
          </button>
          <span className="text-[#1e1e2e] hidden md:inline">|</span>
          <span className="text-sm text-[#6b7280] hidden md:inline">{subtitle}</span>
        </div>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center">
          {user && (
            <button
              onClick={() => navigate({ to: '/profile' })}
              className="flex items-center gap-2 text-xs px-2.5 py-1 rounded hover:bg-[#1e1e2e] transition-colors mr-2 group"
            >
              <span className="text-[#9ca3af] group-hover:text-white transition-colors">{user.display_name}</span>
              <span className="text-[#2e2e4e]">|</span>
              <span className="text-[#4b5563] group-hover:text-[#457b9d] transition-colors">Profile</span>
            </button>
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

        {/* Mobile hamburger button */}
        <button
          className="md:hidden flex items-center justify-center w-9 h-9 rounded hover:bg-[#1e1e2e] transition-colors text-[#9ca3af]"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {menuOpen ? (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="md:hidden absolute top-14 left-0 right-0 z-50 bg-[#12121a] border-b border-[#1e1e2e] shadow-xl">
          <div className="px-4 py-3 space-y-1">
            {user && (
              <button
                onClick={() => { navigate({ to: '/profile' }); closeMenu() }}
                className="w-full text-left flex items-center gap-2 px-3 py-2.5 rounded hover:bg-[#1e1e2e] transition-colors"
              >
                <span className="text-sm text-[#9ca3af]">{user.display_name}</span>
                <span className="text-xs text-[#4b5563] ml-auto">Profile</span>
              </button>
            )}
            {navItems && navItems.map((item) => (
              <button
                key={item.to}
                onClick={() => { navigate({ to: item.to as never }); closeMenu() }}
                className="w-full text-left px-3 py-2.5 rounded hover:bg-[#1e1e2e] transition-colors text-sm text-[#9ca3af] hover:text-white"
              >
                {item.label}
              </button>
            ))}
            <div className="border-t border-[#1e1e2e] pt-1 mt-1">
              <button
                onClick={() => { right.onClick(); closeMenu() }}
                className="w-full text-left px-3 py-2.5 rounded hover:bg-[#1e1e2e] transition-colors text-sm text-[#6b7280] hover:text-white"
              >
                {right.label}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
