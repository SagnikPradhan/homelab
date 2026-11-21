"""Grafana building blocks: thresholds, stat and time series panels, and the grid layout."""

from itertools import count

DS = {"type": "prometheus", "uid": "${DS}"}
LAST = {"calcs": ["lastNotNull"], "fields": "", "values": False}
COLUMNS = 24


def steps(*pairs):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}


def ok_until(warn, bad):
    return steps(("green", None), ("yellow", warn), ("red", bad))


def panel(kind, title, series, defaults, options):
    refs = [{"datasource": DS, "refId": r, "expr": e, **({"legendFormat": s} if s else {})} for r, (e, s) in zip("ABCDEFGH", series)]
    return {
        "type": kind,
        "title": title,
        "datasource": DS,
        "targets": refs,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": options,
    }


def stat(title, expr, unit="percent", thr=None, dec=0, lo=None, hi=None, mappings=()):
    limits = {k: v for k, v in (("min", lo), ("max", hi)) if v is not None}
    defaults = {"unit": unit, "decimals": dec, "thresholds": thr or steps(("green", None)), "mappings": list(mappings), **limits}
    options = {"colorMode": "value", "graphMode": "area", "reduceOptions": LAST, "textMode": "auto"}
    return panel("stat", title, [(expr, None)], defaults, options)


def chart(title, series, unit="short", stack=False, hi=None):
    custom = {"fillOpacity": 15, "lineWidth": 1, "showPoints": "never", "spanNulls": True}
    custom |= {"stacking": {"mode": "normal", "group": "A"}} if stack else {}
    defaults = {"unit": unit, "custom": custom, "min": 0, **({"max": hi} if hi else {})}
    options = {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}}
    return panel("timeseries", title, series, defaults, options)


def layout(lines):
    """[(height, [panel])] -> panels with ids and grid positions, each line splitting the columns evenly."""
    ids, y, out = count(1), 0, []
    for height, panels in lines:
        width = COLUMNS // len(panels)
        out += [{**p, "id": next(ids), "gridPos": {"x": i * width, "y": y, "w": width, "h": height}} for i, p in enumerate(panels)]
        y += height
    return out
