#!/usr/bin/env python3
"""
Test script for speed metrics implementation.
Validates the speed calculation fix and metrics integration.
"""

import sys
import time
import numpy as np
from object_tracker import TrackedObject
from prometheus_metrics import MetricsConfig, TrafficMetrics

def test_speed_calculation():
    """Test the fixed speed calculation method."""
    print("🧪 Testing Speed Calculation Fix...")
    
    # Create a test tracked object
    obj = TrackedObject(1, (100, 100), (95, 95, 10, 10), 100)
    
    # Add some position history with known distances and times
    test_positions = [
        (100, 100),  # Start position
        (110, 100),  # Move 10 pixels right
        (120, 100),  # Move another 10 pixels right
        (130, 105),  # Move 10 pixels right, 5 pixels down
    ]
    
    test_times = [
        1000.0,      # Start time
        1000.1,      # 0.1 seconds later
        1000.2,      # 0.1 seconds later  
        1000.3,      # 0.1 seconds later
    ]
    
    # Manually set the position and timestamp history
    obj.positions = test_positions
    obj.timestamps = test_times
    
    # Test speed calculation
    speed = obj.get_speed_pixels_per_second()
    
    # Expected: distance from (120,100) to (130,105) = sqrt(10^2 + 5^2) = sqrt(125) ≈ 11.18
    # Time difference: 0.1 seconds
    # Expected speed: 11.18 / 0.1 = 111.8 px/s
    expected_speed = np.sqrt(10**2 + 5**2) / 0.1
    
    print(f"  📏 Distance calculation: sqrt(10² + 5²) = {np.sqrt(10**2 + 5**2):.2f} pixels")
    print(f"  ⏱️  Time difference: 0.1 seconds")
    print(f"  🎯 Expected speed: {expected_speed:.1f} px/s")
    print(f"  📊 Calculated speed: {speed:.1f} px/s")
    
    if abs(speed - expected_speed) < 0.1:
        print("  ✅ Speed calculation is CORRECT!")
        return True
    else:
        print("  ❌ Speed calculation is INCORRECT!")
        return False

def test_metrics_integration():
    """Test the metrics integration."""
    print("\n🧪 Testing Metrics Integration...")
    
    try:
        # Create metrics config for testing
        config = MetricsConfig(
            enabled=True,
            app_name="test-speed-metrics",
            app_instance="test",
            http_server_enabled=False,  # Don't start HTTP server for test
            debug=True
        )
        
        # Create metrics instance
        metrics = TrafficMetrics(config)
        
        # Test recording vehicle speed
        print("  📝 Recording test speed metrics...")
        metrics.record_vehicle_speed("left", 45.5)
        metrics.record_vehicle_speed("right", 67.2)
        
        # Test invalid speeds (should be filtered)
        print("  🚫 Testing invalid speed filtering...")
        metrics.record_vehicle_speed("left", -10.0)  # Negative speed
        metrics.record_vehicle_speed("right", 250.0)  # Too high speed
        
        # Check if speed history was recorded
        left_history = metrics._speed_history.get("left", [])
        right_history = metrics._speed_history.get("right", [])
        
        print(f"  📈 Left speed history: {len(left_history)} entries")
        print(f"  📈 Right speed history: {len(right_history)} entries")
        
        if len(left_history) == 1 and len(right_history) == 1:
            print("  ✅ Speed metrics recording is WORKING!")
            print(f"     Left: {left_history[0][1]:.1f} px/s")
            print(f"     Right: {right_history[0][1]:.1f} px/s")
            return True
        else:
            print("  ❌ Speed metrics recording FAILED!")
            return False
            
    except Exception as e:
        print(f"  ❌ Metrics integration test FAILED: {e}")
        return False

def test_speed_validation():
    """Test speed validation ranges."""
    print("\n🧪 Testing Speed Validation...")
    
    config = MetricsConfig(
        enabled=True,
        app_name="test-speed-validation",
        app_instance="test",
        http_server_enabled=False,
        debug=True
    )
    
    metrics = TrafficMetrics(config)
    
    test_cases = [
        (25.5, True, "Normal speed"),
        (75.0, True, "Fast speed"),
        (-5.0, False, "Negative speed"),
        (250.0, False, "Unrealistic high speed"),
        (0.0, False, "Zero speed"),
        (150.0, True, "High but valid speed"),
    ]
    
    passed = 0
    for speed, should_pass, description in test_cases:
        initial_count = len(metrics._speed_history.get("left", []))
        metrics.record_vehicle_speed("left", speed)
        final_count = len(metrics._speed_history.get("left", []))
        
        recorded = final_count > initial_count
        
        if recorded == should_pass:
            print(f"  ✅ {description}: {speed} px/s - {'Recorded' if recorded else 'Filtered'}")
            passed += 1
        else:
            print(f"  ❌ {description}: {speed} px/s - Expected {'recorded' if should_pass else 'filtered'}, got {'recorded' if recorded else 'filtered'}")
    
    print(f"  📊 Validation tests: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)

def main():
    """Run all speed metrics tests."""
    print("🚀 Speed Metrics Implementation Test Suite")
    print("=" * 50)
    
    tests = [
        ("Speed Calculation Fix", test_speed_calculation),
        ("Metrics Integration", test_metrics_integration),
        ("Speed Validation", test_speed_validation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests PASSED! Speed metrics implementation is ready.")
        return 0
    else:
        print("⚠️  Some tests FAILED. Please review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
