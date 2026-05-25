import { useTranslation } from 'react-i18next';
import { usePrintStore } from '../../stores/usePrintStore';
import { STATE_COLORS } from '../../lib/constants';

export default function StateIndicator() {
  const { t } = useTranslation();
  const stateName = usePrintStore((s) => s.printState.state_name);
  const colorClass = STATE_COLORS[stateName] || STATE_COLORS.IDLE;

  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${colorClass}`} />
      <span className="text-sm font-medium">
        {t(`state.${stateName}`, stateName)}
      </span>
    </span>
  );
}
