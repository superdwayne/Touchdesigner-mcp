#!/usr/bin/env python3
"""
Test script to demonstrate complete visualization setup with automatic camera, lighting, and rendering
"""

from cursor_td_client import TouchDesignerClient
import time

def test_complete_3d_visualization():
    """Test creating a complete 3D visualization with automatic setup."""
    print("=== Testing Complete 3D Visualization ===")
    
    client = TouchDesignerClient()
    
    # Create a complete 3D scene with automatic visualization setup
    print("Creating complete 3D visualization...")
    
    # 1. Create geometry (this will trigger camera and render connections)
    print("1. Creating geometry...")
    sphere_result = client.create_component("sphere", "MySphere", auto_connect=True)
    print(f"Sphere created: {sphere_result}")
    
    time.sleep(0.5)  # Allow TD to process and set up camera connections
    
    # 2. Create material (will be applied to geometry)
    print("2. Creating material...")
    material_result = client.create_component("phong", "MyMaterial", auto_connect=True)
    print(f"Material created: {material_result}")
    
    time.sleep(0.5)
    
    # 3. Create camera (will be positioned and connected to geometry)
    print("3. Creating camera...")
    camera_result = client.create_component("camera", "MyCamera", auto_connect=True)
    print(f"Camera created: {camera_result}")
    
    time.sleep(0.5)
    
    # 4. Create light (will be positioned to illuminate geometry)
    print("4. Creating light...")
    light_result = client.create_component("light", "MyLight", auto_connect=True)
    print(f"Light created: {light_result}")
    
    time.sleep(0.5)
    
    # 5. Create render (will connect to camera and geometry)
    print("5. Creating render...")
    render_result = client.create_component("render", "MyRender", auto_connect=True)
    print(f"Render created: {render_result}")
    
    time.sleep(0.5)
    
    # 6. Create output (will connect to render)
    print("6. Creating output...")
    out_result = client.create_component("out", "FinalOutput", auto_connect=True)
    print(f"Output created: {out_result}")
    
    return {
        "sphere": sphere_result,
        "material": material_result,
        "camera": camera_result,
        "light": light_result,
        "render": render_result,
        "output": out_result
    }

def test_multiple_geometry_visualization():
    """Test creating visualization with multiple geometry objects."""
    print("\n=== Testing Multiple Geometry Visualization ===")
    
    client = TouchDesignerClient()
    
    print("Creating visualization with multiple geometry objects...")
    
    # Create multiple geometry objects
    geometries = [
        ("sphere", "Sphere1"),
        ("box", "Box1"),
        ("grid", "Grid1")
    ]
    
    results = {}
    for i, (geo_type, name) in enumerate(geometries):
        print(f"{i+1}. Creating {geo_type}...")
        result = client.create_component(geo_type, name, auto_connect=True)
        results[name] = result
        print(f"{geo_type} created: {result}")
        time.sleep(0.5)
    
    # Create camera and render for the scene
    print("4. Creating camera...")
    camera_result = client.create_component("camera", "SceneCamera", auto_connect=True)
    results["camera"] = camera_result
    
    time.sleep(0.5)
    
    print("5. Creating render...")
    render_result = client.create_component("render", "SceneRender", auto_connect=True)
    results["render"] = render_result
    
    time.sleep(0.5)
    
    print("6. Creating output...")
    out_result = client.create_component("out", "SceneOutput", auto_connect=True)
    results["output"] = out_result
    
    return results

