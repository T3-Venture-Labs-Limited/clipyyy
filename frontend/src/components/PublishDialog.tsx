import { useMutation, useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api, type Clip, type PublishMode } from '../api'
import { Button, Eyebrow, Field, Input, Panel, Textarea, cn } from './ui'

const MODES: { value: PublishMode; label: string }[] = [
  { value: 'queue', label: 'Queue' },
  { value: 'schedule', label: 'Schedule' },
  { value: 'now', label: 'Now' },
  { value: 'draft', label: 'Draft' },
]

export function PublishDialog({ clip, onClose, onDone }: { clip: Clip; onClose: () => void; onDone: () => void }) {
  const channels = useQuery({ queryKey: ['channels'], queryFn: api.channels })
  const [selected, setSelected] = useState<string[]>([])
  const [mode, setMode] = useState<PublishMode>('queue')
  const [when, setWhen] = useState('')
  const [text, setText] = useState(`${clip.caption}\n\n${clip.hashtags.join(' ')}`.trim())
  const [title, setTitle] = useState(clip.post_title || clip.title)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const publish = useMutation({
    mutationFn: () =>
      api.publish(clip.id, {
        channel_ids: selected,
        mode,
        scheduled_at: mode === 'schedule' && when ? new Date(when).toISOString() : null,
        text,
        title,
      }),
    onSuccess: (posts) => {
      const failed = posts.filter((p) => p.status === 'failed')
      if (failed.length) toast.error(`${failed.length} of ${posts.length} failed: ${failed[0].error}`)
      else toast.success(`Sent to Buffer for ${posts.length} channel${posts.length > 1 ? 's' : ''}`)
      onDone()
      onClose()
    },
    onError: (e) => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4 backdrop-blur-[2px]" onClick={onClose}>
      <Panel role="dialog" aria-modal="true" aria-label="Post with Buffer" className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between border-b border-line px-6 py-5">
          <div className="flex flex-col gap-2">
            <Eyebrow>Clip #{clip.rank}</Eyebrow>
            <h2 className="display text-2xl">Post with Buffer</h2>
          </div>
          <button aria-label="Close" onClick={onClose} className="cursor-pointer p-1 text-faint hover:text-ink">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-col gap-6 p-6">
          <Field label="Channels" group>
            {channels.isLoading && <p className="text-sm text-muted">Loading channels…</p>}
            {channels.error && <p className="text-sm text-bad">{channels.error.message}</p>}
            <div className="grid gap-1.5 sm:grid-cols-2">
              {(channels.data ?? []).map((ch) => {
                const on = selected.includes(ch.id)
                return (
                  <button
                    key={ch.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setSelected(on ? selected.filter((id) => id !== ch.id) : [...selected, ch.id])}
                    className={cn(
                      'flex cursor-pointer items-center gap-3 border px-3 py-2.5 text-left text-sm transition-colors',
                      on ? 'border-ink bg-paper' : 'border-line hover:border-line-strong',
                    )}
                  >
                    {ch.avatar ? <img src={ch.avatar} alt="" className="px-sm h-7 w-7" /> : <span className="h-7 w-7 bg-sunk" />}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{ch.name}</span>
                      <span className="label block !text-[10px] text-faint">{ch.service}</span>
                    </span>
                    <span className={cn('h-3 w-3 border', on ? 'border-ink bg-acid' : 'border-line-strong')} />
                  </button>
                )
              })}
            </div>
          </Field>

          <Field label="When" group>
            <div className="grid grid-cols-4 border border-line-strong">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  aria-pressed={mode === m.value}
                  onClick={() => setMode(m.value)}
                  className={cn(
                    'h-9 cursor-pointer border-r border-line text-[13px] font-medium last:border-0 transition-colors',
                    mode === m.value ? 'bg-ink text-white' : 'text-muted hover:text-ink',
                  )}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </Field>
          {mode === 'schedule' && (
            <Field label="Date and time">
              <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
            </Field>
          )}
          <Field label="Title" hint="Used for YouTube Shorts">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} />
          </Field>
          <Field label="Post text">
            <Textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
        </div>

        <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="acid" disabled={!selected.length || (mode === 'schedule' && !when)} loading={publish.isPending} onClick={() => publish.mutate()}>
            {mode === 'now' ? 'Post now' : mode === 'draft' ? 'Save draft' : mode === 'schedule' ? 'Schedule' : 'Add to queue'}
          </Button>
        </div>
      </Panel>
    </div>
  )
}
