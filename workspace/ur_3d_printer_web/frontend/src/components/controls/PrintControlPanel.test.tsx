import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import PrintControlPanel from './PrintControlPanel';
import { usePrintStore } from '../../stores/usePrintStore';
import { useRobotStore } from '../../stores/useRobotStore';
import { PrintStateEnum } from '../../types/ros';
import i18n from '../../i18n';

const slice = {
  gcodeFilepath: '/uploads/x.gcode',
  numLayers: 3,
  estimatedTime: 10,
  layers: [],
  nozzleDiameter: 0.4,
  material: 'PLA',
  slicerMode: 'planar' as const,
  layerHeight: 0.2,
  infillPattern: 'none',
  infillDensity: 0.2,
};

beforeEach(async () => {
  await i18n.changeLanguage('en');
  useRobotStore.setState(useRobotStore.getInitialState());
  usePrintStore.setState({
    printState: { state: PrintStateEnum.IDLE, state_name: 'IDLE', error_message: '' },
    sliceResult: null,
  });
});

describe('PrintControlPanel', () => {
  it('Start is inert and explains itself when no robot is connected', () => {
    usePrintStore.setState({ sliceResult: slice });
    render(<PrintControlPanel />);
    const start = screen.getByRole('button', { name: i18n.t('controls.start') });
    expect(start).toBeDisabled();
    expect(start).toHaveAttribute('title', i18n.t('controls.blocked.noRobot'));
  });

  it('Start needs a slice even with a robot', () => {
    useRobotStore.getState().setRobotMode({ mode: 7, mode_name: 'RUNNING' });
    render(<PrintControlPanel />);
    const start = screen.getByRole('button', { name: i18n.t('controls.start') });
    expect(start).toBeDisabled();
    expect(screen.getByText(new RegExp(i18n.t('controls.blocked.notSliced')))).toBeInTheDocument();
  });

  it('Start is enabled with robot + slice and the robot idle', () => {
    useRobotStore.getState().setRobotMode({ mode: 7, mode_name: 'RUNNING' });
    usePrintStore.setState({ sliceResult: slice });
    render(<PrintControlPanel />);
    expect(screen.getByRole('button', { name: i18n.t('controls.start') })).toBeEnabled();
    expect(screen.getByRole('button', { name: i18n.t('controls.pause') })).toBeDisabled();
  });

  it('while printing only pause and cancel are available', () => {
    useRobotStore.getState().setRobotMode({ mode: 7, mode_name: 'RUNNING' });
    usePrintStore.setState({
      sliceResult: slice,
      printState: { state: PrintStateEnum.PRINTING, state_name: 'PRINTING', error_message: '' },
    });
    render(<PrintControlPanel />);
    expect(screen.getByRole('button', { name: i18n.t('controls.start') })).toBeDisabled();
    expect(screen.getByRole('button', { name: i18n.t('controls.pause') })).toBeEnabled();
    expect(screen.getByRole('button', { name: i18n.t('controls.resume') })).toBeDisabled();
    expect(screen.getByRole('button', { name: i18n.t('controls.cancel') })).toBeEnabled();
  });
});
