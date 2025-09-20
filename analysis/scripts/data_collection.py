#!/usr/bin/env python3
"""
Traffic Pattern Analysis - Phase 2: Data Collection & Caching
Bay Bridge Traffic Detection System

This script implements the data collection phase of RFD-013, fetching
all historical traffic data from Prometheus and caching it for analysis.
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
import time
from pathlib import Path

# Configuration
PROMETHEUS_URL = "http://localhost:9090"
TIMEZONE = pytz.timezone('US/Pacific')
CACHE_DIR = Path("analysis/cache")
DATA_DIR = Path("analysis/data")

# Metrics to collect (based on discovery results)
PRIMARY_METRICS = [
    'traffic_vehicles_total',
    'traffic_flow_rate_per_minute'
]

SECONDARY_METRICS = [
    'traffic_speed_current_pixels_per_second',
    'traffic_speed_average_pixels_per_second'
]

class PrometheusDataCollector:
    """
    Comprehensive data collection from Prometheus with caching and validation.
    """
    
    def __init__(self, prometheus_url: str = PROMETHEUS_URL):
        self.prometheus_url = prometheus_url
        self.session = requests.Session()
        self.session.timeout = 30
        self.collected_data = {}
        
        # Create directories
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
    def load_discovery_results(self) -> Dict:
        """Load results from data discovery phase."""
        discovery_file = DATA_DIR / "discovery_results.json"
        if discovery_file.exists():
            with open(discovery_file, 'r') as f:
                return json.load(f)
        else:
            print("❌ Discovery results not found. Run data_discovery.py first.")
            sys.exit(1)
    
    def collect_metric_data(self, metric: str, start_time: int, end_time: int,
                           step: str = '1m', chunk_hours: int = 24) -> Optional[pd.DataFrame]:
        """
        Collect data for a single metric over the specified time range.
        Uses chunked queries to handle large time ranges.

        Args:
            metric: Prometheus metric name
            start_time: Unix timestamp start
            end_time: Unix timestamp end
            step: Query step size (e.g., '1m', '5m')
            chunk_hours: Hours per chunk to avoid query timeouts

        Returns:
            DataFrame with timestamp and value columns, or None if failed
        """
        try:
            print(f"   📊 Collecting {metric} data...")

            # Calculate chunks
            total_duration = end_time - start_time
            chunk_seconds = chunk_hours * 3600
            num_chunks = max(1, (total_duration + chunk_seconds - 1) // chunk_seconds)

            if num_chunks > 1:
                print(f"   🔄 Breaking into {num_chunks} chunks of {chunk_hours}h each")

            all_chunks = []

            for i in range(num_chunks):
                chunk_start = start_time + (i * chunk_seconds)
                chunk_end = min(start_time + ((i + 1) * chunk_seconds), end_time)

                print(f"   📦 Chunk {i+1}/{num_chunks}: {datetime.fromtimestamp(chunk_start, tz=TIMEZONE).strftime('%m-%d %H:%M')} to {datetime.fromtimestamp(chunk_end, tz=TIMEZONE).strftime('%m-%d %H:%M')}")

                # Query this chunk
                response = self.session.get(
                    f"{self.prometheus_url}/api/v1/query_range",
                    params={
                        'query': metric,
                        'start': chunk_start,
                        'end': chunk_end,
                        'step': step
                    }
                )

                if response.status_code != 200:
                    print(f"   ❌ Chunk {i+1} failed with status {response.status_code}")
                    # Try to get error details
                    try:
                        error_data = response.json()
                        print(f"   📝 Error: {error_data.get('error', 'Unknown error')}")
                    except:
                        pass
                    continue

                data = response.json()

                if not data['data']['result']:
                    print(f"   ⚠️  No data in chunk {i+1}")
                    continue

                # Process results for this chunk
                chunk_series = []

                for series in data['data']['result']:
                    labels = series['metric']
                    values = series['values']

                    if not values:
                        continue

                    # Create DataFrame for this series
                    df = pd.DataFrame(values, columns=['timestamp', 'value'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                    df['timestamp'] = df['timestamp'].dt.tz_convert(TIMEZONE)
                    df['value'] = pd.to_numeric(df['value'], errors='coerce')

                    # Add label columns
                    for label_key, label_value in labels.items():
                        if label_key not in ['__name__', 'instance', 'job']:
                            df[label_key] = label_value

                    df['metric'] = metric
                    chunk_series.append(df)

                if chunk_series:
                    chunk_df = pd.concat(chunk_series, ignore_index=True)
                    all_chunks.append(chunk_df)
                    print(f"   ✅ Chunk {i+1}: {len(chunk_df)} points")

                # Small delay between chunks to be nice to Prometheus
                if i < num_chunks - 1:
                    time.sleep(0.5)

            if not all_chunks:
                print(f"   ❌ No data collected for {metric}")
                return None

            # Combine all chunks
            combined_df = pd.concat(all_chunks, ignore_index=True)

            # Remove duplicates and sort
            # Determine deduplication columns based on what's available
            dedup_columns = ['timestamp', 'metric']
            if 'direction' in combined_df.columns:
                dedup_columns.append('direction')
            if 'app' in combined_df.columns:
                dedup_columns.append('app')
            if 'exported_instance' in combined_df.columns:
                dedup_columns.append('exported_instance')

            combined_df = combined_df.drop_duplicates(subset=dedup_columns)
            combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)

            print(f"   ✅ Total collected: {len(combined_df)} data points")
            return combined_df

        except Exception as e:
            print(f"   ❌ Error collecting {metric}: {e}")
            return None
    
    def collect_all_metrics(self, resolution: str = '1m') -> Dict[str, pd.DataFrame]:
        """
        Collect data for all metrics based on discovery results.
        
        Args:
            resolution: Time resolution ('1m' or '5m')
            
        Returns:
            Dictionary mapping metric names to DataFrames
        """
        print(f"🚀 Starting data collection with {resolution} resolution...")
        
        # Load discovery results to get time ranges
        discovery = self.load_discovery_results()
        volume_analysis = discovery.get('volume_analysis', {})
        
        collected_data = {}
        
        # Collect primary metrics (longest history)
        for metric in PRIMARY_METRICS:
            if metric in volume_analysis:
                analysis = volume_analysis[metric]
                if 'error' in analysis:
                    print(f"⚠️  Skipping {metric}: {analysis['error']}")
                    continue
                
                # Parse time range
                start_dt = datetime.fromisoformat(analysis['earliest'])
                end_dt = datetime.fromisoformat(analysis['latest'])
                
                start_timestamp = int(start_dt.timestamp())
                end_timestamp = int(end_dt.timestamp())
                
                print(f"\n📈 Collecting {metric}")
                print(f"   📅 Range: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
                print(f"   ⏱️  Duration: {analysis['duration_hours']:.1f} hours")
                
                df = self.collect_metric_data(metric, start_timestamp, end_timestamp, resolution)
                if df is not None:
                    collected_data[metric] = df
        
        # Collect secondary metrics (shorter history)
        for metric in SECONDARY_METRICS:
            if metric in volume_analysis:
                analysis = volume_analysis[metric]
                if 'error' in analysis:
                    print(f"⚠️  Skipping {metric}: {analysis['error']}")
                    continue
                
                # Parse time range
                start_dt = datetime.fromisoformat(analysis['earliest'])
                end_dt = datetime.fromisoformat(analysis['latest'])
                
                start_timestamp = int(start_dt.timestamp())
                end_timestamp = int(end_dt.timestamp())
                
                print(f"\n📈 Collecting {metric}")
                print(f"   📅 Range: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
                print(f"   ⏱️  Duration: {analysis['duration_hours']:.1f} hours")
                
                df = self.collect_metric_data(metric, start_timestamp, end_timestamp, resolution)
                if df is not None:
                    collected_data[metric] = df
        
        self.collected_data = collected_data
        return collected_data
    
    def validate_data_quality(self) -> Dict:
        """
        Validate the quality of collected data.
        
        Returns:
            Dictionary with validation results
        """
        print("\n🔍 Validating data quality...")
        
        validation_results = {}
        
        for metric, df in self.collected_data.items():
            print(f"\n   📊 Validating {metric}...")
            
            # Basic statistics
            total_points = len(df)
            null_values = df['value'].isnull().sum()
            unique_timestamps = df['timestamp'].nunique()
            
            # Time range analysis
            time_range = df['timestamp'].max() - df['timestamp'].min()
            expected_points = time_range.total_seconds() / 60  # Assuming 1-minute resolution
            completeness = total_points / expected_points if expected_points > 0 else 0
            
            # Check for duplicates
            duplicates = df.duplicated(subset=['timestamp', 'metric']).sum()
            
            # Value range analysis
            value_stats = df['value'].describe()
            
            results = {
                'total_points': total_points,
                'null_values': null_values,
                'unique_timestamps': unique_timestamps,
                'time_range_hours': time_range.total_seconds() / 3600,
                'completeness': completeness,
                'duplicates': duplicates,
                'value_stats': value_stats.to_dict()
            }
            
            validation_results[metric] = results
            
            print(f"      📈 Total points: {total_points:,}")
            print(f"      🕳️  Null values: {null_values}")
            print(f"      ⏱️  Time range: {time_range.total_seconds()/3600:.1f} hours")
            print(f"      ✅ Completeness: {completeness:.1%}")
            print(f"      🔄 Duplicates: {duplicates}")
            
            if null_values > 0:
                print(f"      ⚠️  Warning: {null_values} null values found")
            if duplicates > 0:
                print(f"      ⚠️  Warning: {duplicates} duplicate entries found")
        
        return validation_results
    
    def save_cached_data(self, format: str = 'parquet') -> bool:
        """
        Save collected data to cache files.
        
        Args:
            format: File format ('parquet', 'csv', or 'pickle')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n💾 Saving data to cache (format: {format})...")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for metric, df in self.collected_data.items():
                if format == 'parquet':
                    filename = CACHE_DIR / f"{metric}_{timestamp}.parquet"
                    df.to_parquet(filename, index=False)
                elif format == 'csv':
                    filename = CACHE_DIR / f"{metric}_{timestamp}.csv"
                    df.to_csv(filename, index=False)
                elif format == 'pickle':
                    filename = CACHE_DIR / f"{metric}_{timestamp}.pkl"
                    df.to_pickle(filename)
                else:
                    raise ValueError(f"Unsupported format: {format}")
                
                print(f"   ✅ Saved {metric}: {filename} ({len(df):,} rows)")
            
            # Save metadata
            metadata = {
                'collection_timestamp': timestamp,
                'format': format,
                'metrics': list(self.collected_data.keys()),
                'total_points': sum(len(df) for df in self.collected_data.values()),
                'validation_results': self.validate_data_quality()
            }
            
            metadata_file = DATA_DIR / f"collection_metadata_{timestamp}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            print(f"   📋 Metadata saved: {metadata_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving cached data: {e}")
            return False
    
    def print_collection_summary(self):
        """Print a summary of the data collection."""
        print("\n" + "="*60)
        print("📋 DATA COLLECTION SUMMARY")
        print("="*60)
        
        total_points = sum(len(df) for df in self.collected_data.values())
        total_memory = sum(df.memory_usage(deep=True).sum() for df in self.collected_data.values()) / 1024 / 1024
        
        print(f"📊 Metrics collected: {len(self.collected_data)}")
        print(f"📈 Total data points: {total_points:,}")
        print(f"💾 Memory usage: {total_memory:.1f} MB")
        
        for metric, df in self.collected_data.items():
            time_range = df['timestamp'].max() - df['timestamp'].min()
            print(f"   📊 {metric}: {len(df):,} points, {time_range.total_seconds()/3600:.1f} hours")
        
        print("="*60)

def main():
    """Main data collection workflow."""
    print("🚀 Starting Traffic Pattern Analysis - Data Collection Phase")
    print("📍 Bay Bridge Traffic Detection System")
    print("-" * 60)
    
    # Initialize collector
    collector = PrometheusDataCollector()
    
    # Collect all metrics
    collected_data = collector.collect_all_metrics(resolution='1m')
    
    if not collected_data:
        print("❌ No data collected")
        sys.exit(1)
    
    # Validate data quality
    validation_results = collector.validate_data_quality()
    
    # Save to cache
    success = collector.save_cached_data(format='parquet')
    
    if success:
        collector.print_collection_summary()
        print("\n✅ Data collection phase completed successfully!")
        print("🎯 Next step: Run data analysis script")
    else:
        print("❌ Data collection failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
