#!/usr/bin/env python3
"""
Example: Creating a scene with merge components for proper visualization
"""

from cursor_td_client import TouchDesignerClient
import time

def create_merge_scene():
    """Create a scene using merge components for proper visualization."""
    print("🎬 Creating Scene with Merge Components...")
    
    client = TouchDesignerClient()
    
    # Create the scene components
    print("1. Creating sphere...")
    client.create_component("sphere", "MainSphere", auto_connect=True)
    time.sleep(0.5)
    
    print("2. Creating box...")
    client.create_component("box", "MainBox", auto_connect=True)
    time.sleep(0.5)
    
    print("3. Creating camera...")
    client.create_component("camera", "MainCamera", auto_connect=True)
    time.sleep(0.5)
    
    print("4. Creating light...")
    client.create_component("light", "MainLight", auto_connect=True)
    time.sleep(0.5)
    
    print("5. Creating merge component...")
    client.create_component("merge", "SceneMerge", auto_connect=True)
    time.sleep(0.5)
    
    print("6. Creating render...")
    client.create_component("render", "MainRender", auto_connect=True)
    time.sleep(0.5)
    
    print("7. Creating output...")
    client.create_component("out", "MainOutput", auto_connect=True)
    time.sleep(0.5)
    
    # Setup the scene with proper connections
    print("8. Setting up scene connections...")
    setup_code = """
# Get all components
sphere = op('/project1/MainSphere')
box = op('/project1/MainBox')
camera = op('/project1/MainCamera')
light = op('/project1/MainLight')
merge = op('/project1/SceneMerge')
render = op('/project1/MainRender')
output = op('/project1/MainOutput')

print("Setting up scene connections...")

# Position geometry
sphere.par.tx = -2
box.par.tx = 2

# Position camera
camera.par.tx = 0
camera.par.ty = 2
camera.par.tz = 8

# Position light
light.par.tx = 3
light.par.ty = 2
light.par.tz = 2
light.par.intensity = 1.0

# Connect geometry to merge
if sphere and merge:
    try:
        sphere.outputConnectors[0].connect(merge, 0)
        print("✓ Sphere connected to merge")
    except Exception as e:
        print(f"Sphere connection error: {e}")

if box and merge:
    try:
        box.outputConnectors[0].connect(merge, 1)
        print("✓ Box connected to merge")
    except Exception as e:
        print(f"Box connection error: {e}")

# Connect merge to render
if merge and render:
    try:
        merge.outputConnectors[0].connect(render, 0)
        print("✓ Merge connected to render")
    except Exception as e:
        print(f"Merge connection error: {e}")

# Connect camera to render
if camera and render:
    try:
        camera.outputConnectors[0].connect(render, 1)
        print("✓ Camera connected to render")
    except Exception as e:
        print(f"Camera connection error: {e}")

# Connect light to render
if light and render:
    try:
        light.outputConnectors[0].connect(render, 2)
        print("✓ Light connected to render")
    except Exception as e:
        print(f"Light connection error: {e}")

# Connect render to output
if render and output:
    try:
        render.outputConnectors[0].connect(output, 0)
        print("✓ Render connected to output")
    except Exception as e:
        print(f"Render connection error: {e}")

print("🎉 Scene setup complete!")
print("You should now see a complete 3D scene with:")
print("- Sphere and box geometry")
print("- Camera positioned to view the scene")
print("- Light illuminating the geometry")
print("- Merge component combining geometry")
print("- Render component creating the final image")
print("- Output displaying the result")
"""
    
    setup_result = client.execute_python(setup_code)
    print(f"Scene setup: {setup_result}")
    
    print("✅ Merge scene created successfully!")
    print("Check TouchDesigner to see the complete scene with proper connections!")

def create_simple_merge_example():
    """Create a simple example showing merge component usage."""
    print("\n🎬 Creating Simple Merge Example...")
    
    client = TouchDesignerClient()
    
    # Create simple components
    print("1. Creating sphere...")
    client.create_component("sphere", "SimpleSphere", auto_connect=True)
    time.sleep(0.5)
    
    print("2. Creating box...")
    client.create_component("box", "SimpleBox", auto_connect=True)
    time.sleep(0.5)
    
    print("3. Creating merge...")
    client.create_component("merge", "SimpleMerge", auto_connect=True)
    time.sleep(0.5)
    
    print("4. Creating output...")
    client.create_component("out", "SimpleOutput", auto_connect=True)
    time.sleep(0.5)
    
    # Simple connection setup
    print("5. Setting up simple connections...")
    simple_code = """
# Simple merge example
sphere = op('/project1/SimpleSphere')
box = op('/project1/SimpleBox')
merge = op('/project1/SimpleMerge')
output = op('/project1/SimpleOutput')

print("Setting up simple merge connections...")

# Position geometry
sphere.par.tx = -1
box.par.tx = 1

# Connect sphere to merge input 0
if sphere and merge:
    try:
        sphere.outputConnectors[0].connect(merge, 0)
        print("✓ Sphere → Merge (input 0)")
    except Exception as e:
        print(f"Sphere connection error: {e}")

# Connect box to merge input 1
if box and merge:
    try:
        box.outputConnectors[0].connect(merge, 1)
        print("✓ Box → Merge (input 1)")
    except Exception as e:
        print(f"Box connection error: {e}")

# Connect merge to output
if merge and output:
    try:
        merge.outputConnectors[0].connect(output, 0)
        print("✓ Merge → Output")
    except Exception as e:
        print(f"Merge connection error: {e}")

print("🎉 Simple merge example complete!")
print("You should see sphere and box combined in the output.")
"""
    
    simple_result = client.execute_python(simple_code)
    print(f"Simple setup: {simple_result}")
    
    print("✅ Simple merge example created!")

if __name__ == "__main__":
    print("🎬 TouchDesigner Merge Component Examples")
    print("=" * 50)
    
    # Create examples
    create_merge_scene()
    create_simple_merge_example()
    
    print("\n" + "=" * 50)
    print("🎉 All merge examples created successfully!")
    print("=" * 50)
    print("\nWhat you can do now:")
    print("1. Open TouchDesigner and see the merge scenes")
    print("2. Check the Textport for connection logs")
    print("3. Modify the scenes by changing parameters")
    print("4. Create your own merge-based scenes")
    print("5. Use merge components to combine multiple geometry objects")
    
    print("\nKey features demonstrated:")
    print("✅ Merge components for combining geometry")
    print("✅ Proper scene connections with merge")
    print("✅ Camera and lighting setup")
    print("✅ Render pipeline with merge")
    print("✅ Output connections for visualization") 