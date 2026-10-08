#!/usr/bin/env python3
"""Render one provider-neutral architecture spec as provider-specific diagrams.

For each target (generic, aws, azure, gcp) it writes:
  <out>/<target>.drawio   editable draw.io file using draw.io's built-in icon libraries
  <out>/<target>.png      preview image using icons from the Python 'diagrams' package
and also:
  <out>/multicloud.drawio  one draw.io file with a page per target
  <out>/service_mapping.md table of every component and the service used on each cloud
  <out>/render_report.md   what was rendered, plus every service name flagged "(v)" for verification

Both outputs share one Graphviz layout, so the PNG and the draw.io page match.

Usage:
  python render_multicloud.py SPEC.json --out OUTDIR [--targets generic,aws,azure,gcp] [--rankdir TB|LR] [--no-png]
  python render_multicloud.py --list-kinds          # show every component kind and the service it maps to

Requirements: Python 3.9+, `pip install diagrams` (for icon files), Graphviz `dot` on PATH.
See resources/05-multicloud-diagrams.md for the spec format.
"""
import argparse, html, json, os, shutil, subprocess, sys, tempfile, textwrap
from xml.sax.saxutils import escape as xesc

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_MAP = os.path.join(HERE, "..", "resources", "icon_map.json")
TARGETS = ["generic", "aws", "azure", "gcp"]
TARGET_NAMES = {"generic": "Provider-neutral", "aws": "Amazon Web Services", "azure": "Microsoft Azure", "gcp": "Google Cloud"}
PLACEMENTS = {"cloud", "onprem", "sovereign", "external"}
CONTAINER_TYPES = {"environment", "subsystem", "platform", "provider_zone", "onprem_site"}
FLOW_TYPES = {"request", "data", "telemetry"}

# Visual conventions (match resources/03-diagram-conventions.md)
DIO_CONTAINER = {
    "environment":  "rounded=0;whiteSpace=wrap;html=1;fillColor=#EEF2FC;strokeColor=#3F5FB8;strokeWidth=3;fontColor=#1F3A93;fontStyle=1;verticalAlign=top;align=center;fontSize=14;",
    "subsystem":    "rounded=1;arcSize=2;whiteSpace=wrap;html=1;fillColor=#EEEEEE;strokeColor=#BDBDBD;verticalAlign=top;align=left;spacingLeft=10;fontSize=14;fontStyle=1;",
    "platform":     "rounded=1;arcSize=2;whiteSpace=wrap;html=1;fillColor=#F7F7F7;strokeColor=#BDBDBD;verticalAlign=top;align=right;spacingRight=10;fontSize=13;fontStyle=1;",
    "provider_zone":"rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor=#DCE8FB;strokeColor=#8FB1E8;verticalAlign=top;align=center;fontSize=14;fontStyle=1;",
    "onprem_site":  "rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor=#FFF8E1;strokeColor=#E0C068;dashed=1;verticalAlign=top;align=center;fontSize=14;fontStyle=1;",
}
GV_CONTAINER = {
    "environment":  dict(style="filled,bold", fillcolor="#EEF2FC", color="#3F5FB8", penwidth="3", fontcolor="#1F3A93"),
    "subsystem":    dict(style="filled,rounded", fillcolor="#EEEEEE", color="#BDBDBD", labeljust="l"),
    "platform":     dict(style="filled,rounded", fillcolor="#F7F7F7", color="#BDBDBD", labeljust="r"),
    "provider_zone":dict(style="filled,rounded", fillcolor="#DCE8FB", color="#8FB1E8"),
    "onprem_site":  dict(style="filled,rounded,dashed", fillcolor="#FFF8E1", color="#E0C068"),
}
FLOW = {"request": ("#2E7D32", False), "data": ("#1F3A93", False), "telemetry": ("#2E7D32", True)}
ICON_PX = 48          # draw.io icon size (longest side)
ICON_GV = 56          # Graphviz icon cell size (points)
NODE_W_IN = 2.0      # Graphviz label width (inches)
WRAP = 26             # characters per label line


def die(msg):
    sys.exit(f"ERROR: {msg}")


def load_icon_map():
    with open(ICON_MAP) as f:
        return json.load(f)


