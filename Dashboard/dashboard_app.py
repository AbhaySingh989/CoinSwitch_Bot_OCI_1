from flask import Flask, jsonify, render_template, request
import pandas as pd
import uuid
import threading
import pytz
from analysis_engine import (
    get_scorecard_kpis, 
    get_pnl_charts_data, 
    get_all_trades_data,
    get_insights_data,
    get_daily_win_rate_data,
    get_daily_completed_positions_data,
    get_symbol_performance,
    run_sell_strategy_optimization,
    run_full_strategy_optimization,
    get_buy_strategy_data,
    get_peak_concurrent_positions_data
)

# App Configuration
app = Flask(__name__)
IST = pytz.timezone('Asia/Kolkata')

# In-memory store for optimization job results
optimization_jobs = {}


@app.route('/')
def home():
    """Renders the main dashboard page."""
    return render_template('index.html')

# --- Data Endpoints ---

@app.route('/api/scorecard')
def get_scorecard_data():
    data = get_scorecard_kpis()
    data['last_updated'] = pd.Timestamp.now(tz=IST).isoformat()
    return jsonify(data)

@app.route('/api/pnl_charts')
def get_pnl_chart_data_route():
    period = request.args.get('period', 'D')
    data = get_pnl_charts_data(period)
    return jsonify(data)

@app.route('/api/all_trades')
def get_all_trades_route():
    data = get_all_trades_data()
    return jsonify(data)

@app.route('/api/insights')
def get_insights_route():
    data = get_insights_data()
    return jsonify(data)

@app.route('/api/daily_win_rate')
def get_daily_win_rate_route():
    period = request.args.get('period', 'D')
    data = get_daily_win_rate_data(period)
    return jsonify(data)

@app.route('/api/daily_completed_positions')
def get_daily_completed_positions_route():
    period = request.args.get('period', 'D')
    data = get_daily_completed_positions_data(period)
    return jsonify(data)

@app.route('/api/symbol_performance')
def get_symbol_performance_route():
    data = get_symbol_performance()
    return jsonify(data)

@app.route('/api/buy_strategy_data')
def get_buy_strategy_data_route():
    period = request.args.get('period', 'D')
    data = get_buy_strategy_data(period)
    return jsonify(data)

@app.route('/api/peak_concurrent_positions')
def get_peak_concurrent_positions_route():
    period = request.args.get('period', 'D')
    data = get_peak_concurrent_positions_data(period)
    return jsonify(data)

# --- Optimization Endpoints ---

def _parse_param_string(param_string, default_values):
    if not param_string:
        return default_values
    try:
        return [float(x.strip()) for x in param_string.split(',')]
    except ValueError:
        return default_values

def run_optimization_in_background(job_id, analysis_function, params):
    """Wrapper to run the specified optimization and store results."""
    print(f"Starting optimization for job_id: {job_id} with function {analysis_function.__name__}")
    
    # Pass parameters to the analysis function
    results = analysis_function(**params)
    
    optimization_jobs[job_id] = results
    print(f"Finished optimization for job_id: {job_id}")

@app.route('/api/run_sell_optimization', methods=['POST'])
def run_sell_optimization_route():
    job_id = str(uuid.uuid4())
    optimization_jobs[job_id] = {"status": "pending", "progress": {"current": 0, "total": 1, "eta": "Calculating..."}}
    
    # Default parameters for sell-side optimization
    default_tpp = [2, 2.5, 3, 3.5, 4, 5, 7, 10, 12, 15]
    default_tslp = [3, 3.5, 4, 5, 6, 7, 8]
    default_ptp = [1, 1.5, 2, 2.5, 3]

    # Parse parameters from request, use defaults if not provided or invalid
    req_data = request.json
    tpp_values = _parse_param_string(req_data.get('tpp'), default_tpp)
    tslp_values = _parse_param_string(req_data.get('tslp'), default_tslp)
    ptp_values = _parse_param_string(req_data.get('ptp'), default_ptp)

    params = {
        'TAKE_PROFIT_PERCENTAGES': tpp_values,
        'TRAILING_STOP_LOSS_PERCENTAGES': tslp_values,
        'PROFIT_TRAIL_PERCENTAGES': ptp_values
    }

    thread = threading.Thread(target=run_optimization_in_background, args=(job_id, run_sell_strategy_optimization, params))
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "started"})

@app.route('/api/run_full_optimization', methods=['POST'])
def run_full_optimization_route():
    job_id = str(uuid.uuid4())
    optimization_jobs[job_id] = {"status": "pending", "progress": {"current": 0, "total": 1, "eta": "Calculating..."}}
    
    # Default parameters for full optimization
    default_momentum = [3.5, 4, 5]
    default_wick = [0.75, 1.0, 1.5]
    default_tpp = [3, 5, 8, 12]
    default_tslp = [3, 5, 8]
    default_ptp = [1.5, 2, 3]

    # Parse parameters from request, use defaults if not provided or invalid
    req_data = request.json
    momentum_values = _parse_param_string(req_data.get('momentum'), default_momentum)
    wick_values = _parse_param_string(req_data.get('wick'), default_wick)
    tpp_values = _parse_param_string(req_data.get('tpp'), default_tpp)
    tslp_values = _parse_param_string(req_data.get('tslp'), default_tslp)
    ptp_values = _parse_param_string(req_data.get('ptp'), default_ptp)

    params = {
        'BULLISH_MOMENTUM_PERC': momentum_values,
        'BULLISH_WICK_PERC': wick_values,
        'TAKE_PROFIT_PERCENTAGES': tpp_values,
        'TRAILING_STOP_LOSS_PERCENTAGES': tslp_values,
        'PROFIT_TRAIL_PERCENTAGES': ptp_values
    }

    thread = threading.Thread(target=run_optimization_in_background, args=(job_id, run_full_strategy_optimization, params))
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "started"})

@app.route('/api/optimization_status/<job_id>')
def get_optimization_status_route(job_id):
    result = optimization_jobs.get(job_id, {})
    if result.get("status") == "pending":
        return jsonify({"status": "pending", "progress": result.get("progress", {"current": 0, "total": 1, "eta": "Calculating..."})})
    
    # Check for errors returned by the analysis engine
    if 'error' in result:
        return jsonify({"status": "error", "message": result['error']})

    return jsonify({"status": "complete", "data": result})


if __name__ == '__main__':
    app.run(debug=True, port=5001)