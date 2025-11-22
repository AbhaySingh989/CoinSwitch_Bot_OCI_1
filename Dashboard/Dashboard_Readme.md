# Trading Performance Dashboard

---

## 1. Description

This project is a local, web-based dashboard designed to provide comprehensive performance analysis and strategy optimization for the associated cryptocurrency trading bot. It connects to the bot's local `Crypto_Data.db` database to generate insights, visualize performance, and run powerful backtesting simulations to refine trading parameters.

The entire application runs locally on your machine and is accessed through a web browser. It is designed for static analysis of historical data, with a manual refresh capability to load the latest trading results.

## 2. Key Features

The dashboard is organized into three main sections:

### 2.1. Performance Scorecard

A high-level overview of the most critical Key Performance Indicators (KPIs):
- **Total Realized P&L:** The net profit or loss from all completed trades.
- **Win Rate:** The percentage of completed trades that were profitable.
- **Average Holding Time:** The mean duration, in minutes, from a position's entry to its exit.
- **Completed Positions:** A count of all trades that have a corresponding buy and sell signal.
- **Open Positions:** A count of all buy signals that have not yet been sold.
- **Total Commission:** The total amount of commission incurred across all trades.
- **Maximum Drawdown:** The largest peak-to-trough decline in the cumulative P&L curve, indicating the biggest paper loss experienced.

### 2.2. Detailed Analysis

An interactive section to drill down into performance drivers:
- **Daily & Cumulative P&L Charts:** A bar chart showing profit/loss for each day and a line chart showing the P&L accumulating over time.
- **Daily Win Rate Chart:** Visualizes the percentage of profitable trades on a daily, weekly, or monthly basis.
- **Daily Completed Positions Chart:** Shows the number of completed trades over time, aggregated daily, weekly, or monthly.
- **Buy Strategy Performance Chart:** Analyzes the effectiveness of different buy strategy parameters, showing trade counts and P&L.
- **Peak Concurrent Positions Chart:** Displays the maximum number of open positions at any given time, aggregated daily, weekly, or monthly.
- **Profitable & Losing Trades Tables:** Two detailed tables listing every winning and losing trade, including the symbol, entry/exit prices, final P&L, holding time, and the reason for the exit (e.g., 'Trailing Stop-Loss').
- **Symbol Performance Table:** A summary table that aggregates performance by each cryptocurrency symbol, showing total P&L, win rate, and trade count for each.

### 2.3. Strategy Optimization

A powerful backtesting engine to find the optimal trading strategy based on historical data. Two modes are available:

- **Sell-Side Optimization:** A quick simulation that uses your bot's actual historical buy trades and runs a grid search to find the optimal combination of sell-strategy parameters (`TAKE_PROFIT_PERCENTAGE`, `TRAILING_STOP_LOSS_PERCENTAGE`, `PROFIT_TRAIL_PERCENTAGE`) that would have yielded the highest possible P&L for those specific trades.

- **Full (Buy & Sell) Optimization:** A highly comprehensive, but more time-intensive, simulation. This engine simulates your entire trading strategy from scratch. It runs a grid search over every combination of **both buy-side and sell-side parameters** to find the single, globally optimal strategy. The results include a detailed breakdown of every strategy tested, allowing for deep analysis of risk vs. reward.

---

## 3. Installation & Setup

Follow these steps to set up and run the dashboard. These commands should be run from the project's root directory (`C:\Abhay\CoinSwitch_Bot`).

### Prerequisites
- Python 3.8+ installed.
- The trading bot has been run at least once to generate the `Crypto_Data.db` file.

### Step 1: Activate the Virtual Environment

Activate the project's existing virtual environment to keep dependencies isolated.

```bash
venv\Scripts\activate
```

### Step 2: Install Dependencies

Install the required Python packages for the dashboard. You only need to do this once.

```bash
pip install -r Dashboard/requirements.txt
```

---

## 4. How to Run and Use the Dashboard

### Step 1: Start the Server

With your virtual environment still active, run the dashboard's Flask application.

```bash
python Dashboard/dashboard_app.py
```

You will see output in your terminal indicating that the server is running, typically on port 5001.

### Step 2: Access in Browser

Open your web browser and navigate to the following address:

[http://127.0.0.1:5001](http://127.0.0.1:5001)

### Step 3: Using the Dashboard

- **Viewing Data:** The dashboard will automatically load the latest data from the database when it first opens.
- **Refreshing Data:** To load new trades that have occurred since you opened the dashboard, click the **"Refresh Data"** button at the top right. The "Last updated" timestamp will confirm when the analysis was last run.
- **Timeframe Filters:** Use the "Daily", "Weekly", and "Monthly" buttons to change the aggregation period for time-series charts (e.g., P&L, Win Rate, Completed Positions).
- **Running Optimization:** To run a strategy optimization, click one of the buttons in the "Strategy Optimization" section. Be aware that the **Full Optimization** process is computationally intensive and may take several minutes to complete. A status indicator will show that the analysis is in progress. Once complete, the results will be displayed automatically.

---

## 5. Project Architecture

The dashboard is contained within the `Dashboard/` directory and consists of these key files:

- `dashboard_app.py`: The main Flask application file. It handles web page routing and the API endpoints that serve data to the frontend.
- `analysis_engine.py`: A Python module that contains all the logic for connecting to the database, performing calculations with `pandas`, and running the optimization simulations.
- `templates/index.html`: The single HTML file that defines the structure and layout of the dashboard.
- `static/style.css`: The stylesheet for custom dashboard styling.
- `static/main.js`: The core JavaScript file that handles all frontend interactivity, such as fetching data from the API, rendering charts, populating tables, and managing the optimization process.
- `Dashboard_Readme.md`: This documentation file.
- `requirements.txt`: A list of the Python dependencies required for the dashboard.