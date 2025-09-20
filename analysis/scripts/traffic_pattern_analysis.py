#!/usr/bin/env python3
"""
Traffic Pattern Analysis - Phase 3: Day-of-Week Pattern Analysis & Visualization
Bay Bridge Traffic Detection System

This script implements the analysis and visualization phase of RFD-013, creating
comprehensive day-of-week traffic pattern analysis with interactive plots.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime, timedelta
import pytz
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Configuration
TIMEZONE = pytz.timezone('US/Pacific')
CACHE_DIR = Path("analysis/cache")
PLOTS_DIR = Path("analysis/plots")
DATA_DIR = Path("analysis/data")

# Day of week mapping
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
WEEKDAY_COLORS = {
    'Monday': '#1f77b4',
    'Tuesday': '#ff7f0e', 
    'Wednesday': '#2ca02c',
    'Thursday': '#d62728',
    'Friday': '#9467bd',
    'Saturday': '#8c564b',
    'Sunday': '#e377c2'
}

class TrafficPatternAnalyzer:
    """
    Comprehensive traffic pattern analysis with day-of-week segmentation.
    """
    
    def __init__(self):
        self.raw_data = {}
        self.processed_data = {}
        self.daily_segments = {}
        self.weekday_stats = {}
        
        # Create output directories
        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        
    def load_cached_data(self) -> bool:
        """Load the most recent cached data files."""
        try:
            print("📂 Loading cached data...")
            
            # Find the most recent cache files
            cache_files = list(CACHE_DIR.glob("*.parquet"))
            if not cache_files:
                print("❌ No cached data files found")
                return False
            
            # Group by metric name and get most recent
            latest_files = {}
            for file in cache_files:
                metric_name = file.name.split('_20250920_')[0]  # Extract metric name
                if metric_name not in latest_files or file.stat().st_mtime > latest_files[metric_name].stat().st_mtime:
                    latest_files[metric_name] = file
            
            # Load each metric
            for metric_name, file_path in latest_files.items():
                print(f"   📊 Loading {metric_name}...")
                df = pd.read_parquet(file_path)
                
                # Ensure timezone-aware timestamps
                if df['timestamp'].dt.tz is None:
                    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
                df['timestamp'] = df['timestamp'].dt.tz_convert(TIMEZONE)
                
                self.raw_data[metric_name] = df
                print(f"   ✅ Loaded {len(df):,} points")
            
            print(f"✅ Loaded {len(self.raw_data)} metrics successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error loading cached data: {e}")
            return False
    
    def preprocess_data(self):
        """Preprocess raw data for analysis."""
        print("\n🔄 Preprocessing data...")
        
        for metric_name, df in self.raw_data.items():
            print(f"   📊 Processing {metric_name}...")
            
            # Add time-based columns
            df = df.copy()
            df['date'] = df['timestamp'].dt.date
            df['hour'] = df['timestamp'].dt.hour
            df['minute'] = df['timestamp'].dt.minute
            df['weekday'] = df['timestamp'].dt.day_name()
            df['weekday_num'] = df['timestamp'].dt.weekday  # 0=Monday, 6=Sunday
            
            # For vehicle counters, calculate flow rates if not already present
            if metric_name == 'traffic_vehicles_total':
                # Calculate instantaneous flow rate from counter deltas
                df = df.sort_values(['direction', 'timestamp'])
                df['flow_rate'] = df.groupby('direction')['value'].diff() / df.groupby('direction')['timestamp'].diff().dt.total_seconds() * 60
                df['flow_rate'] = df['flow_rate'].fillna(0).clip(lower=0, upper=300)  # Reasonable bounds
            
            self.processed_data[metric_name] = df
            print(f"   ✅ Processed {len(df):,} points")
    
    def segment_by_days(self):
        """Segment time series data by calendar days."""
        print("\n📅 Segmenting data by calendar days...")
        
        for metric_name, df in self.processed_data.items():
            print(f"   📊 Segmenting {metric_name}...")
            
            daily_data = {}
            
            # Group by date and direction
            for (date, direction), day_df in df.groupby(['date', 'direction']):
                if len(day_df) < 100:  # Skip days with insufficient data (< ~2 hours)
                    continue
                
                # Create normalized time axis (minutes from midnight)
                day_df = day_df.copy()
                day_df['minutes_from_midnight'] = day_df['hour'] * 60 + day_df['minute']
                
                # Get weekday
                weekday = day_df['weekday'].iloc[0]
                
                # Store daily segment
                key = f"{date}_{direction}"
                daily_data[key] = {
                    'date': date,
                    'direction': direction,
                    'weekday': weekday,
                    'data': day_df,
                    'total_points': len(day_df)
                }
            
            self.daily_segments[metric_name] = daily_data
            print(f"   ✅ Created {len(daily_data)} daily segments")
    
    def calculate_weekday_statistics(self):
        """Calculate statistical summaries for each weekday."""
        print("\n📈 Calculating weekday statistics...")
        
        for metric_name, daily_segments in self.daily_segments.items():
            print(f"   📊 Analyzing {metric_name}...")
            
            weekday_stats = {}
            
            # Group daily segments by weekday and direction
            for weekday in WEEKDAYS:
                weekday_stats[weekday] = {}
                
                for direction in ['left', 'right']:
                    # Get all days for this weekday/direction combination
                    weekday_days = [
                        segment for segment in daily_segments.values()
                        if segment['weekday'] == weekday and segment['direction'] == direction
                    ]
                    
                    if len(weekday_days) < 2:  # Need at least 2 days for statistics
                        continue
                    
                    # Create time-aligned data matrix
                    time_series_data = []
                    for day_segment in weekday_days:
                        day_data = day_segment['data']
                        
                        # Use appropriate value column
                        if metric_name == 'traffic_vehicles_total':
                            values = day_data['flow_rate'].values
                        else:
                            values = day_data['value'].values
                        
                        time_series_data.append({
                            'date': day_segment['date'],
                            'times': day_data['minutes_from_midnight'].values,
                            'values': values
                        })
                    
                    # Calculate statistics
                    weekday_stats[weekday][direction] = {
                        'num_days': len(weekday_days),
                        'raw_data': time_series_data,
                        'date_range': f"{min(d['date'] for d in weekday_days)} to {max(d['date'] for d in weekday_days)}"
                    }
            
            self.weekday_stats[metric_name] = weekday_stats
            
            # Print summary
            total_days = sum(
                len(stats.get('left', {}).get('raw_data', [])) + len(stats.get('right', {}).get('raw_data', []))
                for stats in weekday_stats.values()
            )
            print(f"   ✅ Analyzed {total_days} day-direction combinations")
    
    def create_weekday_plot(self, metric_name: str, weekday: str) -> go.Figure:
        """Create an interactive plot for a specific weekday."""
        
        if metric_name not in self.weekday_stats or weekday not in self.weekday_stats[metric_name]:
            return None
        
        weekday_data = self.weekday_stats[metric_name][weekday]
        
        # Create subplot with secondary y-axis for dual directions
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=[f"{weekday} Traffic Patterns - {metric_name.replace('_', ' ').title()}"],
            specs=[[{"secondary_y": False}]]
        )
        
        colors = {'left': '#1f77b4', 'right': '#ff7f0e'}
        
        for direction in ['left', 'right']:
            if direction not in weekday_data:
                continue
                
            direction_data = weekday_data[direction]
            raw_data = direction_data['raw_data']
            
            if not raw_data:
                continue
            
            # Plot individual day traces (semi-transparent)
            for i, day_data in enumerate(raw_data):
                times = day_data['times']
                values = day_data['values']
                date_str = day_data['date'].strftime('%Y-%m-%d')
                
                fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=values,
                        mode='lines',
                        name=f"{direction.title()} - {date_str}",
                        line=dict(color=colors[direction], width=1),
                        opacity=0.3,
                        showlegend=i == 0,  # Only show legend for first trace
                        legendgroup=direction,
                        hovertemplate=f"<b>{direction.title()} - {date_str}</b><br>" +
                                    "Time: %{x:.0f} min from midnight<br>" +
                                    "Value: %{y:.1f}<br>" +
                                    "<extra></extra>"
                    )
                )
            
            # Calculate and plot mean line
            if len(raw_data) > 1:
                # Interpolate all days to common time grid
                common_times = np.arange(0, 1440, 5)  # Every 5 minutes
                interpolated_values = []
                
                for day_data in raw_data:
                    times = day_data['times']
                    values = day_data['values']
                    
                    # Remove duplicates and sort
                    unique_indices = np.unique(times, return_index=True)[1]
                    times_clean = times[unique_indices]
                    values_clean = values[unique_indices]
                    
                    if len(times_clean) > 1:
                        interp_values = np.interp(common_times, times_clean, values_clean)
                        interpolated_values.append(interp_values)
                
                if interpolated_values:
                    mean_values = np.mean(interpolated_values, axis=0)
                    std_values = np.std(interpolated_values, axis=0)
                    
                    # Mean line
                    fig.add_trace(
                        go.Scatter(
                            x=common_times,
                            y=mean_values,
                            mode='lines',
                            name=f"{direction.title()} Mean",
                            line=dict(color=colors[direction], width=3),
                            legendgroup=direction,
                            hovertemplate=f"<b>{direction.title()} Mean</b><br>" +
                                        "Time: %{x:.0f} min from midnight<br>" +
                                        "Mean: %{y:.1f}<br>" +
                                        "<extra></extra>"
                        )
                    )
                    
                    # Confidence band (±1 std)
                    fig.add_trace(
                        go.Scatter(
                            x=np.concatenate([common_times, common_times[::-1]]),
                            y=np.concatenate([mean_values + std_values, (mean_values - std_values)[::-1]]),
                            fill='toself',
                            fillcolor=colors[direction].replace('rgb', 'rgba').replace(')', ', 0.2)'),
                            line=dict(color='rgba(255,255,255,0)'),
                            name=f"{direction.title()} ±1σ",
                            showlegend=True,
                            legendgroup=direction,
                            hoverinfo='skip'
                        )
                    )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"<b>{weekday} Traffic Patterns</b><br><sub>{metric_name.replace('_', ' ').title()}</sub>",
                x=0.5,
                font=dict(size=16)
            ),
            xaxis_title="Time (minutes from midnight)",
            yaxis_title="Traffic Flow Rate (vehicles/minute)" if 'flow' in metric_name or 'total' in metric_name else "Value",
            hovermode='x unified',
            template='plotly_white',
            width=1200,
            height=600,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Add time axis labels (convert minutes to hours)
        fig.update_xaxes(
            tickmode='array',
            tickvals=[0, 360, 720, 1080, 1440],
            ticktext=['12 AM', '6 AM', '12 PM', '6 PM', '12 AM']
        )
        
        return fig
    
    def create_overview_plot(self, metric_name: str) -> go.Figure:
        """Create an overview plot showing all weekdays."""
        
        if metric_name not in self.weekday_stats:
            return None
        
        fig = make_subplots(
            rows=2, cols=4,
            subplot_titles=WEEKDAYS + ['Overall Summary'],
            specs=[[{"secondary_y": False}]*4, [{"secondary_y": False}]*3 + [{"secondary_y": False}]],
            vertical_spacing=0.12,
            horizontal_spacing=0.08
        )
        
        # Individual weekday plots
        for i, weekday in enumerate(WEEKDAYS):
            row = (i // 4) + 1
            col = (i % 4) + 1
            
            if weekday not in self.weekday_stats[metric_name]:
                continue
            
            weekday_data = self.weekday_stats[metric_name][weekday]
            
            for direction in ['left', 'right']:
                if direction not in weekday_data:
                    continue
                
                direction_data = weekday_data[direction]
                raw_data = direction_data['raw_data']
                
                if not raw_data or len(raw_data) < 2:
                    continue
                
                # Calculate mean for this weekday
                common_times = np.arange(0, 1440, 10)  # Every 10 minutes for overview
                interpolated_values = []
                
                for day_data in raw_data:
                    times = day_data['times']
                    values = day_data['values']
                    
                    unique_indices = np.unique(times, return_index=True)[1]
                    times_clean = times[unique_indices]
                    values_clean = values[unique_indices]
                    
                    if len(times_clean) > 1:
                        interp_values = np.interp(common_times, times_clean, values_clean)
                        interpolated_values.append(interp_values)
                
                if interpolated_values:
                    mean_values = np.mean(interpolated_values, axis=0)
                    
                    color = '#1f77b4' if direction == 'left' else '#ff7f0e'
                    
                    fig.add_trace(
                        go.Scatter(
                            x=common_times,
                            y=mean_values,
                            mode='lines',
                            name=f"{direction.title()}",
                            line=dict(color=color, width=2),
                            showlegend=(i == 0),  # Only show legend for first subplot
                            legendgroup=direction,
                            hovertemplate=f"<b>{weekday} - {direction.title()}</b><br>" +
                                        "Time: %{x:.0f} min<br>" +
                                        "Mean: %{y:.1f}<br>" +
                                        "<extra></extra>"
                        ),
                        row=row, col=col
                    )
        
        # Overall summary in last subplot
        # This will show average patterns across all weekdays
        all_weekday_means = {'left': [], 'right': []}
        common_times = np.arange(0, 1440, 10)
        
        for weekday in WEEKDAYS:
            if weekday not in self.weekday_stats[metric_name]:
                continue
                
            weekday_data = self.weekday_stats[metric_name][weekday]
            
            for direction in ['left', 'right']:
                if direction not in weekday_data:
                    continue
                
                direction_data = weekday_data[direction]
                raw_data = direction_data['raw_data']
                
                if len(raw_data) < 2:
                    continue
                
                # Calculate mean for this weekday/direction
                interpolated_values = []
                for day_data in raw_data:
                    times = day_data['times']
                    values = day_data['values']
                    
                    unique_indices = np.unique(times, return_index=True)[1]
                    times_clean = times[unique_indices]
                    values_clean = values[unique_indices]
                    
                    if len(times_clean) > 1:
                        interp_values = np.interp(common_times, times_clean, values_clean)
                        interpolated_values.append(interp_values)
                
                if interpolated_values:
                    weekday_mean = np.mean(interpolated_values, axis=0)
                    all_weekday_means[direction].append(weekday_mean)
        
        # Plot overall averages
        for direction in ['left', 'right']:
            if all_weekday_means[direction]:
                overall_mean = np.mean(all_weekday_means[direction], axis=0)
                color = '#1f77b4' if direction == 'left' else '#ff7f0e'
                
                fig.add_trace(
                    go.Scatter(
                        x=common_times,
                        y=overall_mean,
                        mode='lines',
                        name=f"Overall {direction.title()}",
                        line=dict(color=color, width=3),
                        showlegend=False,
                        hovertemplate=f"<b>Overall Average - {direction.title()}</b><br>" +
                                    "Time: %{x:.0f} min<br>" +
                                    "Mean: %{y:.1f}<br>" +
                                    "<extra></extra>"
                    ),
                    row=2, col=4
                )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"<b>Weekly Traffic Pattern Overview</b><br><sub>{metric_name.replace('_', ' ').title()}</sub>",
                x=0.5,
                font=dict(size=18)
            ),
            template='plotly_white',
            width=1600,
            height=800,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom", 
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update all x-axes to show time labels
        for i in range(1, 9):  # 8 subplots total
            row = ((i-1) // 4) + 1
            col = ((i-1) % 4) + 1
            
            fig.update_xaxes(
                tickmode='array',
                tickvals=[0, 720, 1440],
                ticktext=['12AM', '12PM', '12AM'],
                row=row, col=col
            )
        
        return fig

def main():
    """Main analysis and visualization workflow."""
    print("🚀 Starting Traffic Pattern Analysis - Visualization Phase")
    print("📍 Bay Bridge Traffic Detection System")
    print("-" * 60)
    
    # Initialize analyzer
    analyzer = TrafficPatternAnalyzer()
    
    # Load cached data
    if not analyzer.load_cached_data():
        print("❌ Failed to load cached data")
        sys.exit(1)
    
    # Preprocess data
    analyzer.preprocess_data()
    
    # Segment by days
    analyzer.segment_by_days()
    
    # Calculate statistics
    analyzer.calculate_weekday_statistics()
    
    print("\n🎨 Creating interactive visualizations...")
    
    # Focus on primary traffic metrics for visualization
    primary_metrics = ['traffic_vehicles_total', 'traffic_flow_rate_per_minute']
    
    for metric_name in primary_metrics:
        if metric_name not in analyzer.weekday_stats:
            continue
            
        print(f"\n📊 Creating plots for {metric_name}...")
        
        # Create individual weekday plots
        for weekday in WEEKDAYS:
            if weekday in analyzer.weekday_stats[metric_name]:
                fig = analyzer.create_weekday_plot(metric_name, weekday)
                if fig:
                    filename = f"{metric_name}_{weekday.lower()}_pattern.html"
                    filepath = PLOTS_DIR / filename
                    fig.write_html(filepath)
                    print(f"   ✅ Saved {weekday} plot: {filepath}")
        
        # Create overview plot
        overview_fig = analyzer.create_overview_plot(metric_name)
        if overview_fig:
            filename = f"{metric_name}_weekly_overview.html"
            filepath = PLOTS_DIR / filename
            overview_fig.write_html(filepath)
            print(f"   ✅ Saved overview plot: {filepath}")
    
    print(f"\n✅ Visualization phase completed successfully!")
    print(f"📁 Interactive plots saved to: {PLOTS_DIR}")
    print(f"🌐 Open the HTML files in your browser to explore the data")

if __name__ == "__main__":
    main()
