import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Card from '../common/Card';
import Badge from '../common/Badge';
import Button from '../common/Button';
import { api } from '../../lib/api';
import { usePrintStore } from '../../stores/usePrintStore';
import type { Severity } from '../../lib/status';

export interface Job {
  id: string;
  started_at: number;
  finished_at: number | null;
  status: 'running' | 'completed' | 'cancelled' | 'error';
  filename: string | null;
  gcode_path: string | null;
  material: string | null;
  slicer_mode: string | null;
  layer_height: number | null;
  nozzle_diameter: number | null;
  infill_pattern: string | null;
  infill_density: number | null;
  num_layers: number | null;
  estimated_time: number | null;
  layers_done: number | null;
  elapsed_time: number | null;
  error_message: string | null;
  source: 'web' | 'external';
}

const STATUS_SEVERITY: Record<Job['status'], Severity> = {
  running: 'ok',
  completed: 'ok',
  cancelled: 'neutral',
  error: 'danger',
};

function fmtDate(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

function fmtDuration(job: Job): string {
  const s =
    job.elapsed_time ??
    (job.finished_at ? job.finished_at - job.started_at : Date.now() / 1000 - job.started_at);
  if (!Number.isFinite(s) || s <= 0) return '—';
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

/** Print history, newest first. Refreshes when the print state changes so
 *  a job that just finished appears without a manual reload. */
export default function JobsPage() {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const printStateName = usePrintStore((s) => s.printState.state_name);

  const load = useCallback(async () => {
    try {
      const r = await api.get<{ jobs: Job[] }>('/jobs?limit=200');
      setJobs(r.jobs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, printStateName]);

  const remove = async (job: Job) => {
    if (!window.confirm(t('jobs.confirmDelete'))) return;
    await api.delete(`/jobs/${job.id}`).catch(() => {});
    void load();
  };

  const clear = async () => {
    if (!window.confirm(t('jobs.confirmClear'))) return;
    await api.delete('/jobs').catch(() => {});
    void load();
  };

  const finished = jobs.filter((j) => j.status !== 'running').length;

  return (
    <div className="scroll-thin flex-1 overflow-y-auto bg-bg p-4 sm:p-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{t('jobs.title')}</h2>
            <p className="text-xs text-muted">{t('jobs.count', { count: jobs.length })}</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void load()}>
              {t('jobs.refresh')}
            </Button>
            <Button size="sm" variant="ghost" onClick={clear} disabled={finished === 0}>
              {t('jobs.clear')}
            </Button>
          </div>
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        {jobs.length === 0 ? (
          <Card>
            <div className="py-8 text-center">
              <p className="text-sm font-medium">{t('jobs.empty')}</p>
              <p className="mt-1 text-xs text-muted">{t('jobs.emptyHint')}</p>
            </div>
          </Card>
        ) : (
          <Card padding="none">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[11px] uppercase tracking-[0.06em] text-muted">
                  <th className="px-4 py-2.5 font-medium">{t('jobs.started')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('jobs.file')}</th>
                  <th className="hidden px-4 py-2.5 font-medium md:table-cell">{t('jobs.material')}</th>
                  <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('jobs.layers')}</th>
                  <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('jobs.duration')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('jobs.status')}</th>
                  <th className="px-2 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => {
                  const expanded = open === job.id;
                  return (
                    <JobRow
                      key={job.id}
                      job={job}
                      expanded={expanded}
                      onToggle={() => setOpen(expanded ? null : job.id)}
                      onDelete={() => remove(job)}
                    />
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </div>
  );
}

function JobRow({
  job, expanded, onToggle, onDelete,
}: { job: Job; expanded: boolean; onToggle: () => void; onDelete: () => void }) {
  const { t } = useTranslation();
  const name = job.filename ?? t('jobs.unknownFile');
  const layers =
    job.num_layers != null
      ? job.status === 'completed'
        ? String(job.num_layers)
        : `${job.layers_done ?? 0}/${job.num_layers}`
      : '—';

  const details: [string, string][] = [
    ['slicer_mode', job.slicer_mode ?? '—'],
    ['layer_height', job.layer_height != null ? `${job.layer_height} mm` : '—'],
    ['nozzle_diameter', job.nozzle_diameter != null ? `${job.nozzle_diameter} mm` : '—'],
    ['infill', job.infill_pattern ? `${job.infill_pattern} · ${Math.round((job.infill_density ?? 0) * 100)}%` : '—'],
    ['estimated', job.estimated_time != null ? `${Math.round(job.estimated_time / 60)} min` : '—'],
    ['gcode', job.gcode_path ?? '—'],
  ];

  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer border-b border-line/70 last:border-b-0 hover:bg-surface2/60"
        aria-expanded={expanded}
      >
        <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-muted">{fmtDate(job.started_at)}</td>
        <td className="max-w-[220px] truncate px-4 py-2.5 font-medium" title={name}>
          {name}
          {job.source === 'external' && (
            <span className="ml-1.5 text-[10px] font-normal text-faint" title={t('jobs.external')}>ROS</span>
          )}
        </td>
        <td className="hidden px-4 py-2.5 uppercase text-muted md:table-cell">{job.material ?? '—'}</td>
        <td className="hidden px-4 py-2.5 font-mono text-xs sm:table-cell">{layers}</td>
        <td className="hidden px-4 py-2.5 font-mono text-xs sm:table-cell">{fmtDuration(job)}</td>
        <td className="px-4 py-2.5">
          <Badge severity={STATUS_SEVERITY[job.status]} dot>
            {t(`jobs.${job.status}`)}
          </Badge>
        </td>
        <td className="px-2 py-2.5 text-right">
          {job.status !== 'running' && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="rounded-md p-2 text-faint hover:bg-surface2 hover:text-danger"
              aria-label={t('jobs.delete')}
              title={t('jobs.delete')}
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-line/70 bg-surface2/40 last:border-b-0">
          <td colSpan={7} className="px-4 py-3">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">
              {t('jobs.settingsOf', { name })}
            </p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
              {details.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 border-b border-line/50 py-1">
                  <dt className="text-muted">{k}</dt>
                  <dd className="truncate font-mono text-ink" title={v}>{v}</dd>
                </div>
              ))}
            </dl>
            {job.error_message && <p className="mt-2 text-xs text-danger">{job.error_message}</p>}
          </td>
        </tr>
      )}
    </>
  );
}
