import { useTranslation } from 'react-i18next';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { Segmented } from './Field';

type Theme = 'light' | 'dark' | 'system';

export default function ThemeToggle() {
  const { t } = useTranslation();
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);

  return (
    <Segmented<Theme>
      value={theme}
      onChange={setTheme}
      size="sm"
      aria-label={t('settings.theme')}
      options={[
        { value: 'light', label: t('settings.light') },
        { value: 'dark', label: t('settings.dark') },
        { value: 'system', label: t('settings.system') },
      ]}
    />
  );
}
