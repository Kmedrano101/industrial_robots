#!/usr/bin/env bash
# Pick the CycloneDDS config that suits the machine we booted on.
#
# config/cyclonedds.xml pins DDS to the NIC holding the robot-network address
# (200.200.2.1). That is what we want in the lab: it keeps discovery on the
# robot link and off the office LAN. But on any machine without that NIC —
# a laptop, CI — CycloneDDS finds no usable interface and every ROS node dies
# with "RCLError: error creating node", which reads as a ROS fault rather than
# a networking one and has repeatedly cost debugging time.
#
# Merging both into one file does not work: if the pinned address IS present,
# also listing an autodetermine entry makes CycloneDDS resolve the same
# interface twice and fail with the identical error. So we keep two mutually
# exclusive files and choose between them here, at startup.
#
# Sourced by the container entrypoints; exports CYCLONEDDS_URI.
#
# Env:
#   DDS_PINNED_ADDR   address that selects the pinned config (default 200.200.2.1)
#   CYCLONEDDS_URI    if already pointing at a readable file, left untouched,
#                     so an explicit override always wins.

_dds_pinned_addr="${DDS_PINNED_ADDR:-200.200.2.1}"
_dds_pinned_cfg="/config/cyclonedds.xml"
_dds_auto_cfg="/config/cyclonedds-auto.xml"

# Can we bind to the pinned address? Binding is the most portable presence
# check available: it needs no `ip`/`ifconfig` binary, just the stdlib, and
# fails with EADDRNOTAVAIL precisely when the address is not local.
_dds_addr_is_local() {
  python3 - "$1" <<'PY' >/dev/null 2>&1
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.bind((sys.argv[1], 0))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

if [ -n "${CYCLONEDDS_URI:-}" ] && [ -f "${CYCLONEDDS_URI#file://}" ] \
   && [ "${CYCLONEDDS_URI#file://}" != "$_dds_pinned_cfg" ]; then
  echo "[dds] honouring explicit CYCLONEDDS_URI=${CYCLONEDDS_URI}"
elif _dds_addr_is_local "$_dds_pinned_addr" && [ -f "$_dds_pinned_cfg" ]; then
  export CYCLONEDDS_URI="file://${_dds_pinned_cfg}"
  echo "[dds] ${_dds_pinned_addr} present — using pinned config ${_dds_pinned_cfg}"
elif [ -f "$_dds_auto_cfg" ]; then
  export CYCLONEDDS_URI="file://${_dds_auto_cfg}"
  echo "[dds] ${_dds_pinned_addr} not on this host — falling back to ${_dds_auto_cfg}"
  echo "[dds] (off the robot network: DDS will auto-select an interface)"
else
  echo "[dds] WARNING: no CycloneDDS config found; using library defaults"
fi
