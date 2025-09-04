# RFD-012: Speed Metrics Implementation for Traffic Detection System

**Authors:** Wentao Jiang, Augment Agent  
**Date:** 2025-09-04  
**Status:** Proposed  
**Enhances:** RFD-001 (Motion Detection), RFD-002 (Traffic Counting), RFD-004 (Prometheus Monitoring)

## Summary

This RFD proposes the implementation of vehicle speed metrics for the Bay Bridge traffic detection system. The proposal leverages existing object tracking infrastructure to capture speed data in pixels per second for both traffic directions, integrate with the current Prometheus metrics system, and display speed analytics in Grafana dashboards.

## Background and Motivation

### Current System Capabilities

The motion-based traffic detection system (RFD-001, RFD-002) already provides:
- ✅ **Object Tracking**: `TrackedObject` instances with position history and timestamps
- ✅ **Speed Calculation**: `get_speed_pixels_per_second()` method (needs fixing)
- ✅ **Traffic Counting**: Directional vehicle counting with `TrafficCounter`
- ✅ **Metrics Infrastructure**: Prometheus metrics collection and Grafana Cloud integration
- ✅ **Real-time Display**: Speed already shown on video feed for debugging

### Business Value

Speed metrics will provide:
1. **Traffic Flow Analysis**: Understand congestion patterns and traffic efficiency
2. **Incident Detection**: Identify unusual speed patterns indicating incidents
3. **Performance Monitoring**: Track traffic flow quality over time
4. **Directional Insights**: Compare speed patterns between left and right traffic
5. **Historical Analysis**: Long-term speed trend analysis via Grafana Cloud storage

### Technical Readiness

The infrastructure is already in place:
- Speed calculation exists but needs correction
- Metrics collection system operational
- Traffic counting integration points available
- Grafana dashboard ready for new panels

## Technical Implementation

### Speed Calculation Fix

#### Current Issue
The existing `get_speed_pixels_per_second()` method has a calculation error:

```python
# INCORRECT: Uses velocity (pixels per frame) with time difference
distance = np.sqrt(self.velocity[0]**2 + self.velocity[1]**2)
return distance / time_diff
```

#### Proposed Fix
```python
def get_speed_pixels_per_second(self):
    """Calculate speed in pixels per second using actual distance."""
    if len(self.positions) >= 2 and len(self.timestamps) >= 2:
        # Calculate actual distance between last two positions
        pos1 = self.positions[-2]
        pos2 = self.positions[-1]
        distance = np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
        
        time_diff = self.timestamps[-1] - self.timestamps[-2]
        if time_diff > 0:
            return distance / time_diff
    return 0.0
```

### Prometheus Metrics Design

#### Priority 1: Essential Speed Metrics

**1. Current Speed (Gauge)**
```
traffic_speed_current_pixels_per_second{direction="left|right"}
- Updated: When vehicle crosses counting line
- Value: Individual vehicle speed at crossing moment
- Use: Real-time speed monitoring
```

**2. Average Speed (Gauge)**
```
traffic_speed_average_pixels_per_second{direction="left|right", window="1min|5min|15min"}
- Calculated: Every 30 seconds via background thread
- Value: Rolling average over specified time window
- Use: Traffic flow trend analysis
```

#### Data Integration Point

Speed metrics will be captured in `TrafficCounter.update()` when vehicles cross counting lines:

```python
# Integration point (existing code at lines 493-501 in object_tracker.py)
if obj.direction in ['left', 'right']:
    self.counts[obj.direction] += 1
    
    # Existing metrics
    metrics = get_metrics()
    if metrics:
        metrics.record_vehicle_count(obj.direction)
        
        # NEW: Speed metrics recording
        speed = obj.get_speed_pixels_per_second()
        if speed > 0:  # Only record valid speeds
            metrics.record_vehicle_speed(obj.direction, speed)
            print(f"  🏃 Speed: {speed:.1f} px/s")
```

