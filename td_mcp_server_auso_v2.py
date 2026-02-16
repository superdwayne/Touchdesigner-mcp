"""
TouchDesigner MCP Server - AUSO v2.0.0 (Auto-connect + Smart Layout)
Provides HTTP endpoints for Claude to interact with TouchDesigner.

Highlights:
- Robust auto-connect on create (same-family sibling or explicit connect_source)
- Smart auto-positioning (by family rows, spaced grid, source-aligned)
- Viewer open helper (show_preview)
- Optional layout tool to reflow an existing network
 - Extensive natural-name aliases for TD operators (e.g., 'webcam' -> Video Device In)
 - Generic natural command: method "create <label>" (auto family hint)

Default port: 8053 (set TD_MCP_PORT to override)
"""

import os
import sys
import json
import threading
import time
import uuid
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# --- TouchDesigner Environment Detection and Type Imports ---
try:
    import td  # type: ignore
    TDF = True
except Exception:
    TDF = False

# Remember this module key so we can dispatch even if the DAT is renamed/deleted
MODULE_KEY = __name__

PROTECTED_PATHS = set()
SERVER_DAT_PATH = None

# --- Result Feedback Mechanism ---
# Allows HTTP thread to wait for results from TD main thread run() calls
_pending_results = {}  # req_id -> {'event': Event, 'result': None, 'error': None}

def _store_result(req_id, result=None, error=None):
    """Called from TD main thread inside run() to deliver results back to HTTP thread."""
    entry = _pending_results.get(req_id)
    if entry:
        entry['result'] = result
        entry['error'] = error
        entry['event'].set()

def _wait_for_result(req_id, timeout=5.0):
    """Called from HTTP thread to block until TD main thread delivers results."""
    entry = _pending_results.get(req_id)
    if not entry:
        return {'error': 'No pending request found'}
    entry['event'].wait(timeout=timeout)
    result = entry.get('result')
    error = entry.get('error')
    # Clean up
    _pending_results.pop(req_id, None)
    if error:
        return {'error': error}
    if result is not None:
        return result
    return {'error': 'Timeout waiting for TouchDesigner response'}

# --- Connection History ---
connection_history = deque(maxlen=100)

def _normalize_path(path):
    """Return a TouchDesigner op path without trailing slashes (except root)."""
    if not isinstance(path, str):
        return ''
    norm = path.strip()
    if not norm:
        return ''
    if norm != '/' and not norm.startswith('/'):
        norm = '/' + norm
    if norm != '/' and norm.endswith('/'):
        norm = norm.rstrip('/')
    return norm

def _register_protected_path(path):
    norm = _normalize_path(path)
    if norm:
        PROTECTED_PATHS.add(norm)

def _is_protected_path(path):
    norm = _normalize_path(path)
    if not norm:
        return False
    for protected in PROTECTED_PATHS:
        if norm == protected:
            return True
        if protected.startswith(norm + '/'):
            return True
    return False

def _safe_td_type(module, name):
    try:
        return getattr(module, name)
    except Exception:
        return None

if TDF:
    # Common TD operator classes (best-effort; available names may vary by build)
    textDAT = _safe_td_type(td, 'textDAT'); tableDAT = _safe_td_type(td, 'tableDAT'); scriptDAT = _safe_td_type(td, 'scriptDAT')
    opfindDAT = _safe_td_type(td, 'opfindDAT'); executeDAT = _safe_td_type(td, 'executeDAT')

    circleTOP = _safe_td_type(td, 'circleTOP'); noiseTOP = _safe_td_type(td, 'noiseTOP'); moviefileinTOP = _safe_td_type(td, 'moviefileinTOP')
    constantTOP = _safe_td_type(td, 'constantTOP'); rampTOP = _safe_td_type(td, 'rampTOP'); textTOP = _safe_td_type(td, 'textTOP')
    outTOP = _safe_td_type(td, 'outTOP'); renderTOP = _safe_td_type(td, 'renderTOP'); blurTOP = _safe_td_type(td, 'blurTOP')
    nullTOP = _safe_td_type(td, 'nullTOP'); compositeTOP = _safe_td_type(td, 'compositeTOP'); levelTOP = _safe_td_type(td, 'levelTOP')

    constantCHOP = _safe_td_type(td, 'constantCHOP'); noiseCHOP = _safe_td_type(td, 'noiseCHOP'); lfoCHOP = _safe_td_type(td, 'lfoCHOP')
    mathCHOP = _safe_td_type(td, 'mathCHOP'); selectCHOP = _safe_td_type(td, 'selectCHOP'); outCHOP = _safe_td_type(td, 'outCHOP')
    nullCHOP = _safe_td_type(td, 'nullCHOP')
    audiodeviceinCHOP = _safe_td_type(td, 'audiodeviceinCHOP') or _safe_td_type(td, 'audioDeviceInCHOP')

    sphereSOP = _safe_td_type(td, 'sphereSOP'); boxSOP = _safe_td_type(td, 'boxSOP'); gridSOP = _safe_td_type(td, 'gridSOP')
    lineSOP = _safe_td_type(td, 'lineSOP'); nullSOP = _safe_td_type(td, 'nullSOP'); outSOP = _safe_td_type(td, 'outSOP')
    torusSOP = _safe_td_type(td, 'torusSOP'); transformSOP = _safe_td_type(td, 'transformSOP'); mergeSOP = _safe_td_type(td, 'mergeSOP')

    baseCOMP = _safe_td_type(td, 'baseCOMP'); containerCOMP = _safe_td_type(td, 'containerCOMP'); geometryCOMP = _safe_td_type(td, 'geometryCOMP')
    cameraCOMP = _safe_td_type(td, 'cameraCOMP'); lightCOMP = _safe_td_type(td, 'lightCOMP'); windowCOMP = _safe_td_type(td, 'windowCOMP')

    phongMAT = _safe_td_type(td, 'phongMAT'); pbrMAT = _safe_td_type(td, 'pbrMAT'); constantMAT = _safe_td_type(td, 'constantMAT')

    project = _safe_td_type(sys.modules.get('__main__', {}), 'project') or _safe_td_type(td, 'project')

else:
    # Mock environment for development outside TD
    class MockOp:
        def __init__(self, path):
            self.path = path; self.name = path.strip('/').split('/')[-1] or 'root'
            self.type = 'mockType'; self.valid = True; self.children = []
            self.nodeX = 0; self.nodeY = 0; self.inputs = []; self.outputs = []
        def parent(self): return MockOp('/')
        def create(self, t, name=None): return MockOp(self.path.rstrip('/') + '/' + (name or 'op'))
        def destroy(self): pass
        @property
        def par(self):
            class P:
                def __getattr__(self, _):
                    class V:
                        val = ''
                        def eval(self): return self.val
                    return V()
            return P()

    class MockTd: OP = MockOp
    td = MockTd()
    def op(path): return MockOp(path)
    def run(cmd, delayFrames=0): print('Mock run:', cmd)
    project = type('P', (), {'name': 'mock'})


# --- Utility helpers ---
def _norm_name(s: str) -> str:
    s = (s or "").lower().replace(" ", "").replace("-", "").replace("_", "")
    # strip common family suffixes if present
    for suf in ["top", "chop", "sop", "dat", "comp", "mat"]:
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s

OP_TYPES_BY_FAMILY = {
    'TOP': {}, 'CHOP': {}, 'SOP': {}, 'DAT': {}, 'COMP': {}, 'MAT': {}
}
OP_TYPES_NORMALIZED = {}  # base token -> list of (family, class, typename)

def _collect_td_op_types():
    if not TDF:
        return
    try:
        for attr in dir(td):
            try:
                cls = getattr(td, attr)
                # Only include OP subclasses
                if isinstance(cls, type) and hasattr(td, 'OP') and issubclass(cls, td.OP):
                    name = str(attr)
                    fam = None
                    for suf, fam_name in [("TOP","TOP"),("CHOP","CHOP"),("SOP","SOP"),("DAT","DAT"),("COMP","COMP"),("MAT","MAT")]:
                        if name.endswith(suf):
                            fam = fam_name
                            break
                    if not fam:
                        continue
                    OP_TYPES_BY_FAMILY[fam][name] = cls
                    base = _norm_name(name)
                    OP_TYPES_NORMALIZED.setdefault(base, []).append((fam, cls, name))
            except Exception:
                continue
    except Exception:
        pass

_collect_td_op_types()

SYNONYM_MAP = {
    # General, common names to canonical base tokens (no family suffix)
    # COMP
    'geo': 'geometry', 'geom': 'geometry', 'geocomp': 'geometry', 'panel': 'container', 'ui': 'container',
    'cam': 'camera',

    # TOP (sources, image/video processing)
    'webcam': 'videodevicein', 'video in': 'videodevicein', 'video_in': 'videodevicein', 'videoin': 'videodevicein',
    'caminput': 'videodevicein', 'camera in': 'videodevicein',
    'movie': 'moviefilein', 'movie in': 'moviefilein', 'movie_in': 'moviefilein', 'video': 'moviefilein', 'video file': 'moviefilein',
    'videofile': 'moviefilein', 'image': 'moviefilein', 'picture': 'moviefilein', 'pic': 'moviefilein', 'img': 'moviefilein',
    'movie out': 'moviefileout', 'video out': 'moviefileout', 'record': 'moviefileout', 'capture': 'moviefileout',
    'text top': 'texttop', 'txttop': 'texttop',
    'null top': 'nulltop', 'out top': 'out', 'transform top': 'transform', 'scale': 'transform', 'crop': 'crop',
    'blur': 'blur', 'switch': 'switch', 'feedback': 'feedback', 'level': 'level',
    'rectangle': 'rectangle',
    # Common creative effects
    'pixelate': 'pixellate', 'pixellate': 'pixellate', 'mosaic': 'pixellate',
    'kaleid': 'kaleidoscope', 'kaleidoscope': 'kaleidoscope',
    'invert top': 'invert', 'invert': 'invert',

    # CHOP (time-based/CHannel OPerators)
    'mic': 'audiodevicein', 'microphone': 'audiodevicein', 'audio in': 'audiodevicein', 'audio_in': 'audiodevicein',
    'timer': 'timer', 'count': 'count', 'filter': 'filter', 'lag': 'lag', 'speed': 'speed', 'logic': 'logic',
    'slope': 'slope', 'shuffle': 'shuffle', 'trigger': 'trigger', 'hold': 'hold',
    'keyboard': 'keyboardin', 'keyboard in': 'keyboardin', 'mouse': 'mousein', 'mouse in': 'mousein',
    'midi': 'midiin', 'midi in': 'midiin', 'osc': 'oscin', 'osc in': 'oscin',
    'null chop': 'nullchop', 'out chop': 'outchop',

    # DAT (tables, scripting, protocols)
    'text dat': 'text', 'txt': 'text', 'table dat': 'table', 'script dat': 'script', 'execute dat': 'execute',
    'http': 'webclient', 'web': 'webclient', 'fetch': 'webclient', 'json': 'json', 'xml': 'xml',
    'tcpip': 'tcpip', 'udp': 'udp', 'serial': 'serial',

    # SOP (geometry)
    'xform': 'transform', 'metaball': 'metaball', 'tube': 'tube', 'copyto': 'copy', 'copy to': 'copy',
    'force': 'force', 'add': 'add', 'boolean': 'boolean', 'poly extrude': 'polyextrude', 'polyextrude': 'polyextrude',
    'subdivide': 'subdivide', 'twist': 'twist', 'facet': 'facet', 'carve': 'carve',

    # MAT (materials)
    'material': 'phong', 'phongmat': 'phong', 'principled': 'pbr',

    # Explicit family-suffixed helpful shorthands
    'null sop': 'nullsop', 'nullsop': 'nullsop',
}

