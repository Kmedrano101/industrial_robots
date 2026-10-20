import { beforeEach, describe, expect, it } from 'vitest';
import { usePrintStore, TEMP_HISTORY_MAX, LOG_MAX } from './usePrintStore';
import { PrintStateEnum } from '../types/ros';

beforeEach(() => {
  usePrintStore.setState({
    printState: { state: PrintStateEnum.IDLE, state_name: 'IDLE', error_message: '' },
    temperatureHistory: [],
    eventLog: [],
  });
});

describe('usePrintStore.setPrintState', () => {
  it('canonicalises the display names print_node publishes', () => {
    usePrintStore.getState().setPrintState({
      state: PrintStateEnum.PRINTING, state_name: 'Printing', error_message: '',
    });
    expect(usePrintStore.getState().printState.state_name).toBe('PRINTING');
    usePrintStore.getState().setPrintState({
      state: PrintStateEnum.LAYER_CHANGE, state_name: 'Layer change', error_message: '',
    });
    expect(usePrintStore.getState().printState.state_name).toBe('LAYER_CHANGE');
  });

  it('keeps an unknown numeric state name as sent', () => {
    usePrintStore.getState().setPrintState({
      state: 99 as PrintStateEnum, state_name: 'Future state', error_message: '',
    });
    expect(usePrintStore.getState().printState.state_name).toBe('Future state');
  });
});

describe('bounded buffers', () => {
  it('temperature history never exceeds its window', () => {
    const s = usePrintStore.getState();
    for (let i = 0; i < TEMP_HISTORY_MAX + 20; i++) {
      s.setExtruderState({ state: 0, extrusion_rate: 0, temperature: i, target_temperature: 0, at_temperature: false });
    }
    const h = usePrintStore.getState().temperatureHistory;
    expect(h).toHaveLength(TEMP_HISTORY_MAX);
    expect(h[h.length - 1].temp).toBe(TEMP_HISTORY_MAX + 19);
  });

  it('event log collapses consecutive duplicates and stays bounded', () => {
    const s = usePrintStore.getState();
    s.addLogEntry('info', 'same');
    s.addLogEntry('info', 'same');
    expect(usePrintStore.getState().eventLog).toHaveLength(1);
    for (let i = 0; i < LOG_MAX + 5; i++) s.addLogEntry('info', `e${i}`);
    expect(usePrintStore.getState().eventLog).toHaveLength(LOG_MAX);
  });
});
