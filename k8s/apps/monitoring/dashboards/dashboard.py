"""Regenerates homelab-server.json. Run: python3 dashboard.py, then prettier --write."""

import json
from pathlib import Path

from panels import chart, layout, ok_until, stat, steps

HOUR = 3600
RATE = "[$__rate_interval]"
CONTAINER = '{container!="",pod!=""}'
DISKS = '{device=~"sda|nvme0n1"}'
FS = '{mountpoint=~"/|/home|/var|/tank"}'
IDLE, BUSY = '{mode="idle"}', '{mode!="idle"}'
HASH = "-[bcdfghjklmnpqrstvwxz2456789]{8,10}"

USED_PCT = f"100*(1-node_filesystem_avail_bytes{FS}/node_filesystem_size_bytes{FS})"
MEM_USED = "node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes"
POOL = 'node_zfs_zpool_state{zpool="tank",state="online"}'
NEXT_BACKUP = "min(volsync_backup_next_sync_timestamp_seconds) - time()"
NIC = '{device="enp3s0"}'
CPU_TEMP = 'node_hwmon_temp_celsius{chip="pci0000:00_0000:00:18_3"}'
NVME_TEMP = 'node_hwmon_temp_celsius{chip="nvme_nvme0"}'
FRIGATE_AGE = 'time() - volsync_backup_last_sync_timestamp_seconds{name="frigate-media"}'
FAILED = 'count(volsync_backup_last_result{result!="Successful"}) or vector(0)'

USAGE, FRIGATE_OLD = ok_until(70, 90), ok_until(3 * HOUR, 12 * HOUR)
ONLINE = [{"type": "value", "options": {"1": {"text": "ONLINE", "color": "green"}, "0": {"text": "PROBLEM", "color": "red"}}}]


def rate(metric, selector=""):
    return f"rate({metric}{selector}{RATE})"


def by_disk(expr):
    return f'label_replace(label_replace({expr}, "disk", "hdd", "device", "sda"), "disk", "nvme", "device", "nvme0n1")'


def by_deployment(inner):
    """Strips the pod suffixes so a replaced pod stays on the same line."""
    pod = f'label_replace({inner}, "app", "$1", "pod", "(.*)")'
    return f'topk(10, sum by(app)(label_replace({pod}, "app", "$1", "app", "(.+?)({HASH})?-[a-z0-9]{{5}}")))'


cpu = stat("CPU", f"100 - avg({rate('node_cpu_seconds_total', IDLE)})*100", thr=USAGE, lo=0, hi=100)
memory = stat("Memory", "100*(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)", thr=USAGE, lo=0, hi=100)
cpu_temp = stat("CPU temp", CPU_TEMP, unit="celsius", thr=ok_until(70, 85))
uptime = stat("Uptime", "time() - node_boot_time_seconds", unit="s", dec=1)
zfs_pool = stat("ZFS pool", POOL, unit="none", mappings=ONLINE, thr=steps(("red", None), ("green", 1)))
frigate_backup = stat("Frigate last backup", FRIGATE_AGE, unit="s", dec=1, thr=FRIGATE_OLD)
next_backup = stat("Next backup", NEXT_BACKUP, unit="s")
backup_failures = stat("Backup failures", FAILED, unit="none", thr=steps(("green", None), ("red", 1)))

cpu_by_mode = chart("CPU by mode", [(f"avg by(mode)({rate('node_cpu_seconds_total', BUSY)})*100", "{{mode}}")], unit="percent", stack=True, hi=100)
memory_usage = chart("Memory", [(MEM_USED, "used"), ("node_zfs_arc_size", "ZFS cache"), ("node_memory_MemTotal_bytes", "total")], unit="bytes")
disk_used = chart("Disk used", [(USED_PCT, "{{mountpoint}}")], unit="percent", hi=100)
cpu_by_deployment = chart("CPU by deployment", [(by_deployment(rate("container_cpu_usage_seconds_total", CONTAINER)), "{{app}}")])
memory_by_deployment = chart("Memory by deployment", [(by_deployment(f"container_memory_working_set_bytes{CONTAINER}"), "{{app}}")], unit="bytes")
disk_busy = chart("Disk busy", [(by_disk(rate("node_disk_io_time_seconds_total", DISKS) + "*100"), "{{disk}}")], unit="percent", hi=100)
network = chart(
    "Network",
    [(rate("node_network_receive_bytes_total", NIC) + "*8", "download"), (rate("node_network_transmit_bytes_total", NIC) + "*8", "upload")],
    unit="bps",
)
temperatures = chart("Temperatures", [(CPU_TEMP, "CPU"), (NVME_TEMP, "NVMe")], unit="celsius")
disk_throughput = chart(
    "Disk throughput",
    [
        (by_disk(rate("node_disk_read_bytes_total", DISKS)), "{{disk}} read"),
        (by_disk(rate("node_disk_written_bytes_total", DISKS)), "{{disk}} write"),
    ],
    unit="Bps",
)

# (height, panels) per line, each line splits the 24 columns evenly; charts are columns of CPU, memory, disk
LINES = [
    (4, [cpu, memory, cpu_temp, uptime]),
    (4, [zfs_pool, frigate_backup, next_backup, backup_failures]),
    (8, [cpu_by_mode, memory_usage, disk_used]),
    (8, [cpu_by_deployment, memory_by_deployment, disk_busy]),
    (8, [network, temperatures, disk_throughput]),
]

dashboard = {
    "uid": "homelab-server",
    "title": "Homelab server",
    "tags": ["homelab"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "30s",
    "time": {"from": "now-6h", "to": "now"},
    "editable": True,
    "templating": {"list": [{"name": "DS", "label": "Data source", "type": "datasource", "query": "prometheus", "current": {}, "hide": 2}]},
    "panels": layout(LINES),
}

if __name__ == "__main__":
    (Path(__file__).parent / "homelab-server.json").write_text(json.dumps(dashboard, indent=1))
