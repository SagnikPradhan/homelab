"""Regenerates homelab-server.json. Run: python3 generate.py, then prettier --write."""

import json
from pathlib import Path

from panels import bargauge, green, ok_until, place, red, stat, steps, table, timeseries

HOUR = 3600
RATE = "[$__rate_interval]"
POD = '{container!="",pod!=""}'
CPU_TEMP = 'node_hwmon_temp_celsius{chip="pci0000:00_0000:00:18_3"}'
NVME_TEMP = 'node_hwmon_temp_celsius{chip="nvme_nvme0"}'
DISKS = '{device=~"sda|nvme0n1"}'
IDLE = '{mode="idle"}'
NOT_IDLE = '{mode!="idle"}'
BACKUP_AGE = "time() - volsync_backup_last_sync_timestamp_seconds"


def used_pct(mount):
    sel = f'{{mountpoint="{mount}"}}'
    return f"100*(1-node_filesystem_avail_bytes{sel}/node_filesystem_size_bytes{sel})"


def per_sec(metric, selector=""):
    return f"rate({metric}{selector}{RATE})"


def top10(inner):
    return f"topk(10, sum by(namespace,pod)({inner}))"


CPU_BUSY = f"100 - avg({per_sec('node_cpu_seconds_total', IDLE)})*100"
MEM_USED = "100*(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)"
ONLINE = [{"type": "value", "options": {"1": {"text": "ONLINE", "color": "green"}, "0": {"text": "PROBLEM", "color": "red"}}}]

usage = ok_until(70, 90)
disk_full = ok_until(75, 90)
backup_age = ok_until(8 * HOUR, 24 * HOUR)

rows = [
    (
        None,
        [
            stat("Uptime", "time() - node_boot_time_seconds", unit="s", dec=1),
            stat("CPU used", CPU_BUSY, thr=usage, dec=0, lo=0, hi=100),
            stat("Memory used", MEM_USED, thr=usage, dec=0, lo=0, hi=100),
            stat("Load (1m)", "node_load1", unit="short", dec=2, thr=ok_until(8, 12)),
            stat("CPU temp", CPU_TEMP, unit="celsius", dec=0, thr=ok_until(70, 85)),
            stat("ZFS pool tank", 'node_zfs_zpool_state{zpool="tank",state="online"}', unit="none", mappings=ONLINE, thr=steps(red(None), green(1))),
        ],
    ),
    (
        None,
        [
            stat("NVMe /home used", used_pct("/home"), thr=disk_full, dec=0, lo=0, hi=100),
            stat("NVMe / used", used_pct("/"), thr=disk_full, dec=0, lo=0, hi=100),
            stat("NVMe /var used", used_pct("/var"), thr=disk_full, dec=0, lo=0, hi=100),
            stat("ZFS tank used", used_pct("/tank"), thr=disk_full, dec=0, lo=0, hi=100),
            stat("NVMe temp", NVME_TEMP, unit="celsius", dec=0, thr=ok_until(60, 75)),
            stat("Pods running", f"count(count by(namespace,pod)(container_memory_working_set_bytes{POD}))", unit="none", dec=0),
        ],
    ),
    (
        "Offsite backups (Hetzner Storage Box)",
        [
            stat("Oldest backup", "time() - min(volsync_backup_last_sync_timestamp_seconds)", unit="s", dec=1, thr=backup_age),
            stat("Frigate media backup", BACKUP_AGE + '{name="frigate-media"}', unit="s", dec=1, thr=ok_until(3 * HOUR, 12 * HOUR)),
            stat(
                "Volumes not successful",
                'count(volsync_backup_last_result{result!="Successful"}) or vector(0)',
                unit="none",
                dec=0,
                thr=steps(green(None), red(1)),
            ),
            stat("Next backup in", "min(volsync_backup_next_sync_timestamp_seconds) - time()", unit="s", dec=0),
        ],
    ),
    (
        None,
        [
            bargauge("Time since last backup, per volume", [(BACKUP_AGE, "{{namespace}}/{{name}}")], thr=backup_age, w=14),
            table("Result of last run", "volsync_backup_last_result", hide=("Time", "Value", "__name__", "job", "instance"), w=10),
        ],
    ),
    (
        "CPU and memory",
        [
            timeseries(
                "CPU by mode",
                [(f"avg by(mode)({per_sec('node_cpu_seconds_total', NOT_IDLE)})*100", "{{mode}}")],
                unit="percent",
                stack=True,
                lo=0,
                hi=100,
            ),
            timeseries(
                "Memory",
                [
                    ("node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes", "used (incl. ZFS cache)"),
                    ("node_zfs_arc_size", "of which ZFS ARC cache"),
                    ("node_memory_MemTotal_bytes", "total"),
                ],
                unit="bytes",
                lo=0,
            ),
        ],
    ),
    (
        "Network and disk",
        [
            timeseries(
                "Network enp3s0",
                [
                    (per_sec("node_network_receive_bytes_total", '{device="enp3s0"}') + "*8", "receive"),
                    (per_sec("node_network_transmit_bytes_total", '{device="enp3s0"}') + "*8", "transmit"),
                ],
                unit="bps",
                lo=0,
            ),
            timeseries(
                "Disk throughput",
                [
                    (per_sec("node_disk_read_bytes_total", DISKS), "{{device}} read"),
                    (per_sec("node_disk_written_bytes_total", DISKS), "{{device}} write"),
                ],
                unit="Bps",
                lo=0,
            ),
        ],
    ),
    (
        None,
        [
            timeseries(
                "Disk busy (sda = ZFS HDD, nvme0n1 = OS)",
                [(per_sec("node_disk_io_time_seconds_total", DISKS) + "*100", "{{device}}")],
                unit="percent",
                lo=0,
                hi=100,
            ),
            timeseries("Free space", [('node_filesystem_avail_bytes{mountpoint=~"/|/home|/var|/tank"}', "{{mountpoint}}")], unit="bytes", lo=0),
        ],
    ),
    (
        "ZFS",
        [
            timeseries("ARC size (read cache in RAM)", [("node_zfs_arc_size", "size"), ("node_zfs_arc_c_max", "limit")], unit="bytes", lo=0),
            timeseries("Temperatures", [(CPU_TEMP, "CPU"), (NVME_TEMP, "NVMe")], unit="celsius"),
        ],
    ),
    (
        "Kubernetes pods",
        [
            timeseries("Memory by pod (top 10)", [(top10(f"container_memory_working_set_bytes{POD}"), "{{namespace}}/{{pod}}")], unit="bytes", lo=0),
            timeseries("CPU by pod (top 10)", [(top10(per_sec("container_cpu_usage_seconds_total", POD)), "{{namespace}}/{{pod}}")], lo=0),
        ],
    ),
]

DATASOURCE_VAR = {"name": "DS", "label": "Data source", "type": "datasource", "query": "prometheus", "current": {}, "hide": 2}
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
    "templating": {"list": [DATASOURCE_VAR]},
    "panels": place(rows),
}

if __name__ == "__main__":
    (Path(__file__).parent / "homelab-server.json").write_text(json.dumps(dashboard, indent=1))
