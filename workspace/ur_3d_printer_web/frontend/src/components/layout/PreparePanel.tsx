import FileUpload from '../controls/FileUpload';
import SliceSettingsPanel from '../controls/SliceSettings';
import PrintControlPanel from '../controls/PrintControlPanel';
import WorkflowSteps from '../controls/WorkflowSteps';
import SliceSummary from '../controls/SliceSummary';
import ExtruderPanel from '../controls/ExtruderPanel';
import PrintProgress from '../status/PrintProgress';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';

/** Import → slice → print, top to bottom. The pipeline is stated up-front
 *  and stays visible, so the steps that are not yet applicable
 *  (SliceSettings renders nothing without a file) are still accounted for. */
export default function PreparePanel() {
  const printState = usePrintStore((s) => s.printState.state);
  const isPrinting =
    printState === PrintStateEnum.PRINTING ||
    printState === PrintStateEnum.PAUSED ||
    printState === PrintStateEnum.TRAVEL_MOVE ||
    printState === PrintStateEnum.LAYER_CHANGE;

  return (
    <div className="space-y-3">
      <WorkflowSteps />
      <FileUpload />
      <SliceSettingsPanel />
      <SliceSummary />
      <PrintControlPanel />
      {isPrinting && <PrintProgress />}
      <ExtruderPanel />
    </div>
  );
}
