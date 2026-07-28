import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Translations are BUNDLED, not fetched at runtime.
//
// They used to be loaded over HTTP from /locales/{lng}/translation.json via
// i18next-http-backend. That split the app across two independently cached
// artifacts: the JS bundle (content-hashed, so always fresh) and the locale
// JSON (stable filename, so freely cacheable). After a redeploy a browser
// could end up running NEW code against an OLD locale file, and every key
// added in that release rendered as its raw id ("test.simulationMode") until
// the user manually hard-refreshed.
//
// Importing the JSON makes it part of the same content-hashed bundle as the
// code that references it, so the two can never disagree — the failure mode
// is structurally impossible rather than merely unlikely. Server-side
// Cache-Control (see backend/main.py) still guards the remaining
// stable-filename assets like index.html.
//
// The files stay in public/locales/ so they remain the single source of
// truth and keep being served as plain static assets; nothing fetches them
// at runtime any more.
import es from '../public/locales/es/translation.json';
import en from '../public/locales/en/translation.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      es: { translation: es },
      en: { translation: en },
    },
    fallbackLng: 'es',
    supportedLngs: ['es', 'en'],
    ns: ['translation'],
    defaultNS: 'translation',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;