def diagrams_resources():
    try:
        import diagrams
    except ImportError:
        return None
    return os.path.join(os.path.dirname(os.path.dirname(diagrams.__file__)), "resources")


# ---------------------------------------------------------------- spec validation
def validate(spec, kinds):
    errs = []
    cids = {}
    for c in spec.get("containers", []):
        if "id" not in c or "label" not in c or c.get("type") not in CONTAINER_TYPES:
            errs.append(f"container needs id, label and type in {sorted(CONTAINER_TYPES)}: {c}")
            continue
        if c["id"] in cids:
            errs.append(f"duplicate container id {c['id']}")
        cids[c["id"]] = c
    for c in cids.values():
        p = c.get("parent")
        if p and p not in cids:
            errs.append(f"container {c['id']} has unknown parent {p}")
    seen, depth_guard = {}, 0
    for c in cids.values():  # cycle check
        cur, hops = c, 0
        while cur.get("parent"):
            cur = cids.get(cur["parent"], {}); hops += 1
            if hops > 20:
                errs.append(f"container parent cycle at {c['id']}"); break
    nids = {}
    for n in spec.get("components", []):
        nid = n.get("id")
        if not nid or nid in nids or nid in cids:
            errs.append(f"component id missing or duplicated: {n}")
            continue
        if n.get("kind") not in kinds:
            errs.append(f"component {nid}: unknown kind {n.get('kind')!r}. Run --list-kinds.")
        if n.get("placement") not in PLACEMENTS:
            errs.append(f"component {nid}: placement must be one of {sorted(PLACEMENTS)}")
        if n.get("container") and n["container"] not in cids:
            errs.append(f"component {nid}: unknown container {n['container']}")
        if not n.get("label"):
            errs.append(f"component {nid}: label required")
        nids[nid] = n
    for e in spec.get("flows", []):
        if e.get("from") not in nids or e.get("to") not in nids:
            errs.append(f"flow {e.get('id')}: from/to must be component ids ({e.get('from')} -> {e.get('to')})")
        if e.get("type", "request") not in FLOW_TYPES:
            errs.append(f"flow {e.get('id')}: type must be one of {sorted(FLOW_TYPES)}")
        if e.get("crosses_boundary") and not e.get("data_class"):
            errs.append(f"flow {e.get('id')}: crosses_boundary=true needs data_class (what data crosses)")
    if errs:
        die("spec is invalid:\n  - " + "\n  - ".join(errs))
    return cids, nids


# ---------------------------------------------------------------- resolution
def resolve(n, target, kinds):
    """Return (icon_entry, service_text) for a component on a target."""
    k = kinds[n["kind"]]
    if n["placement"] == "cloud" and target != "generic":
        ent = k[target]
        svc = (n.get("service_override") or {}).get(target) or ent["service"]
    else:
        ent = k["generic"]
        if n["placement"] == "cloud":   # provider-neutral page: name the capability, not a vendor
            svc = n.get("tech") or f"Managed service: {k['description']}"
        else:
            svc = n.get("tech") or ent["service"]
    return ent, svc


def label_lines(n, svc):
    lines = textwrap.wrap(n["label"], WRAP) or [n["label"]]
    if n["placement"] == "external" and not n.get("tech"):
        return lines            # users and sources: the label says it all
    if svc and svc != n["label"]:
        lines += textwrap.wrap(svc, WRAP)
    return lines


def container_label(c, target):
    if c["type"] == "provider_zone" and target != "generic":
        return f"{TARGET_NAMES[target]}" + (f" — {c['zone_suffix']}" if c.get("zone_suffix") else "")
    return c["label"]


