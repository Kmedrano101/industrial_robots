import { useTranslation } from 'react-i18next';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { Segmented } from './Field';

export default function LanguageSwitch() {
  const { i18n, t } = useTranslation();
  const setLanguage = useSettingsStore((s) => s.setLanguage);

  const changeTo = (lang: string) => {
    i18n.changeLanguage(lang);
    setLanguage(lang);
  };

  return (
    <Segmented<string>
      value={i18n.language.startsWith('en') ? 'en' : 'es'}
      onChange={changeTo}
      size="sm"
      aria-label={t('settings.language')}
      options={[
        { value: 'es', label: 'Español' },
        { value: 'en', label: 'English' },
      ]}
    />
  );
}
