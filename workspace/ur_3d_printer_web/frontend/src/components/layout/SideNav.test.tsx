import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import SideNav from './SideNav';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { usePrintStore } from '../../stores/usePrintStore';
import { PrintStateEnum } from '../../types/ros';
import i18n from '../../i18n';

beforeEach(async () => {
  await i18n.changeLanguage('es');
  useSettingsStore.setState({ page: 'prepare' });
  usePrintStore.setState({
    printState: { state: PrintStateEnum.IDLE, state_name: 'IDLE', error_message: '' },
  });
});

describe('SideNav', () => {
  it('renders the five pages (rail + bottom bar) and marks the current one', () => {
    render(<SideNav />);
    // Both navs render the same items; each page label appears twice.
    expect(screen.getAllByText('Preparar')).toHaveLength(2);
    expect(screen.getAllByText('Ajustes')).toHaveLength(2);
    expect(screen.getAllByText('Trabajos')).toHaveLength(2);
    const current = screen.getAllByRole('button', { current: 'page' });
    expect(current).toHaveLength(2);
    expect(current[0]).toHaveTextContent('Preparar');
  });

  it('clicking an entry changes the page', () => {
    render(<SideNav />);
    fireEvent.click(screen.getAllByText('Robot')[0]);
    expect(useSettingsStore.getState().page).toBe('robot');
  });

  it('shows a live dot on Monitor while printing', () => {
    usePrintStore.setState({
      printState: { state: PrintStateEnum.PRINTING, state_name: 'PRINTING', error_message: '' },
    });
    const { container } = render(<SideNav />);
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
  });
});
