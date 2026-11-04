import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { api, type Setting } from '../api'
import { ModelInput } from '../components/ModelInput'
import { Button, Eyebrow, Field, Input, Panel, Select, Textarea, cn } from '../components/ui'

const WHISPER_MODELS = [
  ['tiny', 'tiny · fastest'],
  ['base', 'base · fast'],
  ['small', 'small · balanced (default)'],
  ['medium', 'medium · more accurate'],
  ['large-v3', 'large-v3 · best, GPU recommended'],
  ['turbo', 'turbo · near large-v3, faster'],
]

const SECTIONS = [
  ['ai', 'AI'],
  ['downloads', 'Downloads'],
  ['broll', 'B-roll'],
  ['publishing', 'Publishing'],
] as const

export function SettingsPage() {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const [draft, setDraft] = useState<Record<string, string>>({})

  useEffect(() => {
    if (settings.data) setDraft(Object.fromEntries(settings.data.map((s) => [s.key, s.secret ? '' : s.value])))
  }, [settings.data])

  const byKey: Record<string, Setting> = Object.fromEntries((settings.data ?? []).map((s) => [s.key, s]))
  const orgs = useQuery({ queryKey: ['orgs'], queryFn: api.organizations, enabled: !!byKey.buffer_api_key?.is_set })

  const changes = () => {
    const values: Record<string, string | null> = {}
    for (const s of settings.data ?? []) {
      const next = draft[s.key] ?? ''
      if (s.secret ? next : next !== s.value) values[s.key] = next || null
    }
    return values
  }
  const dirty = Object.keys(changes()).length > 0

  const save = useMutation({
    mutationFn: () => api.saveSettings(changes()),
    onSuccess: () => {
      toast.success('Saved on this machine')
      queryClient.invalidateQueries()
    },
    onError: (e) => toast.error(e.message),
  })
  const clear = useMutation({
    mutationFn: (key: string) => api.saveSettings({ [key]: null }),
    onSuccess: () => queryClient.invalidateQueries(),
  })

  if (settings.isLoading) return <p className="text-muted">Loading…</p>

  const update = (key: string) => (value: string) => setDraft((d) => ({ ...d, [key]: value }))
  const text = (key: string, placeholder?: string) => (
    <Input value={draft[key] ?? ''} placeholder={placeholder} onChange={(e) => update(key)(e.target.value)} />
  )
  const secret = (key: string, placeholder: string) => {
    const s = byKey[key]
    return (
      <div className="flex gap-2">
        <Input
          type="password"
          autoComplete="off"
          className="font-mono"
          value={draft[key] ?? ''}
          placeholder={s?.is_set ? `${s.value}${s.source === 'env' ? '  (from env)' : ''}` : placeholder}
          onChange={(e) => update(key)(e.target.value)}
        />
        {s?.is_set && s.source === 'app' && (
          <Button variant="line" onClick={() => clear.mutate(key)}>
            Remove
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-3">
          <Eyebrow>Your keys stay on this machine</Eyebrow>
          <h1 className="display text-4xl">
            Settings
          </h1>
          <p className="max-w-xl text-[15px] text-body">Everything is stored locally in clipyyy.db. Environment variables work too and show up here.</p>
        </div>
        <Button loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
          {dirty ? 'Save changes' : 'Saved'}
        </Button>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="flex flex-col gap-6 lg:sticky lg:top-8">
          <nav className="hidden flex-col gap-0.5 lg:flex">
            {SECTIONS.map(([id, name]) => (
              <a key={id} href={`#${id}`} className="label flex h-9 items-center px-3 text-muted transition-colors hover:bg-sunk hover:text-ink">
                {name}
              </a>
            ))}
          </nav>
          <Panel className="flex flex-col">
            <p className="label border-b border-line px-4 py-3 text-ink">System check</p>
            {(health.data?.checks ?? []).map((c) => (
              <div key={c.name} className="flex items-start gap-3 border-b border-line px-4 py-3 last:border-0">
                <span className={cn('mt-1 h-2 w-2 shrink-0', c.ok ? 'bg-ok' : c.required ? 'bg-bad' : 'bg-line-strong')} />
                <div className="min-w-0">
                  <p className="text-[13px] font-medium">{c.label}</p>
                  <p className="text-[12px] leading-snug text-muted">{c.detail}</p>
                </div>
              </div>
            ))}
          </Panel>
        </aside>

        <div className="flex flex-col gap-6">
          <Section id="ai" title="AI" description="A language model reads the transcript and picks the clips. OpenRouter gives you every major model with one key.">
            <Field label="OpenRouter API key" hint={<Ext href="https://openrouter.ai/keys">Create a key</Ext>}>
              {secret('openrouter_api_key', 'sk-or-…')}
            </Field>
            <Field label="Default model" hint="Type to search. Fast, cheap long-context models work well; a one-hour video is about 15k tokens.">
              <ModelInput value={draft.llm_model ?? ''} onChange={update('llm_model')} />
            </Field>
            <Field label="Transcription model" hint="faster-whisper runs locally and downloads the model on first use.">
              <Select value={draft.whisper_model ?? 'small'} onChange={(e) => update('whisper_model')(e.target.value)}>
                {WHISPER_MODELS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Default instructions" hint="Added to every run: your audience, tone, or a call to action for captions.">
              <Textarea
                rows={3}
                value={draft.default_instructions ?? ''}
                onChange={(e) => update('default_instructions')(e.target.value)}
                placeholder="Audience: indie founders. End every caption with “Follow for more build-in-public clips.”"
              />
            </Field>
          </Section>

          <Section
            id="downloads"
            title="Downloads"
            tag="If YouTube blocks you"
            description="YouTube sometimes asks a network to prove it is not a bot. clipyyy can then borrow your browser's YouTube login, read locally by yt-dlp."
          >
            <Field label="Use cookies from browser" hint="Pick the browser where you are signed in to YouTube. Close it first if downloads fail to read cookies.">
              <Select value={draft.ytdlp_cookies_from_browser ?? ''} onChange={(e) => update('ytdlp_cookies_from_browser')(e.target.value)}>
                <option value="">Don't use cookies</option>
                {['chrome', 'chromium', 'brave', 'edge', 'firefox', 'opera', 'vivaldi', 'safari'].map((b) => (
                  <option key={b} value={b}>
                    {b[0].toUpperCase() + b.slice(1)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Or a cookies.txt file" hint="Absolute path to a Netscape-format cookies file. Takes priority over the browser.">
              {text('ytdlp_cookies_file', '/path/to/cookies.txt')}
            </Field>
          </Section>

          <Section id="broll" title="B-roll" tag="Optional" description="Cuts in free stock footage that matches what is being said.">
            <Field label="Pexels API key" hint={<Ext href="https://www.pexels.com/api/">Get a free key</Ext>}>
              {secret('pexels_api_key', 'Pexels key')}
            </Field>
          </Section>

          <Section
            id="publishing"
            title="Publishing"
            tag="Optional"
            description="Clips are always downloadable. Connect Buffer to post or schedule them to TikTok, Instagram, YouTube and more."
          >
            <Field label="Buffer API key" hint={<Ext href="https://publish.buffer.com/settings/api">Create a key in Buffer</Ext>}>
              {secret('buffer_api_key', 'Buffer key')}
            </Field>
            {(orgs.data?.length ?? 0) > 1 && (
              <Field label="Organization">
                <Select value={draft.buffer_organization_id ?? ''} onChange={(e) => update('buffer_organization_id')(e.target.value)}>
                  <option value="">First organization</option>
                  {orgs.data!.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            {orgs.error && <p className="text-[13px] text-bad">{orgs.error.message}</p>}

            <div className="border-t border-line pt-6">
              <p className="label text-ink">Video hosting for Buffer</p>
              <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-muted">
                Buffer fetches videos from a public link, so each clip is uploaded to your own S3-compatible bucket first: Cloudflare R2,
                Backblaze B2, AWS S3 or MinIO.
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Endpoint URL" hint="Leave empty for AWS S3">
                {text('s3_endpoint_url', 'https://<account>.r2.cloudflarestorage.com')}
              </Field>
              <Field label="Region">{text('s3_region', 'auto')}</Field>
              <Field label="Bucket">{text('s3_bucket')}</Field>
              <Field label="Public base URL" hint="Optional. Without it, links are signed for 7 days">
                {text('s3_public_base_url', 'https://media.example.com')}
              </Field>
              <Field label="Access key ID">{secret('s3_access_key_id', 'Access key ID')}</Field>
              <Field label="Secret access key">{secret('s3_secret_access_key', 'Secret')}</Field>
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

function Section({ id, title, tag, description, children }: { id: string; title: string; tag?: string; description: string; children: ReactNode }) {
  return (
    <Panel id={id} className="scroll-mt-8">
      <div className="flex flex-col gap-1.5 border-b border-line px-6 py-5">
        <div className="flex items-center gap-3">
          <h2 className="display text-xl">{title}</h2>
          {tag && <span className="label px-sm bg-sunk px-2 py-0.5 !text-[10px] text-muted">{tag}</span>}
        </div>
        <p className="max-w-2xl text-[13px] leading-relaxed text-muted">{description}</p>
      </div>
      <div className="flex flex-col gap-6 p-6">{children}</div>
    </Panel>
  )
}

function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-ink underline underline-offset-2">
      {children} <ArrowUpRight className="h-3 w-3" />
    </a>
  )
}
