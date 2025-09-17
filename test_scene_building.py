#!/usr/bin/env python3
"""
Test script to demonstrate enhanced scene building with intelligent auto-connections
"""

from cursor_td_client import TouchDesignerClient
import time

def test_scene_building():
    """Test building a complete scene with intelligent auto-connections."""
    print("=== Testing Enhanced Scene Building ===")
    
    client = TouchDesignerClient()
    
    # Build a complete 3D scene with auto-connections
    print("Building a 3D scene with intelligent connections...")
    
    # 1. Create geometry
    print("1. Creating geometry...")
    sphere_result = client.create_component("sphere", "MySphere", auto_connect=True)
    print(f"Sphere created: {sphere_result}")
    
    time.sleep(0.5)  # Allow TD to process
    
    # 2. Create material
    print("2. Creating material...")
    material_result = client.create_component("phong", "MyMaterial", auto_connect=True)
    print(f"Material created: {material_result}")
    
    time.sleep(0.5)
    
    # 3. Create camera
    print("3. Creating camera...")
    camera_result = client.create_component("camera", "MyCamera", auto_connect=True)
    print(f"Camera created: {camera_result}")
    
    time.sleep(0.5)
    
    # 4. Create light
    print("4. Creating light...")
    light_result = client.create_component("light", "MyLight", auto_connect=True)
    print(f"Light created: {light_result}")
    
    time.sleep(0.5)
    
    # 5. Create render
    print("5. Creating render...")
    render_result = client.create_component("render", "MyRender", auto_connect=True)
    print(f"Render created: {render_result}")
    
    return {
        "sphere": sphere_result,
        "material": material_result,
        "camera": camera_result,
        "light": light_result,
        "render": render_result
    }

def test_image_processing_chain():
    """Test building an image processing chain with auto-connections."""
    print("\n=== Testing Image Processing Chain ===")
    
    client = TouchDesignerClient()
    
    print("Building image processing chain...")
    
    # 1. Create source image
    print("1. Creating source image...")
    circle_result = client.create_component("circle", "SourceImage", auto_connect=True)
    print(f"Circle created: {circle_result}")
    
    time.sleep(0.5)
    
    # 2. Create blur effect
    print("2. Creating blur effect...")
    blur_result = client.create_component("blur", "BlurEffect", auto_connect=True)
    print(f"Blur created: {blur_result}")
    
    time.sleep(0.5)
    
    # 3. Create level adjustment
    print("3. Creating level adjustment...")
    level_result = client.create_component("level", "LevelAdjust", auto_connect=True)
    print(f"Level created: {level_result}")
    
    time.sleep(0.5)
    
    # 4. Create output
    print("4. Creating output...")
    out_result = client.create_component("out", "FinalOutput", auto_connect=True)
    print(f"Output created: {out_result}")
    
    return {
        "source": circle_result,
        "blur": blur_result,
        "level": level_result,
        "output": out_result
    }

def test_audio_processing_chain():
    """Test building an audio processing chain with auto-connections."""
    print("\n=== Testing Audio Processing Chain ===")
    
    client = TouchDesignerClient()
    
    print("Building audio processing chain...")
    
    # 1. Create audio source
    print("1. Creating audio source...")
    noise_result = client.create_component("noisechop", "AudioSource", auto_connect=True)
    print(f"Noise CHOP created: {noise_result}")
    
    time.sleep(0.5)
    
    # 2. Create filter
    print("2. Creating filter...")
    filter_result = client.create_component("filter", "AudioFilter", auto_connect=True)
    print(f"Filter created: {filter_result}")
    
    time.sleep(0.5)
    
    # 3. Create math operation
    print("3. Creating math operation...")
    math_result = client.create_component("math", "AudioMath", auto_connect=True)
    print(f"Math CHOP created: {math_result}")
    
    time.sleep(0.5)
    
    # 4. Create output
    print("4. Creating output...")
    out_result = client.create_component("outchop", "AudioOutput", auto_connect=True)
    print(f"Output CHOP created: {out_result}")
    
    return {
        "source": noise_result,
        "filter": filter_result,
        "math": math_result,
        "output": out_result
    }

if __name__ == "__main__":
    print("Testing enhanced scene building with intelligent auto-connections...")
    
    # Test 1: 3D Scene Building
    scene_results = test_scene_building()
    
    # Test 2: Image Processing Chain
    image_results = test_image_processing_chain()
    
    # Test 3: Audio Processing Chain
    audio_results = test_audio_processing_chain()
    
    print("\n" + "="*50)
    print("ENHANCED SCENE BUILDING TESTS COMPLETED!")
    print("="*50)
    print("\nCheck TouchDesigner to see:")
    print("✅ Nodes automatically positioned with proper spacing")
    print("✅ Intelligent connections between relevant nodes")
    print("✅ Complete workflow chains built automatically")
    print("✅ Scene-specific enhancements (camera->geometry, light->geometry, etc.)")
    print("\nLook for detailed connection logs in TouchDesigner Textport!") 