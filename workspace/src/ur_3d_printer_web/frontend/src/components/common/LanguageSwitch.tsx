import { useTranslation } from 'react-i18next';
import { useSettingsStore } from '../../stores/useSettingsStore';

export default function LanguageSwitch() {
  const { i18n } = useTranslation();
  const setLanguage = useSettingsStore((s) => s.setLanguage);

  const changeTo = (lang: string) => {
    i18n.changeLanguage(lang);
    setLanguage(lang);
  };

  return (
    <div className="flex gap-1">
      <button
        onClick={() => changeTo('es')}
        className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
          i18n.language === 'es'
            ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 font-medium'
            : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'
        }`}
      >
        Español
      </button>
      <button
        onClick={() => changeTo('en')}
        className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
          i18n.language === 'en'
            ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 font-medium'
            : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'
        }`}
      >
        English
      </button>
    </div>
  );
}
