"""Extruder profiles: the shipped ones load, and bad ones are rejected
with a message that names the problem."""

import glob
import os

import pytest

from ur_3d_printer.extruder.profile import (
    ExtruderProfile, ProfileError, load_profile, resolve_profile_path,
)

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'config', 'extruders')


def _minimal(**over):
    d = {
        'name': 'x', 'model': 'x', 'kind': 'filament', 'nozzle_diameter_mm': 0.4,
        'flow': {'max_mm3_s': 10.0},
    }
    d.update(over)
    return {'extruder': d}


@pytest.mark.parametrize('path', sorted(glob.glob(os.path.join(CONFIG_DIR, '*.yaml'))))
def test_shipped_profiles_load(path):
    p = ExtruderProfile.from_yaml(path)
    assert p.model == os.path.splitext(os.path.basename(path))[0]
    assert p.flow.max_mm3_s > 0


def test_mahor_profile_describes_a_two_zone_pellet_screw():
    p = load_profile('mahor_v5_m12_pro')
    assert p.kind == 'pellet_screw'
    assert p.zone_names == ['nozzle', 'barrel']
    assert p.thermal.min_extrusion_temperature == 170.0
    assert p.flow.max_mm3_s == 115.0
    assert not p.has_retract                      # screw: coast, do not reverse
    assert p.retraction.prime_volume_mm3 > 0      # but re-prime on restart
    assert p.has_purge
    assert p.driver == 'gcode_serial'
    assert p.driver_params['port'] == '/dev/ttyACM0'
    assert [z.gcode_heater for z in p.thermal.zones] == ['T0', 'T1']


def test_paste_profile_has_no_thermal_feedback():
    p = load_profile('paste_syringe')
    assert p.thermal.zones == []
    assert p.thermal.feedback is False
    assert p.driver == 'ur_io'


def test_resolve_by_name_and_by_path(tmp_path):
    assert resolve_profile_path('generic_fdm', [CONFIG_DIR]).endswith('generic_fdm.yaml')
    f = tmp_path / 'custom.yaml'
    f.write_text('extruder: {}')
    assert resolve_profile_path(str(f), []) == str(f)
    with pytest.raises(ProfileError, match='not found'):
        resolve_profile_path('nope', [CONFIG_DIR])


def test_defaults_fill_optional_sections():
    p = ExtruderProfile.from_dict(_minimal())
    assert p.flow.default_mm3_s == 10.0
    assert p.thermal.zones == [] and p.thermal.has_heaters is False
    assert p.fan.present is False
    assert p.driver == 'mock'
    assert p.has_retract is False and p.has_purge is False


@pytest.mark.parametrize('bad, match', [
    ({'kind': 'laser'}, 'kind must be'),
    ({'flow': {'max_mm3_s': 0}}, 'max_mm3_s must be'),
    ({'flow': {'max_mm3_s': 10, 'default_mm3_s': 20}}, 'default_mm3_s'),
    ({'thermal': {'min_extrusion_temperature': 170}}, 'no thermal zones'),
    ({'thermal': {'zones': [{'name': 'n', 'max_temperature': 150}],
                  'min_extrusion_temperature': 170}}, 'above zone'),
    ({'retraction': {'enabled': True, 'volume_mm3': 5}}, 'retraction.rate_mm3_s'),
    ({'purge': {'volume_mm3': 5}}, 'purge.rate_mm3_s'),
    ({'driver': 'canbus'}, 'driver.type'),
])
def test_invalid_profiles_are_rejected(bad, match):
    with pytest.raises(ProfileError, match=match):
        ExtruderProfile.from_dict(_minimal(**bad))


def test_missing_required_key():
    with pytest.raises(ProfileError, match="missing required key 'flow'"):
        ExtruderProfile.from_dict({'extruder': {'name': 'a', 'model': 'a', 'kind': 'paste',
                                                'nozzle_diameter_mm': 1}})


def test_zone_lookup():
    p = load_profile('mahor_v5_m12_pro')
    assert p.zone_index('barrel') == 1 and p.zone_index(0) == 0
    with pytest.raises(ProfileError):
        p.zone_index('bed')
    with pytest.raises(ProfileError):
        p.zone_index(5)