# Default family hints for ambiguous base tokens when the caller didn't provide one.
DEFAULT_FAMILY_HINTS = {
    # Strong TOP defaults
    'videodevicein': 'TOP', 'moviefilein': 'TOP', 'moviefileout': 'TOP', 'texttop': 'TOP', 'out': 'TOP',
    'null': 'TOP', 'nulltop': 'TOP', 'switch': 'TOP', 'feedback': 'TOP', 'level': 'TOP', 'composite': 'TOP',
    'transform': 'TOP', 'crop': 'TOP', 'blur': 'TOP', 'rectangle': 'TOP', 'circle': 'TOP', 'ramp': 'TOP', 'noise': 'TOP',
    'render': 'TOP', 'displace': 'TOP', 'lookup': 'TOP', 'pixellate': 'TOP', 'kaleidoscope': 'TOP', 'invert': 'TOP',

    # CHOP defaults
    'audiodevicein': 'CHOP', 'constant': 'CHOP', 'math': 'CHOP', 'select': 'CHOP', 'lfo': 'CHOP', 'nullchop': 'CHOP',
    'outchop': 'CHOP', 'timer': 'CHOP', 'count': 'CHOP', 'filter': 'CHOP', 'lag': 'CHOP', 'speed': 'CHOP', 'logic': 'CHOP',
    'keyboardin': 'CHOP', 'mousein': 'CHOP', 'midiin': 'CHOP', 'oscin': 'CHOP',

    # SOP defaults
    'box': 'SOP', 'grid': 'SOP', 'sphere': 'SOP', 'torus': 'SOP', 'tube': 'SOP', 'metaball': 'SOP', 'merge': 'SOP',
    'transformsop': 'SOP', 'nullsop': 'SOP', 'outsop': 'SOP', 'polyextrude': 'SOP', 'boolean': 'SOP',

    # COMP defaults
    'geometry': 'COMP', 'camera': 'COMP', 'light': 'COMP', 'container': 'COMP', 'base': 'COMP', 'window': 'COMP',

    # DAT defaults
    'text': 'DAT', 'table': 'DAT', 'script': 'DAT', 'execute': 'DAT', 'opfind': 'DAT', 'json': 'DAT', 'webclient': 'DAT',
    'tcpip': 'DAT', 'udp': 'DAT', 'serial': 'DAT',

    # MAT defaults
    'phong': 'MAT', 'pbr': 'MAT', 'constantmat': 'MAT',
}

# Prefer likely interactive families first for natural names
FAMILY_ORDER = ['TOP','CHOP','SOP','COMP','MAT','DAT']

def _resolve_type(label: str, family_hint: str = None):
    """Resolve a human label to a TD OP class using introspection.
    family_hint can be one of TOP/CHOP/SOP/DAT/COMP/MAT (case-insensitive) or short forms.
    """
    if not TDF:
        return None
    if not label:
        return None
    fam_hint = None
    if family_hint:
        fh = family_hint.strip().upper()
        # normalize hints like 'top','Top','sop'
        if fh.endswith('S'):  # allow plurals like 'SOPs'
            fh = fh[:-1]
        if fh in OP_TYPES_BY_FAMILY:
            fam_hint = fh
        else:
            for k in OP_TYPES_BY_FAMILY.keys():
                if k.lower().startswith(fh.lower()):
                    fam_hint = k
                    break

    base = _norm_name(SYNONYM_MAP.get(label.lower(), label))

    # If explicitly includes family in the string (e.g., transformSOP), try direct
    direct = getattr(td, label, None)
    if isinstance(direct, type) and hasattr(td, 'OP') and issubclass(direct, td.OP):
        return direct

    candidates = OP_TYPES_NORMALIZED.get(base, [])

    # Check DEFAULT_FAMILY_HINTS before fuzzy scan (after synonym lookup)
    if not fam_hint:
        fam_hint = DEFAULT_FAMILY_HINTS.get(base)

    # Exact base token match with family preference
    if fam_hint:
        for fam, cls, _name in candidates:
            if fam == fam_hint:
                return cls
    # If there's exactly one candidate, use it
    if len(candidates) == 1:
        return candidates[0][1]
    # If multiple candidates but no family hint, prefer by family order
    if candidates and not fam_hint:
        for fam in FAMILY_ORDER:
            for f, cls, _name in candidates:
                if f == fam:
                    return cls

    # Try fuzzy contains across all types if no base match
    try:
        lower = base
        best = None
        for fam in FAMILY_ORDER:
            for name, cls in OP_TYPES_BY_FAMILY[fam].items():
                if lower in name.lower():
                    # When fam_hint is set, require exact family match
                    if fam_hint is not None:
                        if fam == fam_hint:
                            return cls
                        # Don't set best if wrong family
                    else:
                        return cls
        return best
    except Exception:
        return None
def _get_op_family(op_obj):
    try:
        fam = getattr(op_obj, 'family', None)
        if fam:
            return str(fam).upper()
    except Exception:
        pass
    try:
        t = str(getattr(op_obj, 'type', '')).lower()
        for token, fam in [('top', 'TOP'), ('chop', 'CHOP'), ('sop', 'SOP'), ('dat', 'DAT'), ('comp', 'COMP'), ('mat', 'MAT')]:
            if token in t:
                return fam
    except Exception:
        pass
    return None

def _connect_input(target_op, index, source_op):
    try:
        if hasattr(target_op, 'setInput'):
            try:
                target_op.setInput(index, source_op)
                return True
            except Exception:
                pass
        if hasattr(target_op, 'inputConnectors'):
            conns = getattr(target_op, 'inputConnectors')
            if conns and len(conns) > index and hasattr(conns[index], 'connect'):
                try:
                    conns[index].connect(source_op)
                    return True
                except Exception:
                    pass
        if hasattr(target_op, 'inputs'):
            try:
                if len(getattr(target_op, 'inputs', [])) > index:
                    target_op.inputs[index] = source_op
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _list_siblings(parent_op, family):
    sibs = []
    try:
        for c in getattr(parent_op, 'children', []) or []:
            if c and getattr(c, 'valid', False) and _get_op_family(c) == family:
                sibs.append(c)
    except Exception:
        pass
    return sibs

def _create_fallback_top(parent_op, base_name='mcp_const'):
    try:
        # Create a Constant TOP as a safe fallback source
        name = base_name
        i = 1
        while op(f"{getattr(parent_op, 'path', '/')}/{name}{i}"):
            i += 1
        name = f"{name}{i}"
        const_cls = constantTOP or getattr(td, 'constantTOP', None)
        if not const_cls:
            return None
        node = parent_op.create(const_cls, name)
        return node if node and getattr(node, 'valid', False) else None
    except Exception:
        return None

def _ensure_composite_inputs(new_op, parent_op, prefer_paths=None):
    """Ensure a Composite TOP has at least 2 inputs. Prefer specific sources when provided.
    prefer_paths: list of op paths to prioritize when wiring.
    """
    try:
        t = str(getattr(new_op, 'type', '')).lower()
        if 'top' not in t or 'composite' not in t:
            return
        need = 2
        current = []
        try:
            for i in range(need):
                cur = None
                if hasattr(new_op, 'inputs'):
                    ins = getattr(new_op, 'inputs', []) or []
                    if len(ins) > i:
                        cur = ins[i]
                current.append(cur)
        except Exception:
            pass
        if sum(1 for c in current if c) >= need:
            return

        # Build candidate list: preferred paths, then TOP siblings (ordered by nodeX)
        cands = []
        seen = set()
        for pth in (prefer_paths or []):
            try:
                cand = op(pth) if isinstance(pth, str) else None
                if cand and getattr(cand, 'valid', False) and cand is not new_op:
                    if getattr(cand, 'path', None) not in seen:
                        cands.append(cand); seen.add(getattr(cand, 'path', None))
            except Exception:
                continue
        sibs = _list_siblings(parent_op, 'TOP')
        try:
            sibs.sort(key=lambda s: getattr(s, 'nodeX', 0))
        except Exception:
            pass
        for s in sibs[::-1]:  # from rightmost
            if s is new_op:
                continue
            p = getattr(s, 'path', None)
            if p and p not in seen:
                cands.append(s); seen.add(p)

        # Fill inputs 0 and 1
        for i in range(need):
            try:
                # Skip if already connected
                connected = False
                if hasattr(new_op, 'inputs'):
                    ins = getattr(new_op, 'inputs', []) or []
                    if len(ins) > i and ins[i]:
                        connected = True
                if connected:
                    continue
                src = None
                if cands:
                    src = cands.pop(0)
                else:
                    src = _create_fallback_top(parent_op)
                if src and getattr(src, 'valid', False):
                    _connect_input(new_op, i, src)
            except Exception:
                continue
    except Exception:
        pass

