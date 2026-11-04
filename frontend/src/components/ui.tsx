import { clsx, type ClassValue } from 'clsx'
import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

type Variant = 'ink' | 'acid' | 'line' | 'ghost' | 'danger'

const variants: Record<Variant, string> = {
  ink: 'btn btn-ink',
  acid: 'btn btn-acid',
  line: 'border border-line-strong bg-surface text-ink hover:border-ink',
  ghost: 'text-muted hover:text-ink hover:bg-sunk',
  danger: 'border border-line-strong bg-surface text-bad hover:border-bad',
}

export function Button({
  variant = 'ink',
  size = 'md',
  loading,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' | 'lg'; loading?: boolean }) {
  return (
    <button
      className={cn(
        'inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 font-medium tracking-tight transition-colors disabled:pointer-events-none disabled:opacity-40',
        size === 'sm' && 'h-8 px-3 text-[13px]',
        size === 'md' && 'h-10 px-4 text-sm',
        size === 'lg' && 'h-12 px-6 text-[15px]',
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  )
}

export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border border-line bg-surface', className)} {...props} />
}

/** Small mono uppercase label with a leading square, like a slate on a film set. */
export function Eyebrow({ children, className, tone = 'muted' }: { children: ReactNode; className?: string; tone?: 'muted' | 'light' }) {
  return (
    <p className={cn('label flex items-center gap-2', tone === 'light' ? 'text-white/55' : 'text-muted', className)}>
      <span className={cn('h-2 w-2', tone === 'light' ? 'bg-acid' : 'bg-ink')} />
      {children}
    </p>
  )
}

const statusStyle: Record<string, string> = {
  completed: 'bg-ink text-white',
  running: 'bg-acid text-ink',
  queued: 'bg-sunk text-muted',
  failed: 'bg-bad text-white',
}

export function StatusChip({ status }: { status: string }) {
  return (
    <span className={cn('label px-sm inline-flex h-6 items-center gap-1.5 px-2 !text-[10px]', statusStyle[status] ?? statusStyle.queued)}>
      {status === 'running' && <span className="blink h-1.5 w-1.5 bg-ink" />}
      {status}
    </span>
  )
}

/** A row of squares: the brand's way of drawing a count or a score. */
export function Squares({ total, filled, className, size = 'h-2 w-2' }: { total: number; filled: number; className?: string; size?: string }) {
  return (
    <span className={cn('inline-flex gap-[3px]', className)} aria-label={`${filled} of ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={cn(size, i < filled ? 'bg-ink' : 'bg-line')} />
      ))}
    </span>
  )
}

export function Field({
  label,
  hint,
  children,
  className,
  group,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
  className?: string
  /** Render as a labelled group for multi-control fields (segmented buttons, pairs of inputs). */
  group?: boolean
}) {
  const Tag = group ? 'div' : 'label'
  return (
    <Tag className={cn('flex flex-col gap-2', className)} {...(group ? { role: 'group', 'aria-label': label } : {})}>
      <span className="label text-muted">{label}</span>
      {children}
      {hint && <span className="text-xs leading-relaxed text-muted">{hint}</span>}
    </Tag>
  )
}

const control =
  'w-full border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-faint outline-none transition-[border,box-shadow] focus:border-ink focus:shadow-[0_0_0_3px_var(--color-acid)]'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(control, 'h-10', className)} {...props} />
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(control, 'h-10 cursor-pointer pr-8', className)} {...props} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(control, 'py-2.5 leading-relaxed', className)} {...props} />
}

export function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  hint?: ReactNode
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="group flex w-full cursor-pointer items-start gap-3 py-1 text-left disabled:cursor-not-allowed disabled:opacity-45"
    >
      <span className={cn('px-sm mt-0.5 flex h-5 w-9 shrink-0 p-[3px] transition-colors', checked ? 'bg-ink' : 'bg-line-strong')}>
        <span className={cn('h-3.5 w-3.5 transition-transform duration-200', checked ? 'translate-x-4 bg-acid' : 'bg-white')} />
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-ink">{label}</span>
        {hint && <span className="text-xs leading-relaxed text-muted">{hint}</span>}
      </span>
    </button>
  )
}

export function Stepper({
  value,
  min,
  max,
  onChange,
  label,
}: {
  value: number
  min: number
  max: number
  onChange: (value: number) => void
  label: string
}) {
  const clamp = (n: number) => Math.max(min, Math.min(max, n))
  return (
    <div className="inline-flex h-10 items-stretch border border-line-strong bg-surface">
      <button type="button" aria-label="Fewer" className="w-9 cursor-pointer text-lg text-muted hover:bg-sunk hover:text-ink" onClick={() => onChange(clamp(value - 1))}>
        −
      </button>
      <input
        aria-label={label}
        className="w-10 border-x border-line text-center font-mono text-sm outline-none"
        value={value}
        onChange={(e) => onChange(clamp(Number(e.target.value) || min))}
      />
      <button type="button" aria-label="More" className="w-9 cursor-pointer text-lg text-muted hover:bg-sunk hover:text-ink" onClick={() => onChange(clamp(value + 1))}>
        +
      </button>
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <Squares total={3} filled={1} size="h-3 w-3" />
      <p className="display text-2xl">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
      {action}
    </div>
  )
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null) return '–'
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${rest}` : `${m}:${rest}`
}

export function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function sourceLabel(run: { title: string | null; source: string }) {
  if (run.title) return run.title.replace(/^[0-9a-f]{12}-/, '')
  if (/^https?:\/\//.test(run.source)) return run.source.replace(/^https?:\/\/(www\.)?/, '')
  return run.source.split(/[\\/]/).pop()?.replace(/^[0-9a-f]{12}-/, '') ?? run.source
}

export function sourceHost(source: string) {
  if (!/^https?:\/\//.test(source)) return 'Local file'
  try {
    return new URL(source).hostname.replace(/^www\./, '')
  } catch {
    return 'Link'
  }
}