### Data Flow Architecture

```
TrackedObject.get_speed_pixels_per_second()
    ↓
TrafficCounter.update() (when crossing line)
    ↓
prometheus_metrics.record_vehicle_speed()
    ↓
Prometheus HTTP endpoint (:9091/metrics)
    ↓
Local Prometheus scraping (:9090)
    ↓
Grafana Cloud (remote write)
    ↓
Grafana Dashboard visualization
```

## Grafana Dashboard Design

### Panel 1: Real-Time Speed Gauges

**Type**: Gauge panel with dual gauges  
**Query**: `traffic_speed_current_pixels_per_second`  
**Layout**: Side-by-side gauges for left and right directions  
**Thresholds**:
- Green: 0-50 px/s (Normal traffic)
- Yellow: 50-100 px/s (Fast traffic)
- Red: >100 px/s (Very fast/possible outliers)

**Visual Design**:
```
┌─────────────────────────────────────┐
│        Current Traffic Speed        │
├─────────────────┬───────────────────┤
│   LEFT BOUND    │   RIGHT BOUND     │
│   [●●●●○○○○○○]   │   [●●●●●●○○○○]     │
│    45 px/s      │    67 px/s        │
│   (Normal)      │   (Fast)          │
└─────────────────┴───────────────────┘
```

### Panel 2: Speed Trends Over Time

**Type**: Time series panel  
**Query**: `traffic_speed_average_pixels_per_second{window="5min"}`  
**Features**:
- Dual-line chart (left vs right direction)
- 24-hour time range with 5-minute resolution
- Direction-based color coding
- Tooltip showing exact values

**Use Cases**:
- Identify peak traffic periods
- Compare directional speed differences
- Detect speed pattern changes over time

### Panel 3: Speed vs Traffic Volume Correlation

**Type**: Stat panel with calculated metrics  
**Queries**: 
- Speed: `traffic_speed_average_pixels_per_second{window="5min"}`
- Volume: `rate(traffic_vehicles_total[5m]) * 60`
- Ratio: Custom calculation

**Display**: Speed/Volume ratio indicating traffic efficiency  
**Interpretation**:
- High ratio: Fast traffic, low volume (free flow)
- Low ratio: Slow traffic, high volume (congestion)

### Panel 4: Speed Statistics Summary

**Type**: Table panel  
**Metrics**: Current, 5-min average, max observed  
**Breakdown**: By direction and combined totals  
**Refresh**: Every 30 seconds

## Implementation Plan

### Phase 1: Core Speed Metrics (Estimated: 2-3 hours)

1. **Fix Speed Calculation** (30 minutes)
   - Correct `get_speed_pixels_per_second()` method
   - Test with live traffic data
   - Validate speed values are reasonable

2. **Add Prometheus Metrics** (45 minutes)
   - Add speed metrics to `prometheus_metrics.py`
   - Implement `record_vehicle_speed()` method
   - Add background thread for average calculations

3. **Integrate Speed Recording** (30 minutes)
   - Modify `TrafficCounter.update()` to record speeds
   - Add debug output for speed values
   - Test integration with existing traffic counting

4. **Testing and Validation** (45 minutes)
   - Test with live Bay Bridge traffic
   - Verify metrics appear in Prometheus
   - Validate data flow to Grafana Cloud

### Phase 2: Grafana Dashboard (Estimated: 1-2 hours)

1. **Create Speed Panels** (60 minutes)
   - Real-time speed gauges
   - Speed trends time series
   - Speed vs volume correlation
   - Statistics summary table

2. **Dashboard Integration** (30 minutes)
   - Add panels to existing dashboard
   - Configure proper layouts and sizing
   - Set appropriate refresh intervals

## Performance and Scalability

### Data Volume Impact

**Current System**: ~50 data points per minute  
**With Speed Metrics**: ~70 data points per minute  
**Increase**: 40% additional data volume  
**Grafana Cloud Impact**: Still well within free tier limits (10,000 series)

