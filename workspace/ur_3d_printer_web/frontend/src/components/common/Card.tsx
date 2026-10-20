import { useState } from 'react';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  /** Optional element rendered at the right of the title row (a badge, a
   *  small action). Ignored without `title`. */
  action?: React.ReactNode;
  /** Render the title as a toggle button that expands/collapses the body,
   *  with a chevron that rotates to show state. Requires `title`. */
  collapsible?: boolean;
  /** Only relevant when collapsible. Defaults to expanded. */
  defaultCollapsed?: boolean;
  /** `none` lets content (a canvas, a table) run edge to edge. */
  padding?: 'default' | 'none';
}

/** The one surface container. Title is small-caps muted text, the body
 *  sits on `surface`; everything else in the app stacks these. */
export default function Card({
  title,
  children,
  className = '',
  action,
  collapsible = false,
  defaultCollapsed = false,
  padding = 'default',
}: CardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const isCollapsible = collapsible && Boolean(title);
  const pad = padding === 'none' ? '' : 'p-4';

  const heading = (
    <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
      {title}
    </h3>
  );

  return (
    <section className={`rounded-xl border border-line bg-surface shadow-card ${pad} ${className}`}>
      {title && (
        <div className={`flex items-center justify-between gap-2 ${padding === 'none' ? 'px-4 pt-4' : ''}`}>
          {isCollapsible ? (
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              aria-expanded={!collapsed}
              className="flex min-h-[28px] flex-1 items-center justify-between gap-2 text-left"
            >
              {heading}
              <svg
                className={`h-4 w-4 shrink-0 text-faint transition-transform duration-200 ${
                  collapsed ? '' : 'rotate-180'
                }`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          ) : (
            heading
          )}
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {isCollapsible ? (
        // CSS-only expand/collapse (grid-template-rows 0fr <-> 1fr): the
        // body stays mounted so it can smoothly animate height instead of
        // popping in/out, and never needs JS to measure content height.
        <div
          className={`grid transition-[grid-template-rows] duration-200 ease-in-out ${
            collapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr] mt-3'
          }`}
        >
          <div className="overflow-hidden">{children}</div>
        </div>
      ) : (
        <div className={title ? 'mt-3' : ''}>{children}</div>
      )}
    </section>
  );
}
