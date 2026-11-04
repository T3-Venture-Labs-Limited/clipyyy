import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Link, NavLink, Outlet, RouterProvider } from 'react-router'
import { Toaster } from 'sonner'
import { api } from './api'
import { cn, sourceLabel } from './components/ui'
import './index.css'
import { NewRunPage } from './pages/NewRun'
import { RunDetailPage } from './pages/RunDetail'
import { RunsPage, useRuns } from './pages/Runs'
import { SettingsPage } from './pages/Settings'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('font-display text-[22px] leading-none tracking-[-0.04em]', className)}>
      clip<span className="px-sm inline-block bg-acid px-[3px] pb-0.5 text-ink">yyy</span>
    </span>
  )
}

function GithubMark() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

const dot: Record<string, string> = { completed: 'bg-ink', running: 'bg-acid blink', queued: 'bg-faint', failed: 'bg-bad' }

function Sidebar() {
  const runs = useRuns()
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 })
  const queue = health.data?.queue
  const busy = (queue?.running ?? 0) + (queue?.queued ?? 0)
  const nav = ({ isActive }: { isActive: boolean }) =>
    cn('label flex h-9 items-center px-3 transition-colors', isActive ? 'bg-ink text-white' : 'text-muted hover:bg-sunk hover:text-ink')

  return (
    <aside className="sticky top-0 hidden h-screen w-[260px] shrink-0 flex-col border-r border-line bg-surface md:flex">
      <div className="flex h-16 items-center px-5">
        <Link to="/">
          <Wordmark />
        </Link>
      </div>
      <div className="px-4">
        <Link to="/" className="btn btn-acid flex h-11 items-center justify-center gap-2 text-sm font-semibold">
          <Plus className="h-4 w-4" /> New clips
        </Link>
      </div>
      <nav className="mt-5 flex flex-col gap-0.5 px-4">
        <NavLink to="/runs" className={nav}>
          All runs
        </NavLink>
        <NavLink to="/settings" className={nav}>
          Settings
        </NavLink>
      </nav>

      <div className="mt-6 flex min-h-0 flex-1 flex-col px-4">
        <p className="label px-3 pb-2 text-faint">Recent</p>
        <div className="-mx-1 flex-1 overflow-y-auto px-1">
          {(runs.data ?? []).slice(0, 14).map((run) => (
            <NavLink
              key={run.id}
              to={`/runs/${run.id}`}
              className={({ isActive }) =>
                cn('flex items-center gap-2.5 px-3 py-2 text-[13px] transition-colors', isActive ? 'bg-sunk text-ink' : 'text-body hover:bg-sunk')
              }
            >
              <span className={cn('h-2 w-2 shrink-0', dot[run.status])} />
              <span className="truncate">{sourceLabel(run)}</span>
            </NavLink>
          ))}
          {runs.data?.length === 0 && <p className="px-3 text-[13px] text-faint">Nothing yet.</p>}
        </div>
      </div>

      <div className="border-t border-line px-5 py-4">
        <div className="flex items-center gap-2 text-[13px]">
          <span className={cn('h-2 w-2', busy ? 'bg-acid blink' : health.data ? 'bg-ok' : 'bg-faint')} />
          <span className="text-body">
            {!health.data ? 'Connecting…' : busy ? `${queue!.running} running · ${queue!.queued} queued` : 'Ready'}
          </span>
        </div>
        <div className="label mt-3 flex items-center justify-between text-faint">
          <span>v{health.data?.version ?? '–'} · MIT</span>
          <a href="https://github.com/T3-Venture-Labs-Limited/clipyyy" target="_blank" rel="noreferrer" className="hover:text-ink" aria-label="GitHub">
            <GithubMark />
          </a>
        </div>
      </div>
    </aside>
  )
}

function MobileBar() {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b border-line bg-surface px-4 md:hidden">
      <Link to="/">
        <Wordmark className="text-xl" />
      </Link>
      <nav className="label ml-auto flex gap-4 text-muted">
        <NavLink to="/runs">Runs</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
    </header>
  )
}

function Layout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <MobileBar />
        <main className="mx-auto max-w-[1240px] px-5 py-8 md:px-10 md:py-10">
          <Outlet />
        </main>
      </div>
      <Toaster
        position="bottom-right"
        toastOptions={{ classNames: { toast: '!rounded-none !border-line !font-sans', success: '!bg-surface', error: '!text-bad' } }}
      />
    </div>
  )
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <NewRunPage /> },
      { path: '/runs', element: <RunsPage /> },
      { path: '/runs/:runId', element: <RunDetailPage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
