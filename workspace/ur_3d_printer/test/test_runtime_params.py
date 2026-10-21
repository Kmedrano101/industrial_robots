"""Hot-reloadable print_node parameters: validation and derived frames."""

import math

import numpy as np
import pytest

from ur_3d_printer.runtime_params import (
    HOT_PARAMS, RuntimeConfig, build_print_frame, validate_updates, validate_value,
)


def test_valid_batch_while_idle_is_accepted():
    assert validate_updates({'max_print_velocity': 0.08, 'z_hop_enabled': False,
                             'print_origin_xyz': [-0.3, 0.0, -0.01]}, busy=False) is None


def test_any_hot_change_is_rejected_while_printing():
    why = validate_updates({'z_hop_height': 0.01}, busy=True)
    assert why and 'print in progress' in why


def test_static_params_pass_through_even_when_busy():
    assert validate_updates({'publish_rate': 5.0}, busy=True) is None


@pytest.mark.parametrize('name, value, needle', [
    ('max_print_velocity', 2.0, 'outside'),
    ('max_print_velocity', True, 'number'),
    ('z_hop_enabled', 1, 'bool'),
    ('home_joints', [0.0] * 5, 'needs 6'),
    ('print_origin_xyz', [0, 0, 9], 'within'),
    ('tool_offset_xyz', ['a', 0, 0], 'numbers'),
    ('max_acceleration', float('nan'), 'outside'),
])
def test_bad_values(name, value, needle):
    assert needle in validate_value(name, value)


def test_print_frame_matches_translation_and_tilt():
    f = build_print_frame([-0.3, 0.1, 0.02], [0, 0, 0])
    assert np.allclose(f[:3, 3], [-0.3, 0.1, 0.02]) and np.allclose(f[:3, :3], np.eye(3))
    t = build_print_frame([0, 0, 0], [0, 0, 0], tilt_rx=0.1)
    # A point 100 mm along +Y on a bed tilted about X rises by sin(0.1)·0.1
    p = t @ np.array([0, 0.1, 0, 1])
    assert p[2] == pytest.approx(math.sin(0.1) * 0.1)


def test_runtime_config_merge_ignores_unknown_keys():
    rc = RuntimeConfig({k: 0 for k in HOT_PARAMS})
    out = rc.merged({'z_hop_height': 0.01, 'publish_rate': 9})
    assert out['z_hop_height'] == 0.01 and 'publish_rate' not in out
    assert rc.values['z_hop_height'] == 0, 'merge does not mutate'
