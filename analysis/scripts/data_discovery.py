#!/usr/bin/env python3
"""
Traffic Pattern Analysis - Phase 1: Data Discovery & Infrastructure
Bay Bridge Traffic Detection System

This script implements the data discovery phase of RFD-013, assessing
data availability, volume, and quality from the Prometheus server.
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import os
import sys
from typing import Dict, List, Tuple, Optional

# Configuration
PROMETHEUS_URL = "http://localhost:9090"
TIMEZONE = pytz.timezone('US/Pacific')
METRICS_OF_INTEREST = [
    'traffic_vehicles_total',
    'traffic_flow_rate_per_minute', 
    'traffic_speed_current_pixels_per_second',
    'traffic_speed_average_pixels_per_second'
]

class PrometheusDataDiscovery:
    """
    Data discovery and assessment for Prometheus traffic metrics.
    """
    
    def __init__(self, prometheus_url: str = PROMETHEUS_URL):
        self.prometheus_url = prometheus_url
        self.session = requests.Session()
        self.discovery_results = {}
        
    def check_prometheus_health(self) -> bool:
        """Check if Prometheus is accessible and healthy."""
        try:
            response = self.session.get(f"{self.prometheus_url}/api/v1/query", 
                                      params={'query': 'up'}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Prometheus server accessible at {self.prometheus_url}")
                print(f"📊 Status: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ Prometheus server returned status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed to connect to Prometheus: {e}")
            return False
    
    def discover_available_metrics(self) -> List[str]:
        """Discover all available traffic-related metrics."""
        try:
            response = self.session.get(f"{self.prometheus_url}/api/v1/label/__name__/values")
            if response.status_code == 200:
                data = response.json()
                all_metrics = data['data']
                traffic_metrics = [m for m in all_metrics if m.startswith('traffic_')]
                
                print(f"📈 Found {len(traffic_metrics)} traffic metrics:")
                for metric in traffic_metrics:
                    print(f"   - {metric}")
                
                self.discovery_results['available_metrics'] = traffic_metrics
                return traffic_metrics
            else:
                print(f"❌ Failed to get metrics list: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error discovering metrics: {e}")
            return []
    
    def get_metric_time_range(self, metric: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get the earliest and latest timestamps for a metric."""
        try:
            # Get current/latest timestamp first
            response = self.session.get(f"{self.prometheus_url}/api/v1/query",
                                      params={'query': metric})

            if response.status_code != 200:
                return None, None

            data = response.json()
            if not data['data']['result']:
                return None, None

            latest_timestamp = float(data['data']['result'][0]['value'][0])
            latest_dt = datetime.fromtimestamp(latest_timestamp, tz=TIMEZONE)

            # Find earliest timestamp by binary search approach
            # Start with a large range and work backwards
            end_time = int(latest_timestamp)

            # Use a more efficient approach: query with a very early start time
            # and let Prometheus return the actual data range
            very_early_start = 1672531200  # Jan 1, 2023 (arbitrary early date)

            range_response = self.session.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params={
                    'query': metric,
                    'start': very_early_start,
                    'end': end_time,
                    'step': '1d'  # Daily steps to get full range efficiently
                },
                timeout=30
            )

            earliest_timestamp = None

            if range_response.status_code == 200:
                range_data = range_response.json()
                if (range_data['data']['result'] and
                    range_data['data']['result'][0]['values']):
                    # Get the first data point
                    earliest_timestamp = float(range_data['data']['result'][0]['values'][0][0])
                    data_points = len(range_data['data']['result'][0]['values'])
                    print(f"   🔍 Found {data_points} days of data")
                else:
                    print(f"   ⚠️  No data found in range query")
            else:
                print(f"   ⚠️  Range query failed with status {range_response.status_code}")

            if earliest_timestamp:
                earliest_dt = datetime.fromtimestamp(earliest_timestamp, tz=TIMEZONE)
                return earliest_dt, latest_dt
            else:
                # Fallback: just return latest timestamp
                return latest_dt, latest_dt

        except Exception as e:
            print(f"❌ Error getting time range for {metric}: {e}")
            return None, None
    
    def assess_data_density(self, metric: str, sample_hours: int = 24) -> Dict:
        """Assess data density and quality for a metric."""
        try:
            # Get current time and sample period
            end_time = int(datetime.now().timestamp())
            start_time = end_time - (sample_hours * 3600)
            
            # Query with 1-minute resolution
            response = self.session.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params={
                    'query': metric,
                    'start': start_time,
                    'end': end_time,
                    'step': '1m'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    values = data['data']['result'][0]['values']
                    expected_points = sample_hours * 60  # 1 point per minute
                    actual_points = len(values)
                    completeness = actual_points / expected_points
                    
                    # Check for gaps
                    timestamps = [float(v[0]) for v in values]
                    gaps = []
                    for i in range(1, len(timestamps)):
                        gap = timestamps[i] - timestamps[i-1]
                        if gap > 120:  # More than 2 minutes
                            gaps.append(gap)
                    
                    return {
                        'expected_points': expected_points,
                        'actual_points': actual_points,
                        'completeness': completeness,
                        'gaps_count': len(gaps),
                        'max_gap_seconds': max(gaps) if gaps else 0,
                        'sample_hours': sample_hours
                    }
            
            return {'error': 'No data available'}
            
        except Exception as e:
            return {'error': str(e)}
    
    def estimate_total_data_volume(self) -> Dict:
        """Estimate total data volume and memory requirements."""
        results = {}
        
        for metric in METRICS_OF_INTEREST:
            print(f"\n🔍 Analyzing {metric}...")
            
            # Get time range
            earliest, latest = self.get_metric_time_range(metric)
            if earliest and latest:
                duration = latest - earliest
                duration_hours = duration.total_seconds() / 3600
                
                print(f"   📅 Time range: {earliest.strftime('%Y-%m-%d %H:%M')} to {latest.strftime('%Y-%m-%d %H:%M')}")
                print(f"   ⏱️  Duration: {duration_hours:.1f} hours ({duration.days} days)")
                
                # Assess data density
                density = self.assess_data_density(metric, min(24, int(duration_hours)))
                if 'error' not in density:
                    print(f"   📊 Data completeness: {density['completeness']:.1%}")
                    print(f"   🕳️  Data gaps: {density['gaps_count']} gaps, max {density['max_gap_seconds']:.0f}s")
                    
                    # Estimate total volume
                    estimated_points_1m = duration_hours * 60 * density['completeness']
                    estimated_points_5m = duration_hours * 12 * density['completeness']
                    
                    print(f"   📈 Estimated data points:")
                    print(f"      - 1-minute resolution: {estimated_points_1m:,.0f} points")
                    print(f"      - 5-minute resolution: {estimated_points_5m:,.0f} points")
                    
                    results[metric] = {
                        'earliest': earliest,
                        'latest': latest,
                        'duration_hours': duration_hours,
                        'duration_days': duration.days,
                        'completeness': density['completeness'],
                        'gaps_count': density['gaps_count'],
                        'estimated_points_1m': estimated_points_1m,
                        'estimated_points_5m': estimated_points_5m,
                        'memory_mb_1m': estimated_points_1m * 32 / 1024 / 1024,  # Rough estimate
                        'memory_mb_5m': estimated_points_5m * 32 / 1024 / 1024
                    }
                else:
                    print(f"   ❌ Error assessing density: {density.get('error', 'unknown')}")
                    results[metric] = {'error': density.get('error', 'unknown')}
            else:
                print(f"   ❌ Could not determine time range")
                results[metric] = {'error': 'Could not determine time range'}
        
        self.discovery_results['volume_analysis'] = results
        return results
    
    def save_discovery_results(self, output_file: str = "analysis/data/discovery_results.json"):
        """Save discovery results to file."""
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Convert datetime objects to strings for JSON serialization
            serializable_results = {}
            for key, value in self.discovery_results.items():
                if isinstance(value, dict):
                    serializable_value = {}
                    for k, v in value.items():
                        if isinstance(v, dict):
                            serializable_v = {}
                            for k2, v2 in v.items():
                                if isinstance(v2, datetime):
                                    serializable_v[k2] = v2.isoformat()
                                else:
                                    serializable_v[k2] = v2
                            serializable_value[k] = serializable_v
                        else:
                            serializable_value[k] = v
                    serializable_results[key] = serializable_value
                else:
                    serializable_results[key] = value
            
            with open(output_file, 'w') as f:
                json.dump(serializable_results, f, indent=2)
            
            print(f"\n💾 Discovery results saved to {output_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            return False
    
    def print_summary(self):
        """Print a summary of discovery results."""
        print("\n" + "="*60)
        print("📋 DATA DISCOVERY SUMMARY")
        print("="*60)
        
        if 'volume_analysis' in self.discovery_results:
            total_points_1m = sum(r.get('estimated_points_1m', 0) 
                                for r in self.discovery_results['volume_analysis'].values() 
                                if isinstance(r, dict) and 'estimated_points_1m' in r)
            
            total_memory_1m = sum(r.get('memory_mb_1m', 0) 
                                for r in self.discovery_results['volume_analysis'].values() 
                                if isinstance(r, dict) and 'memory_mb_1m' in r)
            
            print(f"📊 Total estimated data points (1-min): {total_points_1m:,.0f}")
            print(f"💾 Estimated memory requirement: {total_memory_1m:.1f} MB")
            print(f"🎯 Recommended resolution: {'1-minute' if total_memory_1m < 500 else '5-minute'}")
            
            # Find the metric with the longest history
            longest_metric = None
            max_duration = 0
            for metric, data in self.discovery_results['volume_analysis'].items():
                if isinstance(data, dict) and 'duration_hours' in data:
                    if data['duration_hours'] > max_duration:
                        max_duration = data['duration_hours']
                        longest_metric = metric
            
            if longest_metric:
                print(f"📅 Longest data history: {longest_metric} ({max_duration:.1f} hours)")
        
        print("="*60)

def main():
    """Main data discovery workflow."""
    print("🚀 Starting Traffic Pattern Analysis - Data Discovery Phase")
    print("📍 Bay Bridge Traffic Detection System")
    print("-" * 60)
    
    # Initialize discovery
    discovery = PrometheusDataDiscovery()
    
    # Phase 1: Health check
    if not discovery.check_prometheus_health():
        print("❌ Cannot proceed without Prometheus access")
        sys.exit(1)
    
    # Phase 2: Discover metrics
    print("\n🔍 Discovering available metrics...")
    available_metrics = discovery.discover_available_metrics()
    
    if not available_metrics:
        print("❌ No traffic metrics found")
        sys.exit(1)
    
    # Phase 3: Assess data volume
    print("\n📊 Assessing data volume and quality...")
    volume_results = discovery.estimate_total_data_volume()
    
    # Phase 4: Save and summarize
    discovery.save_discovery_results()
    discovery.print_summary()
    
    print("\n✅ Data discovery phase completed successfully!")
    print("🎯 Next step: Run data collection script")

if __name__ == "__main__":
    main()
