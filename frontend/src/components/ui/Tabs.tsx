import {
  createContext,
  useContext,
  useState,
  ReactNode,
  HTMLAttributes,
  ButtonHTMLAttributes,
} from 'react'
import { clsx } from 'clsx'

interface TabsContextValue {
  activeTab: string
  setActiveTab: (tab: string) => void
}

const TabsContext = createContext<TabsContextValue>({
  activeTab: '',
  setActiveTab: () => {},
})

interface TabsProps {
  defaultTab?: string
  activeTab?: string
  onTabChange?: (tab: string) => void
  children: ReactNode
  className?: string
}

export function Tabs({ defaultTab, activeTab: controlledTab, onTabChange, children, className }: TabsProps) {
  const [internalTab, setInternalTab] = useState(defaultTab ?? '')

  const activeTab = controlledTab ?? internalTab
  const setActiveTab = (tab: string) => {
    setInternalTab(tab)
    onTabChange?.(tab)
  }

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={clsx('flex flex-col', className)}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabList({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="tablist"
      className={clsx(
        'flex gap-1 border-b border-[#1e1e2e] px-4 overflow-x-auto',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

interface TabProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
}

export function Tab({ value, className, children, ...props }: TabProps) {
  const { activeTab, setActiveTab } = useContext(TabsContext)
  const isActive = activeTab === value

  return (
    <button
      role="tab"
      aria-selected={isActive}
      onClick={() => setActiveTab(value)}
      className={clsx(
        'px-4 py-3 text-sm font-medium transition-all duration-150 border-b-2 -mb-px whitespace-nowrap',
        isActive
          ? 'border-[#e63946] text-white'
          : 'border-transparent text-[#6b7280] hover:text-[#9ca3af]',
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
}

interface TabPanelProps {
  value: string
  children: ReactNode
  className?: string
}

export function TabPanel({ value, children, className }: TabPanelProps) {
  const { activeTab } = useContext(TabsContext)
  if (activeTab !== value) return null
  return <div className={clsx('flex-1 min-h-0', className)}>{children}</div>
}
