import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { api, type Run } from '../api'
import { Button, Empty, Eyebrow, Panel, Squares, StatusChip, sourceHost, sourceLabel, timeAgo } from '../components/ui'

export const STAGE_ORDER = ['download', 'transcribe', 'select', 'plan', 'broll', 'reframe', 'render']

export function useRuns() {
  return useQuery({
    queryKey: ['runs'],
    queryFn: api.runs,
    refetchInterval: (query) => (query.state.data?.some((r) => r.status === 'queued' || r.status === 'running') ? 2000 : 15000),
  })
}

function progress(run: Run) {
  if (run.status === 'completed') return STAGE_ORDER.length
  if (!run.current_stage) return 0
  return STAGE_ORDER.indexOf(run.current_stage)
}

export function RunsPage() {
  const runs = useRuns()
  const navigate = useNavigate()
  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-3">
          <Eyebrow>Library</Eyebrow>
          <h1 className="display text-4xl">
            Runs
          </h1>
        </div>
        <Link to="/">
          <Button variant="ink">
            New clips <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>

      <Panel>
        {runs.isLoading ? (
          <p className="p-6 text-sm text-muted">Loading…</p>
        ) : !runs.data?.length ? (
          <Empty title="No runs yet" action={<Link to="/" className="label text-ink underline underline-offset-4">Clip your first video</Link>}>
            Paste a link or drop a file and clipyyy will cut it into shorts.
          </Empty>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="label border-b border-line text-faint">
                <th className="px-5 py-3 font-medium">Source</th>
                <th className="hidden px-5 py-3 font-medium lg:table-cell">Progress</th>
                <th className="hidden px-5 py-3 font-medium sm:table-cell">Clips</th>
                <th className="hidden px-5 py-3 font-medium sm:table-cell">Format</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="hidden px-5 py-3 text-right font-medium md:table-cell">Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.data.map((run) => (
                <tr
                  key={run.id}
                  onClick={() => navigate(`/runs/${run.id}`)}
                  className="cursor-pointer border-b border-line last:border-0 transition-colors hover:bg-paper"
                >
                  <td className="max-w-0 px-5 py-4">
                    <p className="truncate font-medium">{sourceLabel(run)}</p>
                    <p className="label mt-1 truncate text-faint">
                      {sourceHost(run.source)}
                      {run.status === 'failed' && run.error ? <span className="normal-case tracking-normal text-bad"> · {run.error}</span> : null}
                    </p>
                  </td>
                  <td className="hidden px-5 py-4 lg:table-cell">
                    <Squares total={STAGE_ORDER.length} filled={progress(run)} />
                  </td>
                  <td className="hidden px-5 py-4 font-mono text-[13px] sm:table-cell">
                    {run.status === 'completed' ? run.clip_count : '–'}
                    <span className="text-faint">/{run.options.clip_count}</span>
                  </td>
                  <td className="hidden px-5 py-4 font-mono text-[13px] sm:table-cell">{run.options.aspect_ratio}</td>
                  <td className="px-5 py-4">
                    <StatusChip status={run.status} />
                  </td>
                  <td className="hidden px-5 py-4 text-right font-mono text-[12px] text-muted md:table-cell">{timeAgo(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  )
}
