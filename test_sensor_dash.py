import time
from datetime import datetime
import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objs as go
import collections
from modules.hardware import hw

# Initialize the Dash application
app = dash.Dash(__name__)

# Maintain a rolling window of the last 50 data points in memory
MAX_DATA_POINTS = 50
time_history = collections.deque(maxlen=MAX_DATA_POINTS)
ppm_history = collections.deque(maxlen=MAX_DATA_POINTS)

# Web Layout Architecture
app.layout = html.Div(
    style={'backgroundColor': '#1e1e2f', 'color': '#ffffff', 'padding': '20px', 'fontFamily': 'sans-serif'},
    children=[
        html.H1("MindfulMe Live Alcohol Sensor Diagnostic Dashboard", style={'textAlign': 'center', 'color': '#00d2ff'}),
        html.Div(
            id='live-value-display', 
            style={'textAlign': 'center', 'fontSize': '30px', 'margin': '20px', 'fontWeight': 'bold', 'color': '#ff4a5a'}
        ),
        
        # The interactive graph component
        dcc.Graph(id='live-alcohol-graph', animate=False),
        
        # Interval component to force a page refresh loop every 1000 milliseconds (1 second)
        dcc.Interval(
            id='graph-update-trigger',
            interval=1000,
            n_intervals=0
        )
    ]
)

# Live Data Processing Loop
@app.callback(
    [Output('live-alcohol-graph', 'figure'),
     Output('live-value-display', 'children')],
    [Input('graph-update-trigger', 'n_intervals')]
)
def update_dashboard_metrics(n):
    # Query your live hardware module directly
    try:
        live_ppm = hw.read_alcohol_ppm()
    except Exception as e:
        print(f"Error querying hardware layer: {e}")
        live_ppm = 0.0

    current_timestamp = datetime.now().strftime('%H:%M:%S')

    # Append new data to our rolling history buffers
    time_history.append(current_timestamp)
    ppm_history.append(live_ppm)

    # Build the Plotly real-time line graph configuration
    graph_data = go.Scatter(
        x=list(time_history),
        y=list(ppm_history),
        name='Alcohol Content',
        mode='lines+markers',
        line=dict(color='#00d2ff', width=3),
        marker=dict(size=6, color='#ff4a5a')
    )

    graph_layout = go.Layout(
        xaxis=dict(range=[0, MAX_DATA_POINTS], title="Timestamp", gridcolor='#2e2e3f'),
        yaxis=dict(range=[0.0, 2.0], title="Alcohol Concentration (ppm)", gridcolor='#2e2e3f'),
        plot_bgcolor='#1e1e2f',
        paper_bgcolor='#1e1e2f',
        font=dict(color='#ffffff'),
        margin=dict(l=50, r=50, t=30, b=50)
    )

    display_text = f"Current Real-Time Sensor Reading: {live_ppm:.4f} ppm"

    return {'data': [graph_data], 'layout': graph_layout}, display_text

if __name__ == '__main__':
    print("🚀 Starting local diagnostic server on http://127.0.0.1:8050 ...")
    print("Press Ctrl+C to terminate the session.")
    # Run the server locally
    app.run(debug=True, host='0.0.0.0', port=8050)