def _ensure_two_input_top(new_op, parent_op, prefer_paths=None):
    """Ensure two inputs for common 2-input TOPs (composite, displace, lookup)."""
    try:
        t = str(getattr(new_op, 'type', '')).lower()
        if 'top' not in t:
            return
        if not any(k in t for k in ['composite', 'displace', 'lookup']):
            return
        # Reuse composite ensure logic (works generically for 2 inputs)
        _ensure_composite_inputs(new_op, parent_op, prefer_paths)
    except Exception:
        pass


def _unique_child_name(parent_op, base):
    try:
        i = 1
        while op(f"{getattr(parent_op, 'path', '/')}/{base}{i}"):
            i += 1
        return f"{base}{i}"
    except Exception:
        return base

def _create_fallback_source(parent_op, family, type_label, input_index=0):
    """Create a sensible fallback source for a given family/type.
    Returns the created op or None.
    """
    t = (type_label or '').lower()
    try:
        if family == 'TOP':
            # Prefer type-specific helpful sources
            if 'displace' in t and input_index == 1:
                cls = noiseTOP or getattr(td, 'noiseTOP', None)
                name = _unique_child_name(parent_op, 'mcp_noise')
            elif 'lookup' in t and input_index == 1:
                cls = rampTOP or getattr(td, 'rampTOP', None)
                name = _unique_child_name(parent_op, 'mcp_ramp')
            else:
                cls = constantTOP or getattr(td, 'constantTOP', None)
                name = _unique_child_name(parent_op, 'mcp_const')
            if cls:
                return parent_op.create(cls, name)
        elif family == 'SOP':
            # Provide simple geometry
            if 'boolean' in t and input_index == 1:
                cls = sphereSOP or getattr(td, 'sphereSOP', None)
                name = _unique_child_name(parent_op, 'mcp_sphere')
            else:
                cls = boxSOP or getattr(td, 'boxSOP', None)
                name = _unique_child_name(parent_op, 'mcp_box')
            if cls:
                return parent_op.create(cls, name)
        elif family == 'CHOP':
            cls = constantCHOP or getattr(td, 'constantCHOP', None)
            name = _unique_child_name(parent_op, 'mcp_const')
            if cls:
                return parent_op.create(cls, name)
    except Exception:
        return None
    return None

def _ensure_min_inputs_op(op_obj, parent_op, prefer_paths=None):
    """Ensure reasonable minimum inputs for common nodes across families.
    - TOP: composite/displace/lookup -> 2; blur/level/feedback/transform/crop -> 1
    - SOP: transform/polyextrude/twist/subdivide/facet/carve -> 1; boolean -> 2
    - CHOP: filter/lag/math/speed/logic -> 1
    Creates fallback sources when missing.
    """
    try:
        t = str(getattr(op_obj, 'type', '')).lower()
        family = _get_op_family(op_obj) or (
            'TOP' if 'top' in t else 'SOP' if 'sop' in t else 'CHOP' if 'chop' in t else None
        )
        if not family:
            return

        # Determine required inputs
        required = 0
        if family == 'TOP':
            if any(k in t for k in ['composite', 'displace', 'lookup']):
                required = 2
            elif any(k in t for k in ['blur', 'level', 'feedback', 'transform', 'crop', 'switch']):
                required = 1
        elif family == 'SOP':
            if 'boolean' in t:
                required = 2
            elif any(k in t for k in ['transform', 'polyextrude', 'twist', 'subdivide', 'facet', 'carve']):
                required = 1
        elif family == 'CHOP':
            if any(k in t for k in ['filter', 'lag', 'math', 'speed', 'logic']):
                required = 1

        if required <= 0:
            return

        # Existing connections
        existing = []
        try:
            for i in range(required):
                cur = None
                ins = getattr(op_obj, 'inputs', []) or []
                if len(ins) > i:
                    cur = ins[i]
                existing.append(cur)
        except Exception:
            pass
        have = sum(1 for e in existing if e)
        if have >= required:
            return

        # Build preferred candidates list
        candidates = []
        seen = set()
        for pth in (prefer_paths or []):
            try:
                cand = op(pth) if isinstance(pth, str) else None
                if cand and getattr(cand, 'valid', False) and cand is not op_obj:
                    p = getattr(cand, 'path', None)
                    if p and p not in seen:
                        candidates.append(cand); seen.add(p)
            except Exception:
                continue
        # Family siblings as next choices
        sibs = _list_siblings(parent_op, family)
        try:
            sibs.sort(key=lambda s: getattr(s, 'nodeX', 0))
        except Exception:
            pass
        for s in sibs[::-1]:
            if s is op_obj:
                continue
            p = getattr(s, 'path', None)
            if p and p not in seen:
                candidates.append(s); seen.add(p)

        # Fill missing inputs
        for i in range(required):
            try:
                ins = getattr(op_obj, 'inputs', []) or []
                if len(ins) > i and ins[i]:
                    continue
                src = candidates.pop(0) if candidates else _create_fallback_source(parent_op, family, t, i)
                if src and getattr(src, 'valid', False):
                    _connect_input(op_obj, i, src)
            except Exception:
                continue
    except Exception:
        pass


