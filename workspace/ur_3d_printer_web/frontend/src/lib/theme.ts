/** Shared theme helpers for the 3D viewers.
 *
 *  The canvases set their clear colour imperatively rather than via CSS, so
 *  they cannot inherit the dark/light class the rest of the app uses. Both
 *  viewers resolve it through here so the Robot page and Printer > Live
 *  cannot drift apart — RobotJogViewer previously hardcoded the dark value
 *  and stayed dark under the light theme. */
export type ThemeSetting = 'dark' | 'light' | 'system';

export function isDarkTheme(theme: ThemeSetting): boolean {
  return (
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  );
}

/** Matches the `--c-bg` token of each theme (index.css), so the canvas
 *  reads as part of the page rather than a differently coloured hole. */
export function viewerBackground(theme: ThemeSetting): string {
  return isDarkTheme(theme) ? '#0b0f17' : '#f4f6f8';
}

/** Grid line colours per theme: a dark grid on a light bed was invisible
 *  in the old light theme because both were hardcoded for dark. */
export function viewerGrid(theme: ThemeSetting): { major: string; minor: string; bed: string } {
  return isDarkTheme(theme)
    ? { major: '#2b3650', minor: '#1b2335', bed: '#1a2234' }
    : { major: '#c4ccd8', minor: '#dde2ea', bed: '#dfe4ec' };
}
