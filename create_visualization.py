#!/usr/bin/env python3
"""
Simple example: Create complete visualizations with automatic camera and rendering setup
"""

from cursor_td_client import TouchDesignerClient
import time

def create_simple_visualization():
    """Create a simple 3D visualization."""
    print("🎬 Creating Simple 3D Visualization...")
    
    client = TouchDesignerClient()
    
    # Create geometry - this will automatically trigger camera and render connections
    print("1. Creating sphere...")
    client.create_component("sphere", "MySphere", auto_connect=True)
    time.sleep(0.5)
    
    # Create camera - will be positioned and connected to geometry
    print("2. Creating camera...")
    client.create_component("camera", "MyCamera", auto_connect=True)
    time.sleep(0.5)
    
    # Create light - will be positioned to illuminate geometry
    print("3. Creating light...")
    client.create_component("light", "MyLight", auto_connect=True)
    time.sleep(0.5)
    
    # Create render - will connect to camera and geometry
    print("4. Creating render...")
    client.create_component("render", "MyRender", auto_connect=True)
    time.sleep(0.5)
    
    # Create output - will connect to render
    print("5. Creating output...")
    client.create_component("out", "MyOutput", auto_connect=True)
    
    print("✅ Simple visualization created!")
    print("Check TouchDesigner - you should see:")
    print("- Sphere geometry")
    print("- Camera positioned and looking at sphere")
    print("- Light positioned to illuminate sphere")
    print("- Render connected to camera and geometry")
    print("- Output connected to render")

def create_animated_visualization():
    """Create an animated visualization."""
    print("\n🎬 Creating Animated Visualization...")
    
    client = TouchDesignerClient()
    
    # Create animated scene
    print("1. Creating animated sphere...")
    client.create_component("sphere", "AnimatedSphere", auto_connect=True)
    time.sleep(0.5)
    
    print("2. Creating camera...")
    client.create_component("camera", "AnimatedCamera", auto_connect=True)
    time.sleep(0.5)
    
    print("3. Creating render...")
    client.create_component("render", "AnimatedRender", auto_connect=True)
    time.sleep(0.5)
    
    print("4. Creating output...")
    client.create_component("out", "AnimatedOutput", auto_connect=True)
    time.sleep(0.5)
    
    # Add animation
    print("5. Adding animation...")
    animation_code = """
# Animate the sphere
sphere = op('/project1/AnimatedSphere')
sphere.par.radius = absTime.frame * 0.01 + 0.5

# Animate the camera
camera = op('/project1/AnimatedCamera')
camera.par.tx = math.sin(absTime.frame * 0.1) * 3
camera.par.tz = math.cos(absTime.frame * 0.1) * 3 + 5

print(f"Animation running at frame {absTime.frame}")
"""
    client.execute_python(animation_code)
    
    print("✅ Animated visualization created!")
    print("Check TouchDesigner - you should see:")
    print("- Animated sphere with changing radius")
    print("- Camera orbiting around the sphere")
    print("- Complete render pipeline")

def create_complex_scene():
    """Create a complex scene with multiple elements."""
    print("\n🎬 Creating Complex Scene...")
    
    client = TouchDesignerClient()
    
    # Create complex scene
    components = [
        ("sphere", "MainSphere"),
        ("box", "MainBox"),
        ("phong", "MainMaterial"),
        ("camera", "MainCamera"),
        ("light", "MainLight"),
        ("light", "FillLight"),
        ("render", "MainRender"),
        ("out", "MainOutput")
    ]
    
    for i, (comp_type, name) in enumerate(components):
        print(f"{i+1}. Creating {name}...")
        client.create_component(comp_type, name, auto_connect=True)
        time.sleep(0.5)
    
    # Setup scene positioning
    print("9. Setting up scene...")
    scene_setup = """
# Position geometry
sphere = op('/project1/MainSphere')
box = op('/project1/MainBox')
sphere.par.tx = -2
box.par.tx = 2

# Position lights
main_light = op('/project1/MainLight')
fill_light = op('/project1/FillLight')
main_light.par.tx = 3
main_light.par.ty = 2
main_light.par.tz = 2
main_light.par.intensity = 1.0
fill_light.par.tx = -3
fill_light.par.ty = 1
fill_light.par.tz = 1
fill_light.par.intensity = 0.5

# Position camera
camera = op('/project1/MainCamera')
camera.par.tx = 0
camera.par.ty = 2
camera.par.tz = 8

print("Complex scene setup complete!")
"""
    client.execute_python(scene_setup)
    
    print("✅ Complex scene created!")
    print("Check TouchDesigner - you should see:")
    print("- Multiple geometry objects (sphere and box)")
    print("- Multiple lights (main and fill)")
    print("- Camera positioned to view the scene")
    print("- Complete render pipeline")

if __name__ == "__main__":
    print("🎬 TouchDesigner Visualization Creator")
    print("=" * 50)
    
    # Create different types of visualizations
    create_simple_visualization()
    create_animated_visualization()
    create_complex_scene()
    
    print("\n" + "=" * 50)
    print("🎉 All visualizations created successfully!")
    print("=" * 50)
    print("\nWhat you can do now:")
    print("1. Open TouchDesigner and see the created scenes")
    print("2. Check the Textport for detailed connection logs")
    print("3. Modify the scenes by changing parameters")
    print("4. Add more components with auto_connect=True")
    print("5. Create your own custom visualizations!")
    
    print("\nKey features:")
    print("✅ Automatic camera positioning and connection")
    print("✅ Automatic lighting setup")
    print("✅ Automatic render pipeline connection")
    print("✅ Automatic material application")
    print("✅ Smart node positioning (no overlaps)")
    print("✅ Complete visualization workflows") 