# --- run() payloads executed on TD main thread ---
def _run_create(params_json, req_id=None):
    try:
        params = json.loads(params_json)
        comp_type_str = params.get('type'); name = params.get('name')
        parent_path = params.get('parent', '/')
        properties = params.get('properties', {})
        connect_source = params.get('connect_source'); connect_parameter = params.get('connect_parameter')
        auto_connect = params.get('auto_connect', True)
        open_preview = params.get('open_preview', False)
        family_hint = params.get('family')  # Optional: 'SOP','TOP','CHOP','DAT','COMP','MAT'

        if not comp_type_str:
            raise ValueError('Missing type')

        # Validate parent is a COMP-like type (has create method)
        parent_op = op(parent_path)
        if not parent_op or not getattr(parent_op, 'valid', False):
            raise ValueError(f'Invalid parent: {parent_path}')
        if not hasattr(parent_op, 'create'):
            raise ValueError(f'Parent {parent_path} is not a container (cannot create children)')

        # Type map with common synonyms (fast path), dynamic resolver as primary
        comp_type_map = {
            # DAT
            'text': textDAT, 'table': tableDAT, 'script': scriptDAT, 'opfind': opfindDAT, 'execute': executeDAT,
            # TOP
            'circle': circleTOP, 'noise': noiseTOP, 'moviefilein': moviefileinTOP, 'constant': constantTOP,
            'ramp': rampTOP, 'texttop': textTOP, 'out': outTOP, 'render': renderTOP or outTOP, 'blur': blurTOP or constantTOP,
            'nulltop': nullTOP, 'composite': compositeTOP, 'level': levelTOP,
            # CHOP
            'constantchop': constantCHOP, 'noisechop': noiseCHOP, 'lfo': lfoCHOP, 'math': mathCHOP, 'selectchop': selectCHOP,
            'outchop': outCHOP, 'audiodevicein': audiodeviceinCHOP or constantCHOP, 'nullchop': nullCHOP,
            # SOP
            'sphere': sphereSOP, 'box': boxSOP, 'grid': gridSOP, 'line': lineSOP, 'nullsop': nullSOP, 'outsop': outSOP,
            'torus': torusSOP, 'transform': transformSOP, 'merge': mergeSOP,
            # COMP
            'base': baseCOMP, 'container': containerCOMP, 'geometrycomp': geometryCOMP, 'geometry': geometryCOMP,
            'camera': cameraCOMP, 'cam': cameraCOMP, 'light': lightCOMP, 'window': windowCOMP,
            # MAT
            'phong': phongMAT, 'pbr': pbrMAT, 'constantmat': constantMAT, 'material': phongMAT,
        }

        key = comp_type_str.lower().replace(' ', '').replace('-', '').replace('_', '')
        # First try dynamic resolver (covers ALL types present in this TD build)
        comp_type = _resolve_type(comp_type_str, family_hint)
        # Then static map
        comp_type = comp_type or comp_type_map.get(key)
        # Finally, direct getattr fallback
        if not comp_type:
            try:
                ct = getattr(td, comp_type_str, None)
                if isinstance(ct, type) and hasattr(td, 'OP') and issubclass(ct, td.OP):
                    comp_type = ct
            except Exception:
                comp_type = None
        if not comp_type:
            raise ValueError(f'Unsupported type: {comp_type_str}')

        if not name:
            base_name = key.replace('comp', '').replace('sop', '').replace('top', '').replace('dat', '').replace('mat', '')
            i = 1; name = f'{base_name}{i}'
            while op(f'{parent_path}/{name}'):
                i += 1; name = f'{base_name}{i}'

        # Positioning (explicit or smart)
        node_x = params.get('nodex'); node_y = params.get('nodey')
        if node_x is None or node_y is None:
            spacing_x, spacing_y = 220, 160
            fam_offsets = {'TOP': 0, 'CHOP': -300, 'SOP': -600, 'MAT': -900, 'COMP': -1200, 'DAT': -1500}

            # Detect family from the resolved class name (most reliable)
            family_guess = None
            comp_type_name = getattr(comp_type, '__name__', '') or str(comp_type)
            for suf, fam in [('TOP','TOP'),('CHOP','CHOP'),('SOP','SOP'),('DAT','DAT'),('COMP','COMP'),('MAT','MAT')]:
                if comp_type_name.endswith(suf):
                    family_guess = fam; break
            # Fallback: check the user label
            if not family_guess:
                kl = comp_type_str.lower()
                for token, fam in [('top','TOP'),('chop','CHOP'),('sop','SOP'),('dat','DAT'),('comp','COMP'),('mat','MAT')]:
                    if token in kl:
                        family_guess = fam; break
            # Fallback: use family_hint parameter
            if not family_guess and family_hint:
                fh = family_hint.strip().upper()
                if fh in fam_offsets:
                    family_guess = fh
            family = family_guess or 'COMP'
            try_fam = family
            base_y = fam_offsets.get(try_fam, 0)

            # Build occupied positions set from ALL children (not just same family)
            all_occupied = set()
            for c in getattr(parent_op, 'children', []) or []:
                if c and getattr(c, 'valid', False):
                    all_occupied.add((getattr(c, 'nodeX', -1), getattr(c, 'nodeY', -1)))

            # Optional alignment to connect_source
            align_src = None
            if connect_source:
                align_src = op(connect_source)
            if align_src and getattr(align_src, 'valid', False):
                node_x = getattr(align_src, 'nodeX', 0) + spacing_x
                node_y = getattr(align_src, 'nodeY', base_y)
                # Ensure we don't overlap even when source-aligned
                tries = 0
                while (node_x, node_y) in all_occupied and tries < 50:
                    node_x += spacing_x
                    tries += 1
            else:
                sibs = []
                for c in getattr(parent_op, 'children', []) or []:
                    if c and getattr(c, 'valid', False) and getattr(c, 'path', '') != f'{parent_path}/{name}':
                        if _get_op_family(c) == try_fam:
                            sibs.append(c)
                fam_count = len(sibs)
                cols = 6; row = fam_count // cols; col = fam_count % cols
                node_x = col * spacing_x; node_y = base_y - row * spacing_y
                tries = 0
                while (node_x, node_y) in all_occupied and tries < 50:
                    col += 1
                    if col >= cols:
                        col = 0; row += 1
                    node_x = col * spacing_x; node_y = base_y - row * spacing_y
                    tries += 1

        # Create
        try:
            new_op = parent_op.create(comp_type, name)
        except TypeError:
            # Fallback to TD auto-name then rename
            new_op = parent_op.create(comp_type)
            try:
                new_op.name = name
            except Exception:
                pass

        if not new_op or not getattr(new_op, 'valid', False):
            raise RuntimeError(f'Failed to create {name} in {parent_path}')

        # Apply position
        try:
            new_op.nodeX = node_x; new_op.nodeY = node_y
        except Exception as e:
            print('MCP Run Warning: Failed to set node position:', e)

        # Properties
        for k, v in (properties or {}).items():
            try:
                par = getattr(new_op.par, k, None)
                if par is None:
                    # Case-insensitive fallback
                    for pname in dir(new_op.par):
                        if pname.lower() == k.lower():
                            par = getattr(new_op.par, pname, None)
                            break
                if par is None:
                    continue
                cur = par.val; tgt_type = type(cur)
                try:
                    if tgt_type is bool: val = str(v).lower() in ['true', '1', 'on']
                    elif tgt_type is int: val = int(v)
                    elif tgt_type is float: val = float(v)
                    else: val = str(v)
                except Exception:
                    val = str(v)
                par.val = val
            except Exception as e:
                print(f'MCP Run Warning: Failed to set {k} on {new_op.path}: {e}')

        # Post-create render hints (camera/lights)
        try:
            t_str = str(getattr(new_op, 'type', '')).lower()
            if 'top' in t_str and ('render' in t_str or 'render' in name.lower()):
                cam = None; light = None
                for ch in getattr(parent_op, 'children', []) or []:
                    if not ch or not getattr(ch, 'valid', False):
                        continue
                    ct = str(getattr(ch, 'type', '')).lower(); cn = getattr(ch, 'name', '').lower()
                    if 'comp' in ct and ('camera' in cn or ct.startswith('camera')):
                        cam = ch
                    if 'comp' in ct and ('light' in cn or ct.startswith('light')):
                        light = ch
                if cam is not None:
                    for p in ['cam', 'camera']:
                        par = getattr(new_op.par, p, None)
                        if par is not None:
                            try:
                                par.val = cam; break
                            except Exception:
                                try:
                                    par.val = getattr(cam, 'path', cam)
                                    break
                                except Exception:
                                    pass
                if light is not None:
                    for p in ['light', 'lights', 'light1']:
                        par = getattr(new_op.par, p, None)
                        if par is not None:
                            try:
                                par.val = light; break
                            except Exception:
                                try:
                                    par.val = getattr(light, 'path', light)
                                    break
                                except Exception:
                                    pass
        except Exception as e:
            print('MCP Run: Post-create wiring hint failed:', e)

        # Connections
        connections = []
        if connect_source:
            src = op(connect_source)
            if src and getattr(src, 'valid', False):
                idx = None
                if isinstance(connect_parameter, str):
                    cp = connect_parameter.strip().lower()
                    if cp.startswith('input') and cp[5:].isdigit():
                        try: idx = int(cp[5:]) - 1
                        except Exception: idx = None
                if idx is not None:
                    if _connect_input(new_op, idx, src):
                        connections.append(f'{src.path} -> input {idx}')
                else:
                    par = getattr(new_op.par, connect_parameter, None) if isinstance(connect_parameter, str) else None
                    if par is not None:
                        try:
                            par.val = src
                            connections.append(f'{src.path} -> param {connect_parameter}')
                        except Exception:
                            pass
                    elif _connect_input(new_op, 0, src):
                        connections.append(f'{src.path} -> input 0')
        elif auto_connect:
            fam = _get_op_family(new_op)
            if fam:
                sibs = []
                for c in getattr(parent_op, 'children', []) or []:
                    if c and getattr(c, 'valid', False) and getattr(c, 'path', '') != new_op.path and _get_op_family(c) == fam:
                        sibs.append(c)
                if sibs:
                    sibs.sort(key=lambda x: getattr(x, 'nodeX', 0))
                    last = sibs[-1]
                    if _connect_input(new_op, 0, last):
                        connections.append(f'{last.path} -> input 0 (auto)')

        # Ensure minimum inputs for common nodes (TOP/SOP/CHOP)
        try:
            prefer = []
            if connect_source:
                prefer.append(connect_source)
            _ensure_min_inputs_op(new_op, parent_op, prefer)
        except Exception:
            pass

        # Optional preview
        if open_preview and hasattr(new_op, 'openViewer'):
            try:
                new_op.openViewer()
            except Exception:
                pass

        result = {
            'path': getattr(new_op, 'path', ''),
            'name': getattr(new_op, 'name', name),
            'type': str(getattr(new_op, 'type', comp_type_str)),
            'position': [node_x, node_y],
            'connections': connections
        }
        print(f'MCP Run: Created component at {new_op.path}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_create):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_delete(params_json, req_id=None):
    try:
        p = json.loads(params_json); path = p.get('path')
        if not path: raise ValueError('Missing path')
        obj = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not obj or not getattr(obj, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        obj_path = getattr(obj, 'path', '')
        if _is_protected_path(obj_path):
            result = {'deleted': None, 'skipped': obj_path, 'reason': 'protected'}
            print(f"MCP Run: Skipped deletion of protected operator {obj_path}")
            if req_id:
                _store_result(req_id, result)
            return
        parent = obj.parent(); name = getattr(obj, 'name', '(unknown)')
        parent_path = getattr(parent, 'path', '(invalid)')
        obj.destroy()
        result = {'deleted': name, 'from': parent_path}
        print(f'MCP Run: Deleted {name} from {parent_path}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_delete):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_set(params_json, req_id=None):
    try:
        p = json.loads(params_json)
        path = p.get('path'); param = p.get('parameter'); value_str = p.get('value')
        mode = (p.get('mode') or '').strip().lower()
        is_expr = bool(p.get('expression')) or mode == 'expr'
        if not path or not param or value_str is None:
            raise ValueError('Missing params')
        obj = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not obj or not getattr(obj, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        par = getattr(obj.par, param, None)
        # Case-insensitive fallback
        if par is None:
            for pname in dir(obj.par):
                if pname.lower() == param.lower():
                    par = getattr(obj.par, pname, None)
                    param = pname  # use actual name
                    break
        if par is None:
            raise ValueError(f"Parameter '{param}' not found on {path}")
        previous_value = str(par.val)
        if is_expr:
            par.expr = str(value_str)
            result = {'path': path, 'parameter': param, 'expression': str(value_str), 'previous_value': previous_value}
            print(f"MCP Run: Set expr {param}='{value_str}' on {path}")
        else:
            cur = par.val; tgt_type = type(cur)
            try:
                if tgt_type is bool: val = str(value_str).lower() in ['true', '1', 'on']
                elif tgt_type is int: val = int(float(value_str))
                elif tgt_type is float: val = float(value_str)
                else:
                    s = str(value_str).strip()
                    if s.startswith("op("):
                        inner = s[3:-1].strip().strip('"').strip("'")
                        cand = op(inner) or (op('/' + inner) if not inner.startswith('/') else None)
                        val = cand if cand and getattr(cand, 'valid', False) else s
                    else:
                        val = s
            except Exception:
                val = str(value_str)
            par.val = val
            result = {'path': path, 'parameter': param, 'value': str(val), 'previous_value': previous_value}
            print(f'MCP Run: Set {param}={val} on {path}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_set):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_set_many(params_json, req_id=None):
    """Batch set parameters. Args: { items: [{ path, parameter, value, mode?: 'val'|'expr' }] }"""
    try:
        p = json.loads(params_json)
        items = p.get('items') or []
        if not isinstance(items, list) or not items:
            raise ValueError('Missing items')
        ok = 0
        details = []
        for it in items:
            try:
                path = it.get('path'); param = it.get('parameter'); value = it.get('value')
                mode = (it.get('mode') or '').strip().lower()
                is_expr = bool(it.get('expression')) or mode == 'expr'
                if not path or not param:
                    continue
                obj = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
                if not obj or not getattr(obj, 'valid', False):
                    details.append({'path': path, 'parameter': param, 'error': 'invalid path'})
                    continue
                par = getattr(obj.par, param, None)
                # Case-insensitive fallback
                if par is None:
                    for pname in dir(obj.par):
                        if pname.lower() == param.lower():
                            par = getattr(obj.par, pname, None)
                            break
                if par is None:
                    details.append({'path': path, 'parameter': param, 'error': 'parameter not found'})
                    continue
                if is_expr:
                    try:
                        par.expr = str(value)
                        ok += 1
                        details.append({'path': path, 'parameter': param, 'expression': str(value)})
                    except Exception as e:
                        details.append({'path': path, 'parameter': param, 'error': str(e)})
                else:
                    cur = par.val; tgt_type = type(cur)
                    try:
                        if tgt_type is bool: val = str(value).lower() in ['true', '1', 'on']
                        elif tgt_type is int: val = int(float(value))
                        elif tgt_type is float: val = float(value)
                        else:
                            s = str(value).strip()
                            if s.startswith('op('):
                                inner = s[3:-1].strip().strip('"').strip("'")
                                cand = op(inner) or (op('/' + inner) if not inner.startswith('/') else None)
                                val = cand if cand and getattr(cand, 'valid', False) else s
                            else:
                                val = s
                    except Exception:
                        val = str(value)
                    try:
                        par.val = val
                        ok += 1
                        details.append({'path': path, 'parameter': param, 'value': str(val)})
                    except Exception as e:
                        details.append({'path': path, 'parameter': param, 'error': str(e)})
            except Exception:
                continue
        result = {'updated': ok, 'details': details}
        print(f"MCP Run: set_many updated {ok} parameter(s)")
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_set_many):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_execute(params_json, req_id=None):
    try:
        p = json.loads(params_json); code = p.get('code'); ctx = p.get('context')
        if not code: raise ValueError('Missing code')
        g = globals().copy(); l = {}
        if TDF:
            g['td'] = td; g['op'] = op; g['project'] = project
            ctx_op = op(ctx) if ctx else op('/')
            g['me'] = ctx_op if ctx_op and getattr(ctx_op, 'valid', False) else op('/')
        try:
            exec(code, g, l)
            rv = l.get('result', 'Python code executed successfully.')
            # Ensure result is JSON-serializable
            try:
                json.dumps(rv)
                result_val = rv
            except (TypeError, ValueError):
                result_val = str(rv)
            result = {'result': result_val}
            print('MCP Run: Executed Python. Result:', result_val)
        except AttributeError as ae:
            if "has no attribute 'Parameter'" in str(ae):
                result = {'result': f'Note: {ae}'}
                print('MCP Run Python Execution Note:', ae)
            else:
                raise
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_execute):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_list(params_json, req_id=None):
    try:
        p = json.loads(params_json); path = p.get('path', '/'); type_filter = p.get('type_filter')
        tgt = op(path)
        if not tgt or not getattr(tgt, 'valid', False):
            raise ValueError(f'Invalid path: {path}')
        items = []
        for ch in getattr(tgt, 'children', []) or []:
            if ch and getattr(ch, 'valid', False):
                ch_type = str(getattr(ch, 'type', ''))
                if type_filter and type_filter.upper() not in ch_type.upper():
                    continue
                items.append({'path': getattr(ch, 'path', ''), 'type': ch_type, 'name': getattr(ch, 'name', '')})
        result = {'path': path, 'children': items}
        print(f'MCP Run List Result ({path}): {len(items)} children')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_list):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_get(params_json, req_id=None):
    try:
        p = json.loads(params_json); path = p.get('path'); param = p.get('parameter')
        if not path: raise ValueError('Missing path')
        obj = op(path)
        if not obj or not getattr(obj, 'valid', False):
            result = {'path': path, 'exists': False, 'error': 'Component not found or invalid'}
            if req_id:
                _store_result(req_id, result)
            return
        if param:
            par = getattr(obj.par, param, None)
            # Case-insensitive fallback
            if par is None:
                for pname in dir(obj.par):
                    if pname.lower() == param.lower():
                        par = getattr(obj.par, pname, None)
                        param = pname
                        break
            if par is not None:
                try: val = par.eval()
                except Exception: val = par.val
                result = {'path': path, 'exists': True, 'parameter': param, 'value': str(val), 'type': type(val).__name__}
            else:
                result = {'path': path, 'exists': True, 'parameter': param, 'error': 'Parameter not found'}
        else:
            names = [pa.name for pa in getattr(obj, 'pars', lambda: [])() if pa]
            result = {'path': path, 'exists': True, 'type': str(getattr(obj, 'type', '')), 'name': getattr(obj, 'name', ''), 'parameters': names}
        print(f'MCP Run Get Result ({path})')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_get):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_show_preview(params_json, req_id=None):
    try:
        p = json.loads(params_json); path = p.get('path')
        if not path: raise ValueError('Missing path')
        target = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not target or not getattr(target, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        if hasattr(target, 'openViewer'):
            target.openViewer()
            result = {'path': target.path, 'opened': True}
            print(f'MCP Run: Opened preview viewer for {target.path}')
        else:
            result = {'path': target.path, 'opened': False, 'reason': 'no viewer available'}
            print(f'MCP Run: {target.path} has no viewer to open')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_show_preview):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_layout(params_json, req_id=None):
    try:
        p = json.loads(params_json)
        parent_path = p.get('parent', '/project1')
        spacing_x = int(p.get('spacing_x', 220)); spacing_y = int(p.get('spacing_y', 160)); cols = int(p.get('cols', 6))
        parent_op_obj = op(parent_path)
        if not parent_op_obj or not getattr(parent_op_obj, 'valid', False):
            raise ValueError(f'Invalid parent: {parent_path}')
        fam_offsets = {'TOP': 0, 'CHOP': -300, 'SOP': -600, 'MAT': -900, 'COMP': -1200, 'DAT': -1500}
        buckets = {}
        for ch in getattr(parent_op_obj, 'children', []) or []:
            if ch and getattr(ch, 'valid', False):
                fam = _get_op_family(ch) or 'COMP'
                buckets.setdefault(fam, []).append(ch)
        total = 0
        for fam, nodes in buckets.items():
            nodes.sort(key=lambda n: (getattr(n, 'nodeX', 0), getattr(n, 'nodeY', 0)))
            base_y = fam_offsets.get(fam, 0)
            for i, n in enumerate(nodes):
                row = i // cols; col = i % cols
                n.nodeX = col * spacing_x; n.nodeY = base_y - row * spacing_y
                total += 1
        result = {'parent': parent_path, 'nodes_repositioned': total}
        print(f'MCP Run: Laid out {total} nodes under {parent_path}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_layout):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_build_workflow(params_json, req_id=None):
    """Builds a simple preset workflow and optionally opens a preview.
    Presets: audio_experience, interactive_installation, render_scene/3d/render3d/scene
    Args: { preset, parent='/project1', name_prefix='', open_preview=True }
    """
    try:
        p = json.loads(params_json)
        preset = (p.get('preset') or '').lower()
        parent_path = p.get('parent', '/project1')
        name_prefix = p.get('name_prefix', '')
        open_prev = p.get('open_preview', True)

        parent = op(parent_path)
        if not parent or not getattr(parent, 'valid', False):
            raise ValueError(f'Invalid parent: {parent_path}')

        def uniq(base):
            i = 1
            while op(f"{parent_path}/{name_prefix}{base}{i}"):
                i += 1
            return f"{name_prefix}{base}{i}"

        preview = None
        nodes_created = []

        if 'audio' in preset:
            ain = parent.create(audiodeviceinCHOP or constantCHOP, uniq('audioin'))
            nodes_created.append(getattr(ain, 'path', ''))
            aout = parent.create(outCHOP, uniq('out'))
            nodes_created.append(getattr(aout, 'path', ''))
            _connect_input(aout, 0, ain)
            preview = aout

        elif 'interactive' in preset or 'install' in preset:
            src = parent.create(moviefileinTOP or constantTOP, uniq('movie'))
            nodes_created.append(getattr(src, 'path', ''))
            out = parent.create(outTOP, uniq('out'))
            nodes_created.append(getattr(out, 'path', ''))
            _connect_input(out, 0, src)
            preview = out

        elif any(k in preset for k in ['render_scene', '3d', 'render3d', 'scene']):
            geo = parent.create(geometryCOMP, uniq('geo'))
            nodes_created.append(getattr(geo, 'path', ''))
            try:
                if geo and getattr(geo, 'valid', False):
                    sop = geo.create(sphereSOP or boxSOP, 'shape1')
                    nodes_created.append(getattr(sop, 'path', ''))
            except Exception:
                pass
            mat = parent.create(phongMAT or constantMAT, uniq('mat'))
            nodes_created.append(getattr(mat, 'path', ''))
            try:
                for par_name in ['material', 'mat']:
                    par = getattr(geo.par, par_name, None)
                    if par is not None:
                        par.val = mat; break
            except Exception:
                pass
            cam = parent.create(cameraCOMP, uniq('camera'))
            nodes_created.append(getattr(cam, 'path', ''))
            light = parent.create(lightCOMP, uniq('light'))
            nodes_created.append(getattr(light, 'path', ''))
            rend = parent.create(renderTOP or outTOP, uniq('render'))
            nodes_created.append(getattr(rend, 'path', ''))
            try:
                for par_name in ['cam', 'camera']:
                    par = getattr(rend.par, par_name, None)
                    if par is not None:
                        par.val = cam; break
            except Exception:
                pass
            try:
                for par_name in ['light', 'lights', 'light1']:
                    par = getattr(rend.par, par_name, None)
                    if par is not None:
                        par.val = light; break
            except Exception:
                pass
            preview = rend

        else:
            raise ValueError(f"Unknown preset: {preset}")

        if open_prev and preview and hasattr(preview, 'openViewer'):
            try:
                preview.openViewer()
            except Exception:
                pass

        result = {'preset': preset, 'nodes_created': nodes_created}
        print(f'MCP Run: Built workflow "{preset}" with {len(nodes_created)} nodes')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_build_workflow):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_connect_nodes(params_json, req_id=None):
    """Connect nodes based on a list and mode.
    Args: { nodes: [paths], mode: 'sequence'|'parallel'|'custom', custom_connections: [[src,tgt], ...] }
    """
    try:
        p = json.loads(params_json)
        nodes = p.get('nodes', [])
        mode = p.get('mode', 'sequence')
        pairs = p.get('custom_connections', [])
        made = []
        if mode == 'sequence' and len(nodes) >= 2:
            for i in range(len(nodes) - 1):
                src = op(nodes[i]); tgt = op(nodes[i+1])
                if src and getattr(src, 'valid', False) and tgt and getattr(tgt, 'valid', False):
                    if _connect_input(tgt, 0, src):
                        made.append(f'{src.path}->{tgt.path}')
        elif mode == 'parallel' and len(nodes) >= 2:
            hub = op(nodes[0])
            if hub and getattr(hub, 'valid', False):
                for i in range(1, len(nodes)):
                    src = op(nodes[i])
                    if src and getattr(src, 'valid', False):
                        if _connect_input(hub, i-1, src):
                            made.append(f'{src.path}->{hub.path} (input {i-1})')
        elif mode == 'custom':
            for a,b in pairs:
                src = op(a); tgt = op(b)
                if src and getattr(src, 'valid', False) and tgt and getattr(tgt, 'valid', False):
                    if _connect_input(tgt, 0, src):
                        made.append(f'{src.path}->{tgt.path}')
        # For parallel hub patterns, ensure hub has enough inputs
        try:
            if mode == 'parallel' and nodes:
                hub = op(nodes[0])
                if hub and getattr(hub, 'valid', False):
                    p_op = hub.parent()
                    _ensure_min_inputs_op(hub, p_op)
        except Exception:
            pass
        result = {'connections_made': made, 'mode': mode}
        print(f'MCP Run: Connected {len(made)} link(s)')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_connect_nodes):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_ensure_inputs(params_json, req_id=None):
    """Ensure a node has the minimum number of inputs (adds fallbacks if needed).
    Args: { path: '/final_comp', min_inputs?: 2 }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path'); min_inputs = int(p.get('min_inputs', 2))
        if not path:
            raise ValueError('Missing path')
        node = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not node or not getattr(node, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        parent_op_ref = node.parent()
        # Count inputs before
        before = sum(1 for inp in (getattr(node, 'inputs', []) or []) if inp)
        _ensure_min_inputs_op(node, parent_op_ref)
        # Count inputs after
        after = sum(1 for inp in (getattr(node, 'inputs', []) or []) if inp)
        result = {'path': path, 'inputs_before': before, 'inputs_after': after, 'inputs_added': after - before}
        print(f"MCP Run: ensure_inputs applied to {path}, added {after - before} input(s)")
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_ensure_inputs):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_list_types(params_json, req_id=None):
    """Returns available operator types. Args: { family: 'SOP'|'TOP'|..., search: 'substr' }"""
    try:
        p = json.loads(params_json)
        fam = p.get('family'); search = (p.get('search') or '').lower()
        if fam:
            fam = fam.strip().upper()
        families = [fam] if fam in OP_TYPES_BY_FAMILY else list(OP_TYPES_BY_FAMILY.keys())
        result_families = {}
        for f in families:
            items = sorted(list(OP_TYPES_BY_FAMILY.get(f, {}).keys()))
            if search:
                items = [it for it in items if search in it.lower()]
            result_families[f] = items
        result = {'families': result_families}
        print(f"MCP Run: list_types returned {sum(len(v) for v in result_families.values())} types")
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_list_types):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_list_parameters(params_json, req_id=None):
    """List all parameters of a component with their current values.
    Args: { path: '/project1/circle1' }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path')
        if not path:
            raise ValueError('Missing path')
        obj = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not obj or not getattr(obj, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        params_list = []
        try:
            for par in obj.pars():
                if par:
                    try:
                        val = par.eval()
                    except Exception:
                        val = par.val
                    params_list.append({
                        'name': par.name,
                        'value': str(val),
                        'type': type(val).__name__
                    })
        except Exception:
            pass
        result = {
            'path': path,
            'type': str(getattr(obj, 'type', '')),
            'parameters': params_list
        }
        print(f"MCP Run: list_parameters for {path} ({len(params_list)} params)")
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_list_parameters):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_auto_connect(params_json, req_id=None):
    """Smart auto-connect between two nodes based on types.
    Args: { source: '/project1/noise1', target: '/project1/blur1', connection_type: 'auto'|'input'|'output' }
    """
    try:
        p = json.loads(params_json)
        source_path = p.get('source')
        target_path = p.get('target')
        conn_type = (p.get('connection_type') or 'auto').lower()

        if not source_path or not target_path:
            raise ValueError('Missing source or target path')

        src = op(source_path) or (op('/' + source_path) if not source_path.startswith('/') else None)
        tgt = op(target_path) or (op('/' + target_path) if not target_path.startswith('/') else None)

        if not src or not getattr(src, 'valid', False):
            raise ValueError(f'Invalid source: {source_path}')
        if not tgt or not getattr(tgt, 'valid', False):
            raise ValueError(f'Invalid target: {target_path}')

        connections_made = []
        src_fam = _get_op_family(src)
        tgt_fam = _get_op_family(tgt)

        if conn_type == 'auto':
            # Same family: wire src output -> tgt input 0
            if src_fam == tgt_fam and src_fam is not None:
                if _connect_input(tgt, 0, src):
                    connections_made.append(f'{src_fam}: {src.path} -> {tgt.path}')
            # Cross-family: try input connection
            elif _connect_input(tgt, 0, src):
                connections_made.append(f'{src_fam or "?"}->{tgt_fam or "?"}: {src.path} -> {tgt.path}')
        elif conn_type == 'input':
            if _connect_input(tgt, 0, src):
                connections_made.append(f'input: {src.path} -> {tgt.path}')
        else:
            if _connect_input(tgt, 0, src):
                connections_made.append(f'{conn_type}: {src.path} -> {tgt.path}')

        # Record in history
        if connections_made:
            connection_history.append({
                'source': source_path, 'target': target_path,
                'source_family': src_fam, 'target_family': tgt_fam,
                'connections': connections_made, 'timestamp': time.time()
            })

        result = {'source': source_path, 'target': target_path, 'connections_made': connections_made}
        print(f'MCP Run: auto_connect made {len(connections_made)} connection(s)')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_auto_connect):', e)
        if req_id:
            _store_result(req_id, error=str(e))