def test_animated_visualization():
    """Test creating an animated visualization."""
    print("\n=== Testing Animated Visualization ===")
    
    client = TouchDesignerClient()
    
    print("Creating animated visualization...")
    
    # 1. Create animated geometry
    print("1. Creating animated sphere...")
    sphere_result = client.create_component("sphere", "AnimatedSphere", auto_connect=True)
    print(f"Animated sphere created: {sphere_result}")
    
    time.sleep(0.5)
    
    # 2. Create camera
    print("2. Creating camera...")
    camera_result = client.create_component("camera", "AnimatedCamera", auto_connect=True)
    print(f"Camera created: {camera_result}")
    
    time.sleep(0.5)
    
    # 3. Create render
    print("3. Creating render...")
    render_result = client.create_component("render", "AnimatedRender", auto_connect=True)
    print(f"Render created: {render_result}")
    
    time.sleep(0.5)
    
    # 4. Create output
    print("4. Creating output...")
    out_result = client.create_component("out", "AnimatedOutput", auto_connect=True)
    print(f"Output created: {out_result}")
    
    time.sleep(0.5)
    
    # 5. Add animation via Python execution
    print("5. Adding animation...")
    animation_code = """
# Add animation to the sphere
sphere = op('/project1/AnimatedSphere')
sphere.par.radius = absTime.frame * 0.01 + 0.5

# Add camera movement
camera = op('/project1/AnimatedCamera')
camera.par.tx = math.sin(absTime.frame * 0.1) * 3
camera.par.tz = math.cos(absTime.frame * 0.1) * 3 + 5

print(f"Animation frame: {absTime.frame}")
"""
    
    animation_result = client.execute_python(animation_code)
    print(f"Animation added: {animation_result}")
    
    return {
        "sphere": sphere_result,
        "camera": camera_result,
        "render": render_result,
        "output": out_result,
        "animation": animation_result
    }

def test_complex_scene_visualization():
    """Test creating a complex scene with multiple elements."""
    print("\n=== Testing Complex Scene Visualization ===")
    
    client = TouchDesignerClient()
    
    print("Creating complex scene visualization...")
    
    # Create complex scene components
    scene_components = [
        ("sphere", "MainSphere"),
        ("box", "MainBox"),
        ("phong", "MainMaterial"),
        ("camera", "MainCamera"),
        ("light", "MainLight"),
        ("light", "FillLight"),
        ("render", "MainRender"),
        ("out", "MainOutput")
    ]
    
    results = {}
    for i, (comp_type, name) in enumerate(scene_components):
        print(f"{i+1}. Creating {name}...")
        result = client.create_component(comp_type, name, auto_connect=True)
        results[name] = result
        print(f"{name} created: {result}")
        time.sleep(0.5)
    
    # Add scene setup via Python
    print("9. Setting up complex scene...")
    scene_setup = """
# Setup complex scene
sphere = op('/project1/MainSphere')
box = op('/project1/MainBox')
camera = op('/project1/MainCamera')
main_light = op('/project1/MainLight')
fill_light = op('/project1/FillLight')

# Position geometry
sphere.par.tx = -2
box.par.tx = 2

# Position lights
main_light.par.tx = 3
main_light.par.ty = 2
main_light.par.tz = 2
main_light.par.intensity = 1.0

fill_light.par.tx = -3
fill_light.par.ty = 1
fill_light.par.tz = 1
fill_light.par.intensity = 0.5

# Position camera
camera.par.tx = 0
camera.par.ty = 2
camera.par.tz = 8

print("Complex scene setup complete!")
"""
    
    setup_result = client.execute_python(scene_setup)
    print(f"Scene setup: {setup_result}")
    
    return results

if __name__ == "__main__":
    print("Testing enhanced visualization capabilities...")
    
    # Test 1: Complete 3D Visualization
    scene_results = test_complete_3d_visualization()
    
    # Test 2: Multiple Geometry Visualization
    multi_results = test_multiple_geometry_visualization()
    
    # Test 3: Animated Visualization
    anim_results = test_animated_visualization()
    
    # Test 4: Complex Scene Visualization
    complex_results = test_complex_scene_visualization()
    
    print("\n" + "="*60)
    print("ENHANCED VISUALIZATION TESTS COMPLETED!")
    print("="*60)
    print("\nCheck TouchDesigner to see:")
    print("✅ Complete 3D scenes with automatic camera setup")
    print("✅ Multiple geometry objects properly connected")
    print("✅ Automatic lighting and material application")
    print("✅ Render components connected to camera and geometry")
    print("✅ Output TOPs connected to render pipeline")
    print("✅ Animated scenes with camera movement")
    print("✅ Complex scenes with multiple lights and geometry")
    print("\nLook for detailed connection logs in TouchDesigner Textport!")
    print("Each scene should have:")
    print("- Camera positioned and looking at geometry")
    print("- Lights positioned to illuminate geometry")
    print("- Render connected to camera and geometry")
    print("- Output connected to render")
    print("- Materials applied to geometry") 