#!/usr/bin/env python3
"""
Build a face-reactive visual experience in TouchDesigner.
Uses the mp_face scriptCHOP (55 channels of MediaPipe face tracking)
to drive generative visuals in real-time.

Sends commands to TD via the MCP server on port 8053.
"""

import json
import urllib.request
import time

SERVER = "http://localhost:8053/mcp"

def td_exec(code: str, label: str = ""):
    """Execute Python code in TouchDesigner via MCP."""
    data = json.dumps({"method": "execute_python", "params": {"code": code}}).encode()
    req = urllib.request.Request(SERVER, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if label:
                print(f"  [{label}] OK")
            return result
    except Exception as e:
        print(f"  [{label}] ERROR: {e}")
        return None

def td_create(comp_type, name, parent="/project1"):
    """Create a component via MCP create method."""
    data = json.dumps({
        "method": "create",
        "params": {"type": comp_type, "name": name, "parent": parent}
    }).encode()
    req = urllib.request.Request(SERVER, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"  [create {name}] OK")
            return result
    except Exception as e:
        print(f"  [create {name}] ERROR: {e}")
        return None

def td_set(path, parameter, value):
    """Set a parameter via MCP set method."""
    data = json.dumps({
        "method": "set",
        "params": {"path": path, "parameter": parameter, "value": value}
    }).encode()
    req = urllib.request.Request(SERVER, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [set {path}.{parameter}] ERROR: {e}")
        return None


# ============================================================
# STEP 1: Create a container for the reactive visuals
# ============================================================
print("\n=== STEP 1: Create reactive visuals container ===")

td_exec("""
# Clean up any previous reactive_vis container
old = op('/project1/reactive_vis')
if old and old.valid:
    old.destroy()
""", "cleanup")

time.sleep(0.5)

td_exec("""
# Create container for all reactive visual operators
container = op('/project1').create(baseCOMP, 'reactive_vis')
container.nodeX = 600
container.nodeY = -400
container.viewer = True
""", "create container")

time.sleep(0.5)


# ============================================================
# STEP 2: Data selection and processing CHOPs
# ============================================================
print("\n=== STEP 2: Face data selection & processing ===")

td_exec("""
p = op('/project1/reactive_vis')

# Select key expression channels from mp_face
sel_expr = p.create(selectCHOP, 'sel_expressions')
sel_expr.par.chop = op('/project1/mp_face')
sel_expr.par.channames = 'jawOpen mouthSmileLeft mouthSmileRight eyeBlinkLeft eyeBlinkRight browInnerUp browOuterUpLeft browOuterUpRight cheekPuff mouthPucker'
sel_expr.nodeX = 0
sel_expr.nodeY = 0

# Select head rotation channels
sel_head = p.create(selectCHOP, 'sel_head')
sel_head.par.chop = op('/project1/mp_face')
sel_head.par.channames = 'headPitch headYaw headRoll'
sel_head.nodeX = 0
sel_head.nodeY = -150
""", "select channels")

time.sleep(0.3)

td_exec("""
p = op('/project1/reactive_vis')

# Smooth/lag the expression data for fluid visuals
lag_expr = p.create(lagCHOP, 'lag_expressions')
lag_expr.par.lag1 = 0.15
lag_expr.par.lag2 = 0.15
lag_expr.inputConnectors[0].connect(op('/project1/reactive_vis/sel_expressions'))
lag_expr.nodeX = 300
lag_expr.nodeY = 0

# Smooth head rotation
lag_head = p.create(lagCHOP, 'lag_head')
lag_head.par.lag1 = 0.1
lag_head.par.lag2 = 0.1
lag_head.inputConnectors[0].connect(op('/project1/reactive_vis/sel_head'))
lag_head.nodeX = 300
lag_head.nodeY = -150
""", "lag/smooth data")

time.sleep(0.3)

td_exec("""
p = op('/project1/reactive_vis')

# Create a math CHOP to compute overall "activity" level
# Average of all expression magnitudes
math_activity = p.create(mathCHOP, 'activity_level')
math_activity.par.chopop = 1  # Combine channels: average
math_activity.par.integer = 0  # Output as float
math_activity.inputConnectors[0].connect(op('/project1/reactive_vis/lag_expressions'))
math_activity.nodeX = 600
math_activity.nodeY = 0

# Create smile detector: average of left+right smile
sel_smile = p.create(selectCHOP, 'sel_smile')
sel_smile.par.chop = op('/project1/reactive_vis/lag_expressions')
sel_smile.par.channames = 'mouthSmileLeft mouthSmileRight'
sel_smile.nodeX = 600
sel_smile.nodeY = -75

math_smile = p.create(mathCHOP, 'smile_level')
math_smile.par.chopop = 1  # Average
math_smile.inputConnectors[0].connect(sel_smile)
math_smile.nodeX = 900
math_smile.nodeY = -75
""", "activity & smile")


# ============================================================
# STEP 3: Background noise driven by head rotation
# ============================================================
print("\n=== STEP 3: Background visuals ===")

td_exec("""
p = op('/project1/reactive_vis')

# Create animated noise background
bg_noise = p.create(noiseTOP, 'bg_noise')
bg_noise.par.resolutionw = 1920
bg_noise.par.resolutionh = 1080
bg_noise.par.type = 4  # Sparse noise
bg_noise.par.monochrome = False
bg_noise.par.period = 3.0
bg_noise.par.amp = 1.0
bg_noise.par.harmonics = 5
bg_noise.nodeX = 0
bg_noise.nodeY = -400

# Head rotation drives noise offset via expressions
bg_noise.par.offsetx.expr = "op('lag_head')['headYaw'] * 5"
bg_noise.par.offsety.expr = "op('lag_head')['headPitch'] * 5"
bg_noise.par.offsetz.expr = "absTime.seconds * 0.3 + op('lag_head')['headRoll'] * 2"
bg_noise.par.amp.expr = "0.3 + op('activity_level')[0] * 0.7"

# Color the noise with a ramp
bg_ramp = p.create(rampTOP, 'bg_ramp')
bg_ramp.par.resolutionw = 1920
bg_ramp.par.resolutionh = 1080
bg_ramp.par.type = 1  # Circular ramp
bg_ramp.nodeX = 0
bg_ramp.nodeY = -550

# Composite noise with ramp for colored background
bg_comp = p.create(compositeTOP, 'bg_composite')
bg_comp.par.operand = 27  # Multiply
bg_comp.par.resolutionw = 1920
bg_comp.par.resolutionh = 1080
bg_comp.inputConnectors[0].connect(bg_noise)
bg_comp.inputConnectors[1].connect(bg_ramp)
bg_comp.nodeX = 300
bg_comp.nodeY = -400
""", "background noise")

time.sleep(0.3)


# ============================================================
# STEP 4: Central reactive circle/ring driven by mouth
# ============================================================
print("\n=== STEP 4: Central reactive element ===")

td_exec("""
p = op('/project1/reactive_vis')

# Pulsing circle driven by jawOpen
circle1 = p.create(circleTOP, 'mouth_circle')
circle1.par.resolutionw = 1920
circle1.par.resolutionh = 1080
circle1.par.radius.expr = "0.05 + op('lag_expressions')['jawOpen'] * 0.35"
circle1.par.width.expr = "0.01 + op('lag_expressions')['jawOpen'] * 0.02"
circle1.par.bgcolorr = 0
circle1.par.bgcolorg = 0
circle1.par.bgcolorb = 0
circle1.nodeX = 0
circle1.nodeY = -700

# Second ring driven by eyebrows
circle2 = p.create(circleTOP, 'brow_circle')
circle2.par.resolutionw = 1920
circle2.par.resolutionh = 1080
circle2.par.radius.expr = "0.15 + op('lag_expressions')['browInnerUp'] * 0.25"
circle2.par.width.expr = "0.005 + op('lag_expressions')['browInnerUp'] * 0.01"
circle2.par.bgcolorr = 0
circle2.par.bgcolorg = 0
circle2.par.bgcolorb = 0
circle2.nodeX = 0
circle2.nodeY = -850
""", "reactive circles")

time.sleep(0.3)

td_exec("""
p = op('/project1/reactive_vis')

# Color the mouth circle based on smile
mouth_c = op('/project1/reactive_vis/mouth_circle')
mouth_c.par.colorr.expr = "0.2 + op('smile_level')[0] * 0.8"
mouth_c.par.colorg.expr = "0.8 - op('lag_expressions')['jawOpen'] * 0.5"
mouth_c.par.colorb.expr = "1.0 - op('smile_level')[0] * 0.7"

# Color the brow circle
brow_c = op('/project1/reactive_vis/brow_circle')
brow_c.par.colorr.expr = "0.1 + op('lag_expressions')['browInnerUp'] * 0.5"
brow_c.par.colorg.expr = "0.5 + op('lag_expressions')['browOuterUpLeft'] * 0.5"
brow_c.par.colorb.expr = "0.9"
""", "color expressions")


# ============================================================
# STEP 5: Eye blink flash effect
# ============================================================
print("\n=== STEP 5: Eye blink flash ===")

td_exec("""
p = op('/project1/reactive_vis')

# Create a constant TOP that flashes on blink
blink_flash = p.create(constantTOP, 'blink_flash')
blink_flash.par.resolutionw = 1920
blink_flash.par.resolutionh = 1080
blink_flash.par.colorr.expr = "1.0"
blink_flash.par.colorg.expr = "1.0"
blink_flash.par.colorb.expr = "1.0"
blink_flash.par.alpha.expr = "max(op('lag_expressions')['eyeBlinkLeft'], op('lag_expressions')['eyeBlinkRight']) * 0.3"
blink_flash.nodeX = 0
blink_flash.nodeY = -1000
""", "blink flash")


# ============================================================
# STEP 6: Feedback loop for trails
# ============================================================
print("\n=== STEP 6: Feedback trails ===")

td_exec("""
p = op('/project1/reactive_vis')

# Composite circles together
add_circles = p.create(addTOP, 'add_circles')
add_circles.par.resolutionw = 1920
add_circles.par.resolutionh = 1080
add_circles.inputConnectors[0].connect(op('/project1/reactive_vis/mouth_circle'))
add_circles.inputConnectors[1].connect(op('/project1/reactive_vis/brow_circle'))
add_circles.nodeX = 300
add_circles.nodeY = -700

# Add blink flash
add_blink = p.create(addTOP, 'add_blink')
add_blink.par.resolutionw = 1920
add_blink.par.resolutionh = 1080
add_blink.inputConnectors[0].connect(add_circles)
add_blink.inputConnectors[1].connect(op('/project1/reactive_vis/blink_flash'))
add_blink.nodeX = 600
add_blink.nodeY = -700

# Feedback TOP for trails
feedback = p.create(feedbackTOP, 'feedback')
feedback.par.resolutionw = 1920
feedback.par.resolutionh = 1080
feedback.par.top = op('/project1/reactive_vis/feedback_comp')
feedback.nodeX = 300
feedback.nodeY = -900
""", "add circles + feedback")

time.sleep(0.3)

td_exec("""
p = op('/project1/reactive_vis')

# Transform the feedback (slight scale down for zoom trail effect)
fb_transform = p.create(transformTOP, 'fb_transform')
fb_transform.par.resolutionw = 1920
fb_transform.par.resolutionh = 1080
fb_transform.par.sx.expr = "1.005 + op('activity_level')[0] * 0.01"
fb_transform.par.sy.expr = "1.005 + op('activity_level')[0] * 0.01"
fb_transform.par.rotate.expr = "op('lag_head')['headRoll'] * 2"
fb_transform.inputConnectors[0].connect(op('/project1/reactive_vis/feedback'))
fb_transform.nodeX = 600
fb_transform.nodeY = -900

# Level the feedback to fade over time
fb_level = p.create(levelTOP, 'fb_level')
fb_level.par.resolutionw = 1920
fb_level.par.resolutionh = 1080
fb_level.par.opacity.expr = "0.85 + op('activity_level')[0] * 0.1"
fb_level.inputConnectors[0].connect(fb_transform)
fb_level.nodeX = 900
fb_level.nodeY = -900

# Composite feedback with new frame
fb_comp = p.create(compositeTOP, 'feedback_comp')
fb_comp.par.operand = 0  # Over
fb_comp.par.resolutionw = 1920
fb_comp.par.resolutionh = 1080
fb_comp.inputConnectors[0].connect(op('/project1/reactive_vis/add_blink'))
fb_comp.inputConnectors[1].connect(fb_level)
fb_comp.nodeX = 900
fb_comp.nodeY = -700
""", "feedback loop")


# ============================================================
# STEP 7: Final composite with background
# ============================================================
print("\n=== STEP 7: Final composite & post-processing ===")

time.sleep(0.3)

td_exec("""
p = op('/project1/reactive_vis')

# Layer foreground (circles+feedback) over background
final_comp = p.create(compositeTOP, 'final_comp')
final_comp.par.operand = 31  # Screen blend
final_comp.par.resolutionw = 1920
final_comp.par.resolutionh = 1080
final_comp.inputConnectors[0].connect(op('/project1/reactive_vis/feedback_comp'))
final_comp.inputConnectors[1].connect(op('/project1/reactive_vis/bg_composite'))
final_comp.nodeX = 1200
final_comp.nodeY = -550

# Bloom / glow pass
bloom_thresh = p.create(thresholdTOP, 'bloom_thresh')
bloom_thresh.par.resolutionw = 1920
bloom_thresh.par.resolutionh = 1080
bloom_thresh.par.threshold = 0.6
bloom_thresh.inputConnectors[0].connect(final_comp)
bloom_thresh.nodeX = 1500
bloom_thresh.nodeY = -400

bloom_blur = p.create(blurTOP, 'bloom_blur')
bloom_blur.par.resolutionw = 1920
bloom_blur.par.resolutionh = 1080
bloom_blur.par.size.expr = "5 + op('activity_level')[0] * 20"
bloom_blur.inputConnectors[0].connect(bloom_thresh)
bloom_blur.nodeX = 1500
bloom_blur.nodeY = -550

bloom_add = p.create(addTOP, 'bloom_add')
bloom_add.par.resolutionw = 1920
bloom_add.par.resolutionh = 1080
bloom_add.inputConnectors[0].connect(final_comp)
bloom_add.inputConnectors[1].connect(bloom_blur)
bloom_add.nodeX = 1500
bloom_add.nodeY = -700
""", "final composite + bloom")

time.sleep(0.3)

td_exec("""
p = op('/project1/reactive_vis')

# Color grading - shift hue with head rotation
color_grade = p.create(hsvadjustTOP, 'color_grade')
color_grade.par.resolutionw = 1920
color_grade.par.resolutionh = 1080
color_grade.par.hueoffset.expr = "op('lag_head')['headYaw'] * 0.3"
color_grade.par.saturationmult.expr = "0.8 + op('smile_level')[0] * 0.5"
color_grade.par.valuemult.expr = "0.9 + op('activity_level')[0] * 0.2"
color_grade.inputConnectors[0].connect(op('/project1/reactive_vis/bloom_add'))
color_grade.nodeX = 1800
color_grade.nodeY = -550

# Output
out = p.create(outTOP, 'out1')
out.par.resolutionw = 1920
out.par.resolutionh = 1080
out.inputConnectors[0].connect(color_grade)
out.nodeX = 2100
out.nodeY = -550
""", "color grading + output")


# ============================================================
# STEP 8: Open viewer
# ============================================================
print("\n=== STEP 8: Activate viewer ===")

td_exec("""
# Set the output TOP as the viewer
out = op('/project1/reactive_vis/out1')
if out and out.valid:
    out.viewer = True

# Also set the container to show the output
container = op('/project1/reactive_vis')
if container and container.valid:
    container.viewer = True
""", "activate viewer")


print("\n" + "=" * 60)
print("FACE-REACTIVE VISUALS BUILT SUCCESSFULLY!")
print("=" * 60)
print("""
Network created in /project1/reactive_vis:

DATA FLOW:
  mp_face (55ch) → select → lag → activity/smile detectors

VISUAL LAYERS:
  1. Background noise    ← head rotation drives offset + color
  2. Mouth circle/ring   ← jawOpen drives radius, smile drives color
  3. Brow circle/ring    ← browInnerUp drives size
  4. Blink flash         ← eyeBlink triggers white flash
  5. Feedback trails     ← zoom + rotate based on activity + head roll

POST-PROCESSING:
  bloom (activity-driven) → hue shift (head yaw) → saturation (smile)

HOW TO VIEW:
  - Click on /project1/reactive_vis in TD to see the container
  - Or click on reactive_vis/out1 to see the final output
  - Move your face to drive the visuals!

FACE MAPPINGS:
  jawOpen        → circle radius + color shift
  smile          → warm colors + saturation boost
  eyeBlink       → white flash overlay
  browRaise      → outer ring size
  headYaw        → noise X offset + hue shift
  headPitch      → noise Y offset
  headRoll       → feedback rotation
  overall activity → bloom intensity + noise amplitude + trail persistence
""")