### Processing Overhead

**Speed Calculation**: Minimal CPU impact (<1ms per vehicle)  
**Metrics Recording**: Event-driven, no continuous overhead  
**Background Aggregation**: 30-second intervals, negligible impact  
**Overall Impact**: <2% additional CPU usage

### Memory Usage

**Speed History Storage**: ~1KB per direction (1000 entries max)  
**Metrics Objects**: ~5KB additional Prometheus metrics  
**Total Additional Memory**: <10KB

## Speed Interpretation Guidelines

### Speed Ranges (Pixels per Second)

Based on Bay Bridge camera setup and typical vehicle sizes:

- **0-20 px/s**: Slow/congested traffic or stopped vehicles
- **20-50 px/s**: Normal traffic flow
- **50-100 px/s**: Fast-moving traffic
- **>100 px/s**: Very fast traffic or possible detection artifacts

### Analysis Use Cases

1. **Congestion Detection**: Average speed <20 px/s with high vehicle count
2. **Incident Detection**: Sudden speed drops or unusual patterns
3. **Traffic Flow Optimization**: Speed vs volume correlation analysis
4. **Performance Monitoring**: Track speed consistency over time
5. **Directional Analysis**: Compare left vs right traffic patterns

### Alert Thresholds (Future Enhancement)

- **Speed Drop Alert**: >50% decrease in 5-minute average
- **Congestion Alert**: Average speed <15 px/s for >10 minutes
- **High Speed Alert**: Sustained speeds >80 px/s (possible detection issues)

## Testing Strategy

### Unit Testing
- Speed calculation accuracy with known position/time data
- Metrics recording functionality
- Background aggregation calculations

### Integration Testing
- End-to-end data flow from detection to Grafana
- Prometheus metrics endpoint validation
- Grafana Cloud data ingestion

### Live Traffic Testing
- Deploy with Bay Bridge camera feed
- Validate speed values are reasonable for observed traffic
- Verify directional speed differences make sense
- Monitor system performance impact

## Future Enhancements

### Phase 3: Advanced Analytics (Future)
- Speed distribution histograms
- Percentile calculations (P50, P95)
- Speed prediction based on historical patterns
- Weather correlation analysis

### Phase 4: Alerting Integration (Future)
- Grafana alerts for speed anomalies
- Slack/email notifications for traffic incidents
- Automated incident detection algorithms

## Success Criteria

### Technical Success
- ✅ Speed calculation produces reasonable values (20-80 px/s typical range)
- ✅ Metrics successfully flow from detection to Grafana Cloud
- ✅ Dashboard panels display real-time speed data
- ✅ System performance impact <5% additional CPU/memory usage

### Business Success
- ✅ Speed trends visible and interpretable in Grafana
- ✅ Directional speed differences clearly shown
- ✅ Historical speed data available for analysis
- ✅ Foundation established for traffic flow optimization

## Conclusion

The speed metrics implementation leverages existing infrastructure to provide valuable traffic flow insights with minimal system impact. The proposed solution is technically sound, scalable, and provides immediate business value through enhanced traffic monitoring capabilities.

Key benefits:
- **Low Implementation Cost**: Builds on existing tracking and metrics infrastructure
- **Immediate Value**: Real-time speed monitoring and historical analysis
- **Scalable Design**: Ready for future enhancements and advanced analytics
- **Minimal Impact**: <5% additional system resource usage

The implementation provides a solid foundation for advanced traffic analysis while maintaining the system's current performance and reliability.

## References

- [RFD-001: Motion-Based Traffic Detection](./RFD-001-motion-based-traffic-detection.md)
- [RFD-002: Traffic Counting and Direction Detection](./RFD-002-traffic-counting-direction-detection.md)
- [RFD-004: Prometheus + Grafana Monitoring](./RFD-004-prometheus-grafana-monitoring.md)
- [Prometheus Metrics Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Dashboard Design Guidelines](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
