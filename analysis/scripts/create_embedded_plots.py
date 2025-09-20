#!/usr/bin/env python3
"""
Create embedded-friendly versions of traffic pattern plots
Optimized for iframe display in dashboard
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configuration
TIMEZONE = pytz.timezone('US/Pacific')
CACHE_DIR = Path("analysis/cache")
PLOTS_DIR = Path("analysis/plots")
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

class EmbeddedPlotGenerator:
    """Generate plots optimized for iframe embedding."""
    
    def __init__(self):
        self.raw_data = {}
        self.processed_data = {}
        self.daily_segments = {}
        self.weekday_stats = {}
        
    def load_cached_data(self) -> bool:
        """Load the most recent cached data files."""
        try:
            print("Loading cached data...")
            
            # Find the most recent cache files
            cache_files = list(CACHE_DIR.glob("*.parquet"))
            if not cache_files:
                print("No cached data files found")
                return False
            
            # Load flow rate data
            flow_rate_files = [f for f in cache_files if 'traffic_flow_rate_per_minute' in f.name]
            if not flow_rate_files:
                print("No flow rate data found")
                return False
            
            latest_file = max(flow_rate_files, key=lambda f: f.stat().st_mtime)
            print(f"Loading {latest_file.name}...")
            
            df = pd.read_parquet(latest_file)
            
            # Ensure timezone-aware timestamps
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
            df['timestamp'] = df['timestamp'].dt.tz_convert(TIMEZONE)
            
            self.raw_data['traffic_flow_rate_per_minute'] = df
            print(f"Loaded {len(df):,} points")
            return True
            
        except Exception as e:
            print(f"Error loading cached data: {e}")
            return False
    
    def preprocess_data(self):
        """Preprocess raw data for analysis."""
        print("Preprocessing data...")
        
        for metric_name, df in self.raw_data.items():
            df = df.copy()
            df['date'] = df['timestamp'].dt.date
            df['hour'] = df['timestamp'].dt.hour
            df['minute'] = df['timestamp'].dt.minute
            df['weekday'] = df['timestamp'].dt.day_name()
            df['weekday_num'] = df['timestamp'].dt.weekday
            
            self.processed_data[metric_name] = df
    
    def segment_by_days(self):
        """Segment time series data by calendar days."""
        print("Segmenting data by calendar days...")
        
        for metric_name, df in self.processed_data.items():
            daily_data = {}
            
            for (date, direction), day_df in df.groupby(['date', 'direction']):
                if len(day_df) < 100:  # Skip days with insufficient data
                    continue
                
                day_df = day_df.copy()
                day_df['minutes_from_midnight'] = day_df['hour'] * 60 + day_df['minute']
                weekday = day_df['weekday'].iloc[0]
                
                key = f"{date}_{direction}"
                daily_data[key] = {
                    'date': date,
                    'direction': direction,
                    'weekday': weekday,
                    'data': day_df,
                    'total_points': len(day_df)
                }
            
            self.daily_segments[metric_name] = daily_data
    
    def calculate_weekday_statistics(self):
        """Calculate statistical summaries for each weekday."""
        print("Calculating weekday statistics...")
        
        for metric_name, daily_segments in self.daily_segments.items():
            weekday_stats = {}
            
            for weekday in WEEKDAYS:
                weekday_stats[weekday] = {}
                
                for direction in ['left', 'right']:
                    weekday_days = [
                        segment for segment in daily_segments.values()
                        if segment['weekday'] == weekday and segment['direction'] == direction
                    ]
                    
                    if len(weekday_days) < 2:
                        continue
                    
                    time_series_data = []
                    for day_segment in weekday_days:
                        day_data = day_segment['data']
                        values = day_data['value'].values
                        
                        time_series_data.append({
                            'date': day_segment['date'],
                            'times': day_data['minutes_from_midnight'].values,
                            'values': values
                        })
                    
                    weekday_stats[weekday][direction] = {
                        'num_days': len(weekday_days),
                        'raw_data': time_series_data,
                        'date_range': f"{min(d['date'] for d in weekday_days)} to {max(d['date'] for d in weekday_days)}"
                    }
            
            self.weekday_stats[metric_name] = weekday_stats
    
    def create_embedded_weekday_plot(self, weekday: str) -> go.Figure:
        """Create a compact plot optimized for iframe embedding."""
        
        metric_name = 'traffic_flow_rate_per_minute'
        if metric_name not in self.weekday_stats or weekday not in self.weekday_stats[metric_name]:
            return None
        
        weekday_data = self.weekday_stats[metric_name][weekday]
        
        # Create single plot (no subplots for simplicity)
        fig = go.Figure()
        
        colors = {'left': '#1f77b4', 'right': '#ff7f0e'}
        
        for direction in ['left', 'right']:
            if direction not in weekday_data:
                continue
                
            direction_data = weekday_data[direction]
            raw_data = direction_data['raw_data']
            
            if not raw_data:
                continue
            
            # Plot individual day traces (semi-transparent, no hover)
            for i, day_data in enumerate(raw_data):
                times = day_data['times']
                values = day_data['values']
                date_str = day_data['date'].strftime('%Y-%m-%d')

                fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=values,
                        mode='lines',
                        name=f"{direction.title()} Raw Data",
                        line=dict(color=colors[direction], width=1),
                        opacity=0.3,
                        showlegend=i == 0,
                        legendgroup=f"{direction}_raw",
                        hoverinfo='skip'  # Remove hover for individual days
                    )
                )
            
            # Calculate and plot mean line
            if len(raw_data) > 1:
                common_times = np.arange(0, 1440, 5)  # Every 5 minutes
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
                    std_values = np.std(interpolated_values, axis=0)
                    
                    # Convert minutes to time strings for hover
                    time_strings = []
                    for minutes in common_times:
                        hours = int(minutes // 60)
                        mins = int(minutes % 60)
                        if hours == 0:
                            time_str = f"12:{mins:02d} AM"
                        elif hours < 12:
                            time_str = f"{hours}:{mins:02d} AM"
                        elif hours == 12:
                            time_str = f"12:{mins:02d} PM"
                        else:
                            time_str = f"{hours-12}:{mins:02d} PM"
                        time_strings.append(time_str)

                    # Mean line with simplified hover
                    fig.add_trace(
                        go.Scatter(
                            x=common_times,
                            y=mean_values,
                            mode='lines',
                            name=f"{direction.title()} Mean",
                            line=dict(color=colors[direction], width=3),
                            legendgroup=direction,
                            hovertemplate=f"<b>{direction.title()}</b><br>" +
                                        "Time: %{customdata}<br>" +
                                        "Mean: %{y:.1f} vehicles/min<br>" +
                                        "Std: " + f"{np.mean(std_values):.1f}<br>" +
                                        "<extra></extra>",
                            customdata=time_strings
                        )
                    )
                    
                    # Confidence band (±1 std) - very transparent
                    # Convert color to rgba with very low opacity
                    if colors[direction].startswith('#'):
                        # Convert hex to rgba
                        hex_color = colors[direction].lstrip('#')
                        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                        fill_color = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.05)'
                    else:
                        # Handle rgb format
                        fill_color = colors[direction].replace('rgb', 'rgba').replace(')', ', 0.05)')

                    fig.add_trace(
                        go.Scatter(
                            x=np.concatenate([common_times, common_times[::-1]]),
                            y=np.concatenate([mean_values + std_values, (mean_values - std_values)[::-1]]),
                            fill='toself',
                            fillcolor=fill_color,
                            line=dict(color='rgba(255,255,255,0)'),
                            name=f"{direction.title()} ±1σ",
                            showlegend=True,
                            legendgroup=direction,
                            hoverinfo='skip'
                        )
                    )
        
        # Compact layout optimized for embedding
        fig.update_layout(
            title=dict(
                text=f"{weekday} Traffic Flow Patterns",
                x=0.5,
                font=dict(size=14)
            ),
            xaxis_title="Time",
            yaxis_title="Flow Rate (vehicles/min)",
            hovermode='x unified',
            template='plotly_white',
            width=480,  # Compact width for embedding
            height=480,  # Slightly taller to accommodate legend
            margin=dict(l=50, r=20, t=50, b=80),  # More bottom margin for legend
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.6,  # Move legend further down
                xanchor="center",
                x=0.5,
                font=dict(size=9)
            )
        )
        
        # Time axis with actual time format
        fig.update_xaxes(
            tickmode='array',
            tickvals=[0, 120, 240, 360, 480, 600, 720, 840, 960, 1080, 1200, 1320, 1440],
            ticktext=['12AM', '2AM', '4AM', '6AM', '8AM', '10AM', '12PM', '2PM', '4PM', '6PM', '8PM', '10PM', '12AM'],
            tickfont=dict(size=9),
            tickangle=45  # Angle the labels for better readability
        )
        
        fig.update_yaxes(
            tickfont=dict(size=10)
        )
        
        return fig

    def create_weekday_comparison_plot(self) -> go.Figure:
        """Create a comparison plot showing all weekdays with 14 curves (7 days × 2 directions)."""

        metric_name = 'traffic_flow_rate_per_minute'
        if metric_name not in self.weekday_stats:
            return None

        # Create single plot for comparison
        fig = go.Figure()

        # Color scheme: consistent with other plots (blue=left, orange=right)
        # Use transparency/hue to distinguish weekdays (lighter) vs weekends (darker)
        def get_colors(weekday, direction):
            if direction == 'left':
                # Blue for left direction
                if weekday in ['Saturday', 'Sunday']:
                    return '#1f77b4'  # Darker blue for weekends
                else:
                    return '#aec7e8'  # Lighter blue for weekdays
            else:
                # Orange for right direction
                if weekday in ['Saturday', 'Sunday']:
                    return '#ff7f0e'  # Darker orange for weekends
                else:
                    return '#ffbb78'  # Lighter orange for weekdays

        # Process each weekday
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
                common_times = np.arange(0, 1440, 5)  # Every 5 minutes
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
                    std_values = np.std(interpolated_values, axis=0)

                    # Convert minutes to time strings for hover
                    time_strings = []
                    for minutes in common_times:
                        hours = int(minutes // 60)
                        mins = int(minutes % 60)
                        if hours == 0:
                            time_str = f"12:{mins:02d} AM"
                        elif hours < 12:
                            time_str = f"{hours}:{mins:02d} AM"
                        elif hours == 12:
                            time_str = f"12:{mins:02d} PM"
                        else:
                            time_str = f"{hours-12}:{mins:02d} PM"
                        time_strings.append(time_str)

                    # Mean line for this weekday/direction
                    color = get_colors(weekday, direction)

                    fig.add_trace(
                        go.Scatter(
                            x=common_times,
                            y=mean_values,
                            mode='lines',
                            name=f"{weekday} {direction.title()}",
                            line=dict(color=color, width=2),  # Removed line style, using color only
                            hovertemplate=f"<b>{weekday} - {direction.title()}</b><br>" +
                                        "Time: %{customdata}<br>" +
                                        "Mean: %{y:.1f} vehicles/min<br>" +
                                        "Std: " + f"{np.mean(std_values):.1f}<br>" +
                                        "<extra></extra>",
                            customdata=time_strings
                        )
                    )

        # Larger layout for comparison plot (double width)
        fig.update_layout(
            title=dict(
                text="Weekday Traffic Flow Comparison",
                x=0.5,
                font=dict(size=16)
            ),
            xaxis_title="Time",
            yaxis_title="Flow Rate (vehicles/min)",
            hovermode='x unified',
            template='plotly_white',
            width=1000,  # Double width to occupy two tiles
            height=480,  # Same height as other plots
            margin=dict(l=50, r=150, t=50, b=80),  # Extra right margin for legend
            legend=dict(
                orientation="v",  # Vertical legend on the right
                yanchor="top",
                y=1,  # Top of plot area
                xanchor="left",
                x=1.02,  # Position to the right of plot
                font=dict(size=9),  # Readable font for 14 items
                itemsizing='constant',
                itemwidth=30,
                bgcolor='rgba(255,255,255,0.8)',  # Semi-transparent background
                bordercolor='rgba(0,0,0,0.2)',
                borderwidth=1
            )
        )

        # Time axis with actual time format
        fig.update_xaxes(
            tickmode='array',
            tickvals=[0, 120, 240, 360, 480, 600, 720, 840, 960, 1080, 1200, 1320, 1440],
            ticktext=['12AM', '2AM', '4AM', '6AM', '8AM', '10AM', '12PM', '2PM', '4PM', '6PM', '8PM', '10PM', '12AM'],
            tickfont=dict(size=9),
            tickangle=45
        )

        fig.update_yaxes(
            tickfont=dict(size=10)
        )

        return fig

def main():
    """Generate embedded-friendly plots."""
    print("Creating embedded-friendly traffic pattern plots...")
    
    generator = EmbeddedPlotGenerator()
    
    if not generator.load_cached_data():
        print("Failed to load cached data")
        return
    
    generator.preprocess_data()
    generator.segment_by_days()
    generator.calculate_weekday_statistics()
    
    print("Creating embedded plots...")

    # Generate individual weekday plots
    for weekday in WEEKDAYS:
        fig = generator.create_embedded_weekday_plot(weekday)
        if fig:
            filename = f"traffic_flow_rate_per_minute_{weekday.lower()}_pattern.html"
            filepath = PLOTS_DIR / filename

            # Save with embedded-friendly configuration
            fig.write_html(
                filepath,
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
                    'responsive': True
                }
            )
            print(f"Updated {weekday} embedded plot: {filepath}")

    # Generate weekday comparison plot
    comparison_fig = generator.create_weekday_comparison_plot()
    if comparison_fig:
        filename = "traffic_flow_rate_weekday_comparison.html"
        filepath = PLOTS_DIR / filename

        comparison_fig.write_html(
            filepath,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
                'responsive': True
            }
        )
        print(f"Updated weekday comparison plot: {filepath}")

    print("Embedded plots updated successfully!")

if __name__ == "__main__":
    main()
