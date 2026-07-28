import { useState } from 'react';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  /** Render the title as a toggle button that expands/collapses the body,
   *  with a chevron that rotates to show state (dropdown effect).
   *  Requires `title`. Off by default — existing Card usages elsewhere in
   *  the app keep their original, always-expanded rendering. */
  collapsible?: boolean;
  /** Only relevant when collapsible. Defaults to expanded. */
  defaultCollapsed?: boolean;
}

export default function Card({
  title,
  children,
  className = '',
  collapsible = false,
  defaultCollapsed = false,
}: CardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const isCollapsible = collapsible && Boolean(title);

  return (
    <div
      className={`rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 ${className}`}
    >
      {title && (
        isCollapsible ? (
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-expanded={!collapsed}
            className="flex w-full items-center justify-between gap-2 text-left"
          >
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              {title}
            </h3>
            <svg
              className={`h-4 w-4 shrink-0 text-gray-400 transition-transform duration-200 ${
                collapsed ? '' : 'rotate-180'
              }`}
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        ) : (
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
            {title}
          </h3>
        )
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
        children
      )}
    </div>
  );
}
