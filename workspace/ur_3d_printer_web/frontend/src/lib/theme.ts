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

export function viewerBackground(theme: ThemeSetting): string {
  return isDarkTheme(theme) ? '#1a1a2e' : '#f0f0f0';
}
