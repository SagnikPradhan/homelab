"""Building blocks for Grafana panels. Everything here is a pure function returning plain data."""

from itertools import accumulate, count
from typing import NamedTuple

DS = {"type": "prometheus", "uid": "${DS}"}
WIDTH = 24  # Grafana grid columns


def color(name):
    return lambda value: {"color": name, "value": value}


green, yellow, red = map(color, ("green", "yellow", "red"))


def steps(*xs):
    return {"mode": "absolute", "steps": list(xs) or [green(None)]}


def ok_until(warn, bad):
    return steps(green(None), yellow(warn), red(bad))


def targets(*series, **extra):
    """(expr, legend) pairs -> Grafana targets with refIds A, B, C, ..."""
    refs = "ABCDEFGH"
    return [{"datasource": DS, "refId": r, "expr": e, **({"legendFormat": l} if l else {}), **extra} for r, (e, l) in zip(refs, series)]


def bounds(lo, hi):
    return {k: v for k, v in (("min", lo), ("max", hi)) if v is not None}


class Piece(NamedTuple):
    h: int
    body: dict
    w: int | None = None


READ_LAST = {"calcs": ["lastNotNull"], "fields": "", "values": False}


def panel(kind, title, series, defaults, options, **extra):
    field_config = {"defaults": defaults, "overrides": []}
    return {"type": kind, "title": title, "targets": targets(*series), "fieldConfig": field_config, "options": options, **extra}


def stat(title, expr, unit="percent", thr=None, dec=None, lo=None, hi=None, mappings=(), w=None):
    decimals = {"decimals": dec} if dec is not None else {}
    defaults = {"unit": unit, "thresholds": thr or steps(), "mappings": list(mappings), **bounds(lo, hi), **decimals}
    options = {"colorMode": "value", "graphMode": "area", "reduceOptions": READ_LAST, "textMode": "auto"}
    return Piece(4, panel("stat", title, [(expr, None)], defaults, options), w)


def timeseries(title, series, unit="short", stack=False, lo=None, hi=None, w=None):
    line = {"fillOpacity": 15, "lineWidth": 1, "showPoints": "never", "spanNulls": True}
    custom = {**line, **({"stacking": {"mode": "normal", "group": "A"}} if stack else {})}
    options = {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}}
    return Piece(8, panel("timeseries", title, series, {"unit": unit, "custom": custom, **bounds(lo, hi)}, options), w)


def bargauge(title, series, unit="s", thr=None, w=None):
    options = {"orientation": "horizontal", "displayMode": "gradient", "reduceOptions": READ_LAST, "showUnfilled": True}
    return Piece(6, panel("bargauge", title, series, {"unit": unit, "min": 0, "thresholds": thr or steps()}, options), w)


def table(title, expr, hide=(), w=None):
    organize = {"id": "organize", "options": {"excludeByName": dict.fromkeys(hide, True)}}
    body = panel("table", title, [(expr, None)], {}, {"showHeader": True}, transformations=[organize])
    return Piece(6, {**body, "targets": targets((expr, None), instant=True, format="table")}, w)


def share_width(requested):
    """Pieces without a width split what the others leave over."""
    left = WIDTH - sum(w or 0 for w in requested)
    unset = requested.count(None)
    return [w if w else left // unset for w in requested]


def place(rows):
    """[(title or None, [Piece])] -> flat list of panels with ids and grid positions."""
    ids, y, out = count(1), 0, []
    for title, pieces in rows:
        if title:
            header = {"id": next(ids), "type": "row", "title": title, "collapsed": False, "panels": []}
            out.append({**header, "gridPos": {"x": 0, "y": y, "w": WIDTH, "h": 1}})
            y += 1
        widths = share_width([p.w for p in pieces])
        xs = [0, *accumulate(widths)]
        out += [{**p.body, "id": next(ids), "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": p.h}} for p, x, w in zip(pieces, xs, widths)]
        y += max(p.h for p in pieces)
    return out