# --- New tools: disconnect, rename, set_text, timeline, chop_export, custom_par, node_style ---

def _run_disconnect(params_json, req_id=None):
    """Disconnect inputs from a node.
    Args: { path, input_index?: int (omit to clear all), count?: int }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path')
        input_index = p.get('input_index')  # None = all
        if not path:
            raise ValueError('Missing path')
        node = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not node or not getattr(node, 'valid', False):
            raise ValueError(f'Invalid component: {path}')

        disconnected = []
        if input_index is not None:
            idx = int(input_index)
            try:
                node.inputConnectors[idx].disconnect()
                disconnected.append(idx)
            except Exception:
                try:
                    node.setInput(idx, None)
                    disconnected.append(idx)
                except Exception as e2:
                    raise ValueError(f'Failed to disconnect input {idx}: {e2}')
        else:
            # Disconnect all inputs
            try:
                ins = node.inputConnectors
                for i in range(len(ins)):
                    try:
                        ins[i].disconnect()
                        disconnected.append(i)
                    except Exception:
                        try:
                            node.setInput(i, None)
                            disconnected.append(i)
                        except Exception:
                            pass
            except Exception:
                pass

        result = {'path': path, 'disconnected_inputs': disconnected}
        print(f'MCP Run: Disconnected {len(disconnected)} input(s) on {path}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_disconnect):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_rename(params_json, req_id=None):
    """Rename a node.
    Args: { path, new_name }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path'); new_name = p.get('new_name')
        if not path or not new_name:
            raise ValueError('Missing path or new_name')
        node = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not node or not getattr(node, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        old_name = getattr(node, 'name', '')
        node.name = str(new_name)
        new_path = getattr(node, 'path', '')
        result = {'old_name': old_name, 'new_name': str(new_name), 'new_path': new_path}
        print(f'MCP Run: Renamed {old_name} -> {new_name}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_rename):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_set_text(params_json, req_id=None):
    """Set the text content of a DAT operator.
    Args: { path, text, append?: bool }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path'); text = p.get('text', '')
        append = bool(p.get('append', False))
        if not path:
            raise ValueError('Missing path')
        node = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not node or not getattr(node, 'valid', False):
            raise ValueError(f'Invalid component: {path}')
        if not hasattr(node, 'text'):
            raise ValueError(f'{path} is not a text-capable DAT')
        # Disconnect inputs that may lock the DAT content
        try:
            ins = getattr(node, 'inputConnectors', [])
            for ic in ins:
                try:
                    ic.disconnect()
                except Exception:
                    pass
        except Exception:
            pass
        if append:
            node.text += str(text)
        else:
            node.text = str(text)
        result = {'path': path, 'length': len(node.text), 'appended': append}
        print(f'MCP Run: Set text on {path} ({len(node.text)} chars)')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_set_text):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_timeline(params_json, req_id=None):
    """Control the timeline.
    Args: { action: 'play'|'pause'|'stop'|'get'|'set_frame'|'set_fps'|'set_range',
            frame?: int, fps?: float, start?: int, end?: int }
    """
    try:
        p = json.loads(params_json)
        action = (p.get('action') or 'get').lower()

        if not TDF:
            raise ValueError('Timeline control requires TouchDesigner environment')

        time_op = op('/local/time')
        if not time_op or not getattr(time_op, 'valid', False):
            raise ValueError('Timeline operator /local/time not found')

        result = {}
        if action == 'play':
            time_op.par.play = True
            result = {'action': 'play', 'playing': True}
        elif action == 'pause' or action == 'stop':
            time_op.par.play = False
            result = {'action': action, 'playing': False}
        elif action == 'set_frame':
            frame = p.get('frame')
            if frame is None:
                raise ValueError('Missing frame')
            time_op.par.play = False
            absTime.frame = int(frame)
            result = {'action': 'set_frame', 'frame': int(absTime.frame)}
        elif action == 'set_fps':
            fps = p.get('fps')
            if fps is None:
                raise ValueError('Missing fps')
            time_op.par.rate = float(fps)
            result = {'action': 'set_fps', 'fps': float(time_op.par.rate)}
        elif action == 'set_range':
            start = p.get('start'); end = p.get('end')
            if start is not None:
                time_op.par.start = int(start)
            if end is not None:
                time_op.par.end = int(end)
            result = {'action': 'set_range', 'start': int(time_op.par.start), 'end': int(time_op.par.end)}
        elif action == 'get':
            result = {
                'action': 'get',
                'frame': int(absTime.frame),
                'fps': float(time_op.par.rate),
                'playing': bool(time_op.par.play),
                'realTime': bool(getattr(project, 'realTime', True)),
                'start': int(time_op.par.start),
                'end': int(time_op.par.end),
            }
        else:
            raise ValueError(f'Unknown timeline action: {action}')

        print(f'MCP Run: Timeline {action}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_timeline):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_chop_export(params_json, req_id=None):
    """Set up a CHOP export binding from a CHOP channel to a parameter.
    Args: { chop_path, channel, target_path, parameter, enable?: bool }
    """
    try:
        p = json.loads(params_json)
        chop_path = p.get('chop_path'); channel = p.get('channel')
        target_path = p.get('target_path'); parameter = p.get('parameter')
        enable = p.get('enable', True)

        if not chop_path or not target_path or not parameter:
            raise ValueError('Missing chop_path, target_path, or parameter')

        chop_node = op(chop_path) or (op('/' + chop_path) if not chop_path.startswith('/') else None)
        if not chop_node or not getattr(chop_node, 'valid', False):
            raise ValueError(f'Invalid CHOP: {chop_path}')

        target_node = op(target_path) or (op('/' + target_path) if not target_path.startswith('/') else None)
        if not target_node or not getattr(target_node, 'valid', False):
            raise ValueError(f'Invalid target: {target_path}')

        par = getattr(target_node.par, parameter, None)
        if par is None:
            for pname in dir(target_node.par):
                if pname.lower() == parameter.lower():
                    par = getattr(target_node.par, pname, None)
                    parameter = pname
                    break
        if par is None:
            raise ValueError(f"Parameter '{parameter}' not found on {target_path}")

        if enable:
            # Set expression referencing the CHOP channel
            if channel:
                par.expr = f"op('{chop_node.path}')['{channel}']"
            else:
                par.expr = f"op('{chop_node.path}')[0]"
            par.mode = 2  # ParMode.EXPRESSION
        else:
            par.mode = 0  # ParMode.CONSTANT
            par.expr = ''

        result = {
            'chop_path': chop_path, 'channel': channel or '0',
            'target_path': target_path, 'parameter': parameter,
            'enabled': bool(enable)
        }
        print(f'MCP Run: CHOP export {"enabled" if enable else "disabled"}: {chop_path}[{channel}] -> {target_path}.{parameter}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_chop_export):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_custom_par(params_json, req_id=None):
    """Add or remove custom parameters on a COMP.
    Args: { path, action: 'add'|'remove', name, par_type?: 'float'|'int'|'string'|'bool'|'menu'|'pulse',
            label?: str, default?: any, min?: float, max?: float, page?: str }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path'); action = (p.get('action') or 'add').lower()
        name = p.get('name')
        if not path or not name:
            raise ValueError('Missing path or name')

        # TD requires custom par names to start with uppercase
        if name and name[0].islower():
            name = name[0].upper() + name[1:]

        node = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not node or not getattr(node, 'valid', False):
            raise ValueError(f'Invalid component: {path}')

        if action == 'remove':
            try:
                par = getattr(node.par, name, None)
                if par is None:
                    raise ValueError(f"Parameter '{name}' not found")
                page = par.page
                page.destroy()  # Removes the page; for single par removal we need different approach
            except Exception:
                # Try destroying individual parameter
                try:
                    node.destroyCustomPars(name)
                except Exception as e2:
                    raise ValueError(f'Failed to remove parameter: {e2}')
            result = {'path': path, 'action': 'remove', 'name': name}
        else:
            par_type = (p.get('par_type') or p.get('type') or 'float').lower()
            label = p.get('label', name)
            default = p.get('default')
            min_val = p.get('min'); max_val = p.get('max')
            page_name = p.get('page', 'Custom')

            # Get or create the page
            page = None
            try:
                for pg in node.customPages:
                    if pg.name == page_name:
                        page = pg
                        break
            except Exception:
                pass
            if page is None:
                try:
                    page = node.appendCustomPage(page_name)
                except Exception as e:
                    raise ValueError(f'Failed to create custom page: {e}')

            # Add parameter by type
            new_par = None
            if par_type in ('float', 'number'):
                new_par = page.appendFloat(name, label=label)
            elif par_type == 'int':
                new_par = page.appendInt(name, label=label)
            elif par_type in ('string', 'str', 'text'):
                new_par = page.appendStr(name, label=label)
            elif par_type in ('bool', 'toggle'):
                new_par = page.appendToggle(name, label=label)
            elif par_type == 'menu':
                new_par = page.appendMenu(name, label=label)
            elif par_type == 'pulse':
                new_par = page.appendPulse(name, label=label)
            else:
                new_par = page.appendFloat(name, label=label)

            # Apply settings – appendFloat etc. return a ParGroup; [0] → Par
            if new_par is not None:
                try:
                    par_obj = new_par[0]
                except Exception:
                    par_obj = new_par
                # Cast default using par_type, not introspection (avoids bool(ParGroup))
                if default is not None:
                    try:
                        if par_type in ('float', 'number'):
                            par_obj.default = float(default)
                            par_obj.val = float(default)
                        elif par_type == 'int':
                            par_obj.default = int(default)
                            par_obj.val = int(default)
                        elif par_type in ('bool', 'toggle'):
                            par_obj.default = bool(default)
                            par_obj.val = bool(default)
                        else:
                            par_obj.default = default
                            par_obj.val = default
                    except Exception:
                        pass
                if min_val is not None:
                    try: par_obj.min = float(min_val); par_obj.clampMin = True
                    except Exception: pass
                if max_val is not None:
                    try: par_obj.max = float(max_val); par_obj.clampMax = True
                    except Exception: pass

            result = {'path': path, 'action': 'add', 'name': name, 'par_type': par_type, 'page': page_name}

        print(f'MCP Run: custom_par {action} "{name}" on {path}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_custom_par):', e)
        if req_id:
            _store_result(req_id, error=str(e))


def _run_node_style(params_json, req_id=None):
    """Set node visual style (color, comment, tags).
    Args: { path, color?: [r,g,b] (0-1 floats), comment?: str, tags?: [str] }
    """
    try:
        p = json.loads(params_json)
        path = p.get('path')
        if not path:
            raise ValueError('Missing path')
        node = op(path) or (op('/' + path) if isinstance(path, str) and not path.startswith('/') else None)
        if not node or not getattr(node, 'valid', False):
            raise ValueError(f'Invalid component: {path}')

        changes = {}
        color = p.get('color')
        if color and isinstance(color, (list, tuple)) and len(color) >= 3:
            try:
                node.color = (float(color[0]), float(color[1]), float(color[2]))
                changes['color'] = list(color[:3])
            except Exception as e:
                changes['color_error'] = str(e)

        comment = p.get('comment')
        if comment is not None:
            try:
                node.comment = str(comment)
                changes['comment'] = str(comment)
            except Exception as e:
                changes['comment_error'] = str(e)

        tags_list = p.get('tags')
        if tags_list is not None and isinstance(tags_list, list):
            try:
                node.tags = tags_list
                changes['tags'] = tags_list
            except Exception as e:
                changes['tags_error'] = str(e)

        result = {'path': path, 'changes': changes}
        print(f'MCP Run: node_style on {path}: {changes}')
        if req_id:
            _store_result(req_id, result)
    except Exception as e:
        print('MCP Run Error (_run_node_style):', e)
        if req_id:
            _store_result(req_id, error=str(e))


# --- HTTP Server ---
server_thread = None
server_instance = None
server_running = False
SERVER_HOST = '127.0.0.1'
SERVER_PORT = int(os.environ.get('TD_MCP_PORT', '8053'))

class ThreadingHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, dat_path, bind_and_activate=True):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.dat_path = dat_path

class TouchDesignerMCPHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def _send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print('Error sending JSON response:', e)

    def _handle_error(self, message, status=400):
        print(f'MCP Server Error: {message} (Status: {status})')
        self._send_json({'error': {'message': message, 'code': -32000}}, status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path in ('/', '/api/status'):
                self._send_json({
                    'status': 'running', 'touchdesigner': True, 'version': '2.0.0',
                    'features': [
                        'create','delete','list','get','set','set_many','execute_python',
                        'build_workflow','connect_nodes','show_preview','layout','list_types',
                        'types_json','ensure_inputs','set_dat','list_parameters','auto_connect',
                        'disconnect','rename','set_text','timeline','chop_export','custom_par','node_style'
                    ]
                })
            else:
                self._handle_error('Endpoint not found', 404)
        except Exception as e:
            self._handle_error(f'Error handling GET: {e}', 500)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length == 0:
                return self._handle_error('Empty request body', 400)
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            path = urlparse(self.path).path
            if path == '/mcp':
                self._handle_mcp(data)
            elif path == '/context':
                self._send_json({'contextItems': []})
            elif path == '/types':
                # convenience endpoint
                self._handle_list_types(data)
            elif path == '/types_json':
                # return types as JSON instead of printing
                self._handle_types_json(data)
            else:
                self._handle_error(f'Unknown POST endpoint: {path}', 404)
        except json.JSONDecodeError:
            self._handle_error('Invalid JSON', 400)
        except Exception as e:
            self._handle_error(f'Error handling POST: {e}', 500)

    def _handle_mcp(self, data):
        method = data.get('method'); params = data.get('params', {})
        if not method:
            return self._handle_error("Missing 'method'", 400)
        try:
            # Alias support for external clients (e.g., n8n) using natural names
            m = str(method).strip().lower()
            alias_family = None
            # Generic "create <label>" support (natural language convenience)
            if m.startswith('create '):
                label = m[len('create '):].strip()
                method = 'create'
                if not isinstance(params, dict):
                    params = {}
                if 'type' not in params:
                    params = {**params, 'type': label}
                if 'family' not in params:
                    base = _norm_name(SYNONYM_MAP.get(label, label))
                    fam = DEFAULT_FAMILY_HINTS.get(base)
                    if fam:
                        params = {**params, 'family': fam}
            if m in ('create sop', 'createsop'):
                method = 'create'; alias_family = 'SOP'
            elif m in ('create top', 'createtop'):
                method = 'create'; alias_family = 'TOP'
            elif m in ('create chop', 'createchop'):
                method = 'create'; alias_family = 'CHOP'
            elif m in ('create comp', 'createcomp', 'create component'):
                method = 'create'; alias_family = 'COMP'
            elif m in ('create dat', 'createdat'):
                method = 'create'; alias_family = 'DAT'
            elif m in ('create mat', 'createmat', 'create material'):
                method = 'create'; alias_family = 'MAT'
            elif m in ('show preview', 'showpreview', 'open viewer', 'openviewer'):
                method = 'show_preview'
            elif m in ('connect nodes', 'connectnodes'):
                method = 'connect_nodes'
            elif m in ('build workflow', 'buildworkflow'):
                method = 'build_workflow'
            elif m in ('list types', 'listtypes'):
                method = 'list_types'
            elif m in ('set dat', 'setdat', 'set module', 'setmodule'):
                method = 'set_dat'
            elif m in ('auto connect', 'autoconnect', 'auto_connect'):
                method = 'auto_connect'
            elif m in ('list parameters', 'listparameters', 'list_parameters'):
                method = 'list_parameters'
            elif m in ('ensure inputs', 'ensureinputs', 'ensure_inputs'):
                method = 'ensure_inputs'
            elif m in ('disconnect', 'disconnect_inputs', 'clear inputs', 'clearinputs'):
                method = 'disconnect'
            elif m in ('rename', 'rename_node', 'renamenode'):
                method = 'rename'
            elif m in ('set text', 'settext', 'set_text', 'set dat text', 'setdattext'):
                method = 'set_text'
            elif m in ('timeline', 'playback', 'transport'):
                method = 'timeline'
            elif m in ('chop export', 'chopexport', 'chop_export', 'export chop', 'exportchop'):
                method = 'chop_export'
            elif m in ('custom par', 'custompar', 'custom_par', 'add parameter', 'addparameter'):
                method = 'custom_par'
            elif m in ('node style', 'nodestyle', 'node_style', 'set color', 'setcolor', 'node color', 'nodecolor'):
                method = 'node_style'

            if alias_family and isinstance(params, dict) and 'family' not in params:
                # inject family hint for create aliases
                params = {**params, 'family': alias_family}

            # Timeouts: 10s reads, 15s mutations, 30s heavy ops
            if method == 'create': res = self._tool('_run_create', params, timeout=15.0)
            elif method == 'delete': res = self._tool('_run_delete', params, timeout=15.0)
            elif method == 'set': res = self._tool('_run_set', params, timeout=15.0)
            elif method == 'execute_python': res = self._tool('_run_execute', params, timeout=30.0)
            elif method == 'list': res = self._tool('_run_list', params, timeout=10.0)
            elif method == 'get': res = self._tool('_run_get', params, timeout=10.0)
            elif method == 'show_preview': res = self._tool('_run_show_preview', params, timeout=10.0)
            elif method == 'layout': res = self._tool('_run_layout', params, timeout=15.0)
            elif method == 'build_workflow': res = self._tool('_run_build_workflow', params, timeout=30.0)
            elif method == 'connect_nodes': res = self._tool('_run_connect_nodes', params, timeout=15.0)
            elif method == 'set_many': res = self._tool('_run_set_many', params, timeout=15.0)
            elif method == 'ensure_inputs': res = self._tool('_run_ensure_inputs', params, timeout=15.0)
            elif method == 'list_types': res = self._tool('_run_list_types', params, timeout=10.0)
            elif method == 'list_parameters': res = self._tool('_run_list_parameters', params, timeout=10.0)
            elif method == 'auto_connect': res = self._tool('_run_auto_connect', params, timeout=15.0)
            elif method == 'disconnect': res = self._tool('_run_disconnect', params, timeout=15.0)
            elif method == 'rename': res = self._tool('_run_rename', params, timeout=15.0)
            elif method == 'set_text': res = self._tool('_run_set_text', params, timeout=15.0)
            elif method == 'timeline': res = self._tool('_run_timeline', params, timeout=10.0)
            elif method == 'chop_export': res = self._tool('_run_chop_export', params, timeout=15.0)
            elif method == 'custom_par': res = self._tool('_run_custom_par', params, timeout=15.0)
            elif method == 'node_style': res = self._tool('_run_node_style', params, timeout=15.0)
            elif method == 'set_dat':
                # Update the server's control module DAT path without requiring a restart
                newp = None
                if isinstance(params, dict):
                    newp = params.get('path') or params.get('dat') or params.get('module')
                if not newp:
                    return self._handle_error("Missing 'path' for set_dat", 400)
                self.server.dat_path = str(newp)
                self._send_json({'result': {'content': [{'type': 'text', 'text': f"dat_path set to {self.server.dat_path}"}]}})
                return
            else: return self._handle_error(f'Unknown MCP method: {method}', 404)
            self._send_json({'result': res})
        except Exception as e:
            self._send_json({'error': {'message': f"Error executing MCP method '{method}': {e}", 'code': -32001}}, 500)

    def _tool(self, func_name, params, timeout=5.0):
        req_id = str(uuid.uuid4())
        _pending_results[req_id] = {'event': threading.Event(), 'result': None, 'error': None}
        pj = json.dumps(params)
        # Robust dispatch: prefer calling the already-loaded Python module by name; if missing, fallback to DAT.
        code = (
            "import sys\n"
            "mk = " + repr(MODULE_KEY) + "\n"
            "fn = '" + func_name + "'\n"
            "pj = " + repr(pj) + "\n"
            "rid = " + repr(req_id) + "\n"
            "m = sys.modules.get(mk)\n"
            "if m is not None:\n"
            "    try:\n"
            "        getattr(m, fn)(pj, rid)\n"
            "    except Exception as e:\n"
            "        print('MCP Dispatch Error (module):', e)\n"
            "        try:\n"
            "            m._store_result(rid, error=str(e))\n"
            "        except Exception:\n"
            "            pass\n"
            "else:\n"
            "    try:\n"
            "        dp = '" + self.server.dat_path.replace("'", "\\'") + "'\n"
            "        d = op(dp) if 'op' in globals() else None\n"
            "    except Exception:\n"
            "        d = None\n"
            "    if not d or not getattr(d, 'valid', False):\n"
            "        try:\n"
            "            d = op('/project1/mcp_server') or op('mcp_server') or op('/mcp_server')\n"
            "        except Exception:\n"
            "            d = None\n"
            "    if d and getattr(d, 'valid', False):\n"
            "        try:\n"
            "            getattr(mod(d.path), fn)(pj, rid)\n"
            "        except Exception as e:\n"
            "            print('MCP Dispatch Error (fallback DAT):', e)\n"
            "            try:\n"
            "                m = sys.modules.get(mk)\n"
            "                if m: m._store_result(rid, error=str(e))\n"
            "            except Exception:\n"
            "                pass\n"
            "    else:\n"
            "        print('MCP Dispatch Error: control module/DAT unavailable')\n"
            "        try:\n"
            "            m = sys.modules.get(mk)\n"
            "            if m: m._store_result(rid, error='Control module/DAT unavailable')\n"
            "        except Exception:\n"
            "            pass\n"
        )
        run(code, delayFrames=1)
        # Wait for result from TD main thread
        result = _wait_for_result(req_id, timeout=timeout)
        if isinstance(result, dict) and 'error' in result and len(result) == 1:
            # Return error as MCP content
            return {'content': [{'type': 'text', 'text': f'Error: {result["error"]}'}]}
        # Wrap result in MCP content format
        if isinstance(result, dict) and 'content' in result:
            return result
        return {'content': [{'type': 'text', 'text': json.dumps(result, default=str)}]}

    def _handle_list_types(self, data):
        # Queue via robust dispatcher
        try:
            params = data.get('params', {})
            res = self._tool('_run_list_types', params)
            self._send_json({'result': res})
        except Exception as e:
            self._send_json({'error': {'message': f"Error executing list_types: {e}", 'code': -32001}}, 500)

    def _handle_types_json(self, data):
        try:
            params = data.get('params', {}) if isinstance(data, dict) else {}
            fam = params.get('family')
            search = (params.get('search') or '').strip().lower()
            if fam:
                fam = fam.strip().upper()
            families = [fam] if fam in OP_TYPES_BY_FAMILY else list(OP_TYPES_BY_FAMILY.keys())
            result = {}
            for f in families:
                items = sorted(list(OP_TYPES_BY_FAMILY.get(f, {}).keys()))
                if search:
                    items = [it for it in items if search in it.lower()]
                result[f] = items
            self._send_json({'result': result})
        except Exception as e:
            self._send_json({'error': {'message': f"Error building types_json: {e}", 'code': -32001}}, 500)


# --- Server control ---
def start_mcp_server(dat_op):
    global server_thread, server_instance, server_running, SERVER_DAT_PATH, PROTECTED_PATHS
    if server_running and server_instance:
        stop_mcp_server()
    if not TDF:
        # Allow mock start for testing
        class MockDatOp: path = '/mock/text1'
        dat_path = MockDatOp().path
    else:
        if not dat_op or not isinstance(dat_op, td.OP):
            print('Error: DAT operator reference not provided or invalid.')
            return False
        dat_path = dat_op.path
    # Remember the DAT that launched the server so we can protect it from deletion
    SERVER_DAT_PATH = _normalize_path(dat_path)
    PROTECTED_PATHS.clear()
    _register_protected_path(SERVER_DAT_PATH)
    extra_protected = os.environ.get('TD_MCP_PROTECTED_PATHS')
    if extra_protected:
        for item in extra_protected.split(','):
            _register_protected_path(item)
    try:
        server_instance = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), TouchDesignerMCPHandler, dat_path)
        print(f'Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT} (DAT: {dat_path}) ...')
        server_thread = threading.Thread(target=server_instance.serve_forever)
        server_thread.daemon = True; server_thread.start(); server_running = True
        print('MCP Server started successfully.')
        return True
    except Exception as e:
        print('Failed to start MCP server:', e)
        server_instance = None; server_thread = None; server_running = False
        return False

def stop_mcp_server():
    global server_thread, server_instance, server_running, SERVER_DAT_PATH, PROTECTED_PATHS
    if not server_running or not server_instance:
        print('MCP Server is not running.'); return
    print('Shutting down MCP server ...')
    try:
        server_instance.shutdown(); server_instance.server_close()
        if server_thread: server_thread.join(timeout=5)
        print('MCP Server stopped.')
    except Exception as e:
        print('Error stopping MCP server:', e)
    finally:
        server_instance = None; server_thread = None; server_running = False
        SERVER_DAT_PATH = None
        PROTECTED_PATHS.clear()