# ---------------------------------------------------------------- graphviz
def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_dot(spec, cids, nids, target, kinds, res_dir, rankdir):
    out = [f"digraph G {{", f"  graph [rankdir={rankdir}, compound=true, newrank=true, nodesep=0.5, ranksep=0.9, "
           f"fontname=Helvetica, fontsize=14, pad=0.4, label={q(spec.get('title', ''))}, labelloc=t, fontsize=18];",
           "  node [fontname=Helvetica, fontsize=11];", "  edge [fontname=Helvetica, fontsize=10];"]
    children = {}
    for c in cids.values():
        children.setdefault(c.get("parent"), []).append(c["id"])
    members = {}
    for n in nids.values():
        members.setdefault(n.get("container"), []).append(n["id"])

    def node_stmt(nid, ind):
        n = nids[nid]
        ent, svc = resolve(n, target, kinds)
        lines = label_lines(n, svc)
        icon = os.path.join(res_dir, ent["py_icon"]) if res_dir else None
        text = "<BR/>".join(html.escape(l, quote=False) for l in lines)
        img = (f'<TR><TD FIXEDSIZE="TRUE" WIDTH="{ICON_GV}" HEIGHT="{ICON_GV}"><IMG SRC="{html.escape(icon)}" SCALE="TRUE"/></TD></TR>'
               if icon and os.path.exists(icon) else "")
        lab = (f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="2" CELLPADDING="0">{img}'
               f'<TR><TD WIDTH="{int(NODE_W_IN * 72)}"><FONT POINT-SIZE="11">{text}</FONT></TD></TR></TABLE>>')
        return f"{ind}{q(nid)} [shape=plain, label={lab}];"

    def emit(cid, ind):
        c = cids[cid]
        st = GV_CONTAINER[c["type"]]
        out.append(f"{ind}subgraph {q('cluster_' + cid)} {{")
        out.append(f"{ind}  label={q(container_label(c, target))}; fontsize=13; margin=18;")
        for k, v in st.items():
            out.append(f"{ind}  {k}={q(v)};")
        for ch in children.get(cid, []):
            emit(ch, ind + "  ")
        for nid in members.get(cid, []):
            out.append(node_stmt(nid, ind + "  "))
        out.append(f"{ind}}}")

    for top in children.get(None, []):
        emit(top, "  ")
    for nid in members.get(None, []):
        out.append(node_stmt(nid, "  "))
    for e in spec.get("flows", []):
        col, dashed = FLOW[e.get("type", "request")]
        lbl = e.get("label", "")
        if e.get("crosses_boundary"):
            lbl = f"{lbl} [{e['data_class']}]" if lbl else f"[{e['data_class']}]"
        attrs = dict(color=col, fontcolor=col, penwidth="2", label=lbl)
        if dashed:
            attrs["style"] = "dashed"
        a = ", ".join(f"{k}={q(v)}" for k, v in attrs.items())
        out.append(f"  {q(e['from'])} -> {q(e['to'])} [{a}];")
    out.append("}")
    return "\n".join(out)


def run_dot(dot_src, fmt, out_path=None):
    if not shutil.which("dot"):
        die("Graphviz 'dot' not found on PATH. Install Graphviz (see README).")
    r = subprocess.run(["dot", f"-T{fmt}"] + (["-o", out_path] if out_path else []),
                       input=dot_src.encode(), capture_output=True)
    if r.returncode != 0:
        die("Graphviz failed:\n" + r.stderr.decode()[-2000:])
    return r.stdout


# ---------------------------------------------------------------- draw.io
def dio_attr(s):
    return xesc(s, {'"': "&quot;", "\n": "&#10;"})


def dio_label(lines):
    return "<br>".join(html.escape(l, quote=False) for l in lines)


def build_drawio_page(spec, cids, nids, target, kinds, layout, page_id):
    bb = [float(v) for v in layout["bb"].split(",")]
    H = bb[3]
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    objs = layout.get("objects", [])
    # containers: Graphviz subgraphs named cluster_<id>; draw outer first
    depth = {}
    for cid, c in cids.items():
        d, cur = 0, c
        while cur.get("parent"):
            cur = cids[cur["parent"]]; d += 1
        depth[cid] = d
    cl_bb = {o["name"][8:]: o["bb"] for o in objs if o.get("name", "").startswith("cluster_") and "bb" in o}
    for cid in sorted(cids, key=lambda i: depth[i]):
        if cid not in cl_bb:
            continue
        x0, y0, x1, y1 = (float(v) for v in cl_bb[cid].split(","))
        c = cids[cid]
        cells.append(f'<mxCell id="{dio_attr("c_" + cid)}" value="{dio_attr(html.escape(container_label(c, target), quote=False))}" '
                     f'style="{DIO_CONTAINER[c["type"]]}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x0:.0f}" y="{H - y1:.0f}" width="{x1 - x0:.0f}" height="{y1 - y0:.0f}" as="geometry"/></mxCell>')
    # components
    for o in objs:
        nid = o.get("name")
        if nid not in nids or "pos" not in o:
            continue
        n = nids[nid]
        ent, svc = resolve(n, target, kinds)
        cx, cy = (float(v) for v in o["pos"].split(","))
        nh = float(o["height"]) * 72
        w0, h0 = float(ent["w"] or ICON_PX), float(ent["h"] or ICON_PX)
        s = ICON_PX / max(w0, h0)
        iw, ih = w0 * s, h0 * s
        top = (H - cy) - nh / 2 + 2 + (ICON_GV - ih) / 2
        style = ent["drawio_style"].rstrip(";") + (";verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;"
                                                   "align=center;whiteSpace=nowrap;html=1;fontSize=11;fontColor=#1A1A1A;labelBackgroundColor=none;")
        cells.append(f'<mxCell id="{dio_attr(nid)}" value="{dio_attr(dio_label(label_lines(n, svc)))}" style="{dio_attr(style)}" '
                     f'vertex="1" parent="1"><mxGeometry x="{cx - iw / 2:.0f}" y="{top:.0f}" width="{iw:.0f}" height="{ih:.0f}" as="geometry"/></mxCell>')
    # flows: follow Graphviz's routed splines so connectors avoid icons and labels
    gvid = {o["_gvid"]: o.get("name") for o in objs}
    pool = {}
    for ge in sorted(layout.get("edges", []), key=lambda g: g["_gvid"]):
        pool.setdefault((gvid.get(ge["tail"]), gvid.get(ge["head"])), []).append(ge)
    for i, e in enumerate(spec.get("flows", [])):
        cand = pool.get((e["from"], e["to"])) or []
        ge = cand.pop(0) if cand else {}
        pts = []
        if "pos" in ge:
            toks = [t for t in ge["pos"].split() if not t.startswith(("e,", "s,"))]
            ctrl = [tuple(float(v) for v in t.split(",")) for t in toks]
            pts = [(x, H - y) for x, y in ctrl[1:-1]]
        lp = ge.get("lp")
        col, dashed = FLOW[e.get("type", "request")]
        lbl = e.get("label", "")
        if e.get("crosses_boundary"):
            lbl = f"{lbl} [{e['data_class']}]" if lbl else f"[{e['data_class']}]"
        st = (("edgeStyle=none;curved=1;" if pts else "edgeStyle=orthogonalEdgeStyle;rounded=1;") +
              f"html=1;endArrow=classic;strokeWidth=2;strokeColor={col};fontColor={col};fontSize=10;labelBackgroundColor=#FFFFFF;"
              + ("dashed=1;" if dashed else ""))
        eid = e.get("id") or f"e{i + 1}"
        geo = '<mxGeometry relative="1" as="geometry">'
        if pts:
            geo += "<Array as=\"points\">" + "".join(f'<mxPoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in pts) + "</Array>"
        geo += "</mxGeometry>"
        lbl_cell = ""
        if lbl and lp:   # place the label where Graphviz put it, as a separate text box
            lx, ly = (float(v) for v in lp.split(","))
            lbl_cell = (f'<mxCell id="{dio_attr("fl_" + eid)}" value="{dio_attr(html.escape(lbl, quote=False))}" '
                        f'style="text;html=1;align=center;verticalAlign=middle;fontSize=10;fontColor={col};labelBackgroundColor=#FFFFFF;" '
                        f'vertex="1" parent="1"><mxGeometry x="{lx - 80:.0f}" y="{H - ly - 10:.0f}" width="160" height="20" as="geometry"/></mxCell>')
            lbl = ""
        cells.append(f'<mxCell id="{dio_attr("f_" + eid)}" value="{dio_attr(html.escape(lbl, quote=False))}" style="{st}" edge="1" parent="1" '
                     f'source="{dio_attr(e["from"])}" target="{dio_attr(e["to"])}">{geo}</mxCell>' + lbl_cell)
    W = bb[2]
    name = TARGET_NAMES[target]
    return (f'<diagram id="{page_id}" name="{dio_attr(name)}"><mxGraphModel dx="{W:.0f}" dy="{H:.0f}" grid="1" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{max(1169, W + 40):.0f}" '
            f'pageHeight="{max(827, H + 40):.0f}" math="0" shadow="0"><root>' + "".join(cells) + "</root></mxGraphModel></diagram>")


def wrap_file(pages):
    return '<mxfile host="app.diagrams.net">' + "".join(pages) + "</mxfile>"


# ---------------------------------------------------------------- reports
def service_table(spec, nids, kinds, targets):
    hdr = ["Component", "Kind", "Placement"] + [TARGET_NAMES[t] for t in targets]
    rows = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    flags = set()
    for n in nids.values():
        cells = [n["label"], n["kind"], n["placement"]]
        for t in targets:
            _, svc = resolve(n, t, kinds)
            if "(v)" in svc:
                flags.add(svc)
            cells.append(svc)
        rows.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return "\n".join(rows) + "\n", sorted(flags)


def list_kinds(kinds):
    for k, v in kinds.items():
        print(f"{k:22} {v['description']}")
        for t in ["aws", "azure", "gcp", "generic"]:
            print(f"    {t:8} {v[t]['service']}")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--targets", default=",".join(TARGETS))
    ap.add_argument("--rankdir", default="TB", choices=["TB", "LR"])
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--list-kinds", action="store_true")
    a = ap.parse_args()
    im = load_icon_map()
    kinds = im["kinds"]
    if a.list_kinds:
        list_kinds(kinds); return
    if not a.spec or not a.out:
        ap.error("SPEC and --out are required (or use --list-kinds)")
    targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    for t in targets:
        if t not in TARGETS:
            die(f"unknown target {t}; choose from {TARGETS}")
    with open(a.spec) as f:
        spec = json.load(f)
    cids, nids = validate(spec, kinds)
    res = diagrams_resources()
    if res is None and not a.no_png:
        die("Python package 'diagrams' not installed (needed for PNG icons). Run: pip install diagrams  (or use --no-png)")
    os.makedirs(a.out, exist_ok=True)
    pages, done = [], []
    for i, t in enumerate(targets):
        dot_src = build_dot(spec, cids, nids, t, kinds, res, a.rankdir)
        with open(os.path.join(a.out, f"{t}.dot"), "w") as f:
            f.write(dot_src)
        layout = json.loads(run_dot(dot_src, "json"))
        page = build_drawio_page(spec, cids, nids, t, kinds, layout, f"p{i + 1}_{t}")
        pages.append(page)
        with open(os.path.join(a.out, f"{t}.drawio"), "w") as f:
            f.write(wrap_file([page]))
        if not a.no_png:
            run_dot(dot_src, "png", os.path.join(a.out, f"{t}.png"))
        done.append(t)
    with open(os.path.join(a.out, "multicloud.drawio"), "w") as f:
        f.write(wrap_file(pages))
    table, flags = service_table(spec, nids, kinds, targets)
    with open(os.path.join(a.out, "service_mapping.md"), "w") as f:
        f.write(f"# Service mapping — {spec.get('title', '')}\n\n" + table)
    meta = im["_meta"]
    rep = [f"# Render report — {spec.get('title', '')}", "",
           f"Targets rendered: {', '.join(TARGET_NAMES[t] for t in done)}",
           f"Icon map built {meta['built']} from draw.io commit {meta['drawio_commit'][:10]} and diagrams {meta['diagrams_version']}.", "",
           "## Service names to verify before submission", ""]
    rep += [f"- {s}" for s in flags] or ["- None flagged by the icon map. Still verify region availability for every cloud service."]
    rep += ["", "## Always verify", "",
            "- Availability of each managed service in the Malaysian region(s) proposed.",
            "- Provider icon usage terms if diagrams are published outside the proposal.",
            "- That the diagram matches the component and flow specification tables."]
    with open(os.path.join(a.out, "render_report.md"), "w") as f:
        f.write("\n".join(rep) + "\n")
    print(f"Rendered {', '.join(done)} -> {a.out}")
    print(f"Flagged service names: {len(flags)} (see render_report.md)")


if __name__ == "__main__":
    main()
