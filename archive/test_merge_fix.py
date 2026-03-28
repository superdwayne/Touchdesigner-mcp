#!/usr/bin/env python3
"""
Test script to verify that mergeCOMP and other COMP types are properly available
"""

from cursor_td_client import TouchDesignerClient
import time

def test_merge_component():
    """Test creating a merge component."""
    print("=== Testing Merge Component Creation ===")
    
    client = TouchDesignerClient()
    
    # Test creating a merge component
    print("Creating merge component...")
    result = client.create_component("merge", "TestMerge", auto_connect=True)
    print(f"Merge component result: {result}")
    
    # Test creating a null component
    print("Creating null component...")
    result2 = client.create_component("nullcomp", "TestNull", auto_connect=True)
    print(f"Null component result: {result2}")
    
    return result, result2

def test_complex_scene_with_merge():
    """Test creating a complex scene using merge components."""
    print("\n=== Testing Complex Scene with Merge ===")
    
    client = TouchDesignerClient()
    
    # Create scene components
    components = [
        ("sphere", "SceneSphere"),
        ("box", "SceneBox"),
        ("merge", "SceneMerge"),
        ("camera", "SceneCamera"),
        ("render", "SceneRender"),
        ("out", "SceneOutput")
    ]
    
    results = {}
    for i, (comp_type, name) in enumerate(components):
        print(f"{i+1}. Creating {name}...")
        result = client.create_component(comp_type, name, auto_connect=True)
        results[name] = result
        print(f"{name} created: {result}")
        time.sleep(0.5)
    
    # Test Python execution with merge components
    print("7. Testing Python execution with merge...")
    test_code = """
# Test that mergeCOMP is available
try:
    print(f"mergeCOMP available: {mergeCOMP}")
    print(f"nullCOMP available: {nullCOMP}")
    print(f"baseCOMP available: {baseCOMP}")
    
    # Test creating a merge component via Python
    project = op('/')
    test_merge = project.create(mergeCOMP, 'PythonMerge')
    if test_merge:
        print("✓ Successfully created merge component via Python")
    else:
        print("✗ Failed to create merge component via Python")
        
except Exception as e:
    print(f"Error testing merge components: {e}")
"""
    
    python_result = client.execute_python(test_code)
    print(f"Python execution result: {python_result}")
    
    return results

if __name__ == "__main__":
    print("Testing merge component fixes...")
    
    # Test 1: Basic merge component creation
    merge_result, null_result = test_merge_component()
    
    # Test 2: Complex scene with merge
    scene_results = test_complex_scene_with_merge()
    
    print("\n" + "="*50)
    print("MERGE COMPONENT TESTS COMPLETED!")
    print("="*50)
    print("\nCheck TouchDesigner to see:")
    print("✅ Merge components created successfully")
    print("✅ Null components created successfully")
    print("✅ Complex scenes with merge components")
    print("✅ Python execution with mergeCOMP available")
    print("\nThe 'Invalid number or type of arguments' error should be resolved!") 