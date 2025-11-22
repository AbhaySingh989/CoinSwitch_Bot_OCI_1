# Epic: Interactive Dashboard for Trading Bot Performance Analysis & Strategy Optimization

**Epic Owner:** Super Boss
**Date:** August 18, 2025

**Description:** This epic covers the development of a comprehensive, local web-based dashboard to analyze, visualize, and optimize the trading bot's performance. The dashboard will provide at-a-glance KPIs, detailed drill-downs into profitability, and a powerful backtesting engine to systematically refine trading strategy parameters using historical data from the local `Crypto_Data.db` database.

---

## Component 1: Core Dashboard Foundation & UI
Status: Complete

### User Stories:

#### US-D1.1: As a developer, I want to set up the Flask application structure so that the project is organized and scalable.
**Status:** Complete

#### US-D1.2: As a user, I want a clean, responsive dashboard UI so that I can easily view analytics on different screen sizes.
**Status:** Complete

#### US-D1.3: As a user, I want to see when the data was last computed so that I am confident I am looking at a current analysis.
**Status:** Complete

---

## Component 2: Top-Level Performance Scorecard (Section 1)
Status: Complete

### User Stories:

#### US-D2.1: As a user, I want to see all essential KPIs in a clean, card-based format so that I can quickly assess overall performance.
**Status:** Complete

---

## Component 3: Detailed Performance Analysis (Section 2)
Status: Complete

### User Stories:

#### US-D3.1: As a user, I want to see a daily breakdown of P&L so that I can understand performance trends over time.
**Status:** Complete

#### US-D3.2: As a user, I want to analyze my losing trades so that I can identify common failure patterns.
**Status:** Complete

#### US-D3.3: As a user, I want to analyze my profitable trades so that I can understand what a successful trade looks like.
**Status:** Complete

#### US-D3.4: As a user, I want to see a performance summary for each trading symbol so that I can know which pairs are most/least profitable.
**Status:** Complete

---

## Component 4: Strategy Optimization Engine (Section 3)
Status: Complete

### User Stories:

#### US-D4.1: As a user, I want to run a "grid search" to find the optimal Sell Strategy parameters so that I can improve my exit logic.
**Status:** Complete

#### US-D4.2: As a user, I want to run an integrated grid search for both Buy and Sell strategies so that I can find the globally optimal parameter set.
**Description:** Extend the backtesting engine to simultaneously optimize buy-side parameters (e.g., 'Bullish Momentum' thresholds) and sell-side parameters.
**Status:** Complete

---

## Component 5: Timezone and Aggregation Enhancements
Status: Complete

### User Stories:

#### US-D5.1: As a user, I want all dashboard timestamps and daily P&L aggregations to be displayed in Indian Standard Time (IST) and aggregated by the buy date, so that I have a consistent and relevant view of my trading performance.
**Description:** Modify the dashboard's backend and frontend to ensure all displayed timestamps (e.g., "Last updated") and daily P&L aggregations are based on Indian Standard Time (IST). The daily P&L chart should aggregate profits and losses based on the `Signal_Timestamp_buy` rather than the `Signal_Timestamp_sell`.
**Acceptance Criteria:**
*   The "Last updated" timestamp on the dashboard accurately reflects the IST time.
*   The daily P&L chart correctly aggregates P&L by the `Signal_Timestamp_buy` in IST.
*   All other relevant timestamps displayed on the dashboard (if any) are in IST.
*   The underlying data processing for daily P&L uses the `Signal_Timestamp_buy`.
**Status:** Complete

---

# Epic: Dashboard UI/UX and Insights Overhaul

**Description:** Overhaul the dashboard to improve its visual appeal, usability, and, most importantly, to provide the user with actionable insights for data-driven decision-making. This involves a modernized UI, new insightful charts, and a powerful, interactive table for deep trade analysis.

---

## Component 6: Modernized Look and Feel
Status: Complete

### User Stories:

#### US-D6.1: As a user, I want the dashboard to have a clean, modern, and visually appealing design so that it's enjoyable to use and easy to read.
**Acceptance Criteria:**
*   The dashboard uses a modern, clean font (e.g., 'Inter' or 'Roboto').
*   A new, professional color palette is implemented.
*   The layout is spacious and well-organized, with clear visual separation between sections.
*   Icons are used to enhance scannability.
*   The UI is responsive and works well on different screen sizes.
**Status:** Complete

---

## Component 7: Enhanced Scorecard
Status: Complete

### User Stories:

#### US-D7.1: As a user, I want to see the key performance indicators (KPIs) in a visually distinct and easy-to-read scorecard at the top of the dashboard.
**Acceptance Criteria:**
*   Each KPI is displayed in its own "card".
*   Each card includes an icon, the KPI value, and a clear label.
*   The scorecard is prominently displayed at the top of the dashboard.
**Status:** Complete

---

## Component 8: New "Insights" Section
Status: Complete

### User Stories:

#### US-D8.1: As a user, I want to see a chart that shows my P&L broken down by the exit reason so that I can understand which parts of my exit strategy are most and least effective.
**Acceptance Criteria:**
*   A bar chart is added to the dashboard.
*   The chart displays the total P&L for each unique `Exit Reason`.
*   The chart is clearly labeled and easy to understand.
**Status:** Complete

#### US-D8.2: As a user, I want to see a distribution of holding periods for my trades so that I can identify if there's an optimal trade duration for my strategy.
**Acceptance Criteria:**
*   A histogram or bar chart is added to the dashboard.
*   The chart shows the frequency of trades across different holding period buckets (e.g., 0-1h, 1-4h, 4-12h, etc.).
*   The chart preferably distinguishes between profitable and losing trades.
**Status:** Complete

#### US-D8.3: As a user, I want to see an "Average P&L by Holding Period" chart and have the layout adjusted so that I can better analyze the relationship between holding time and profitability.
*   **Status:** Complete

---

## Component 9: "All Trades" Interactive Table
Status: Complete

### User Stories:

#### US-D9.1: As a user, I want to see all my trades (both profitable and losing) in a single, comprehensive table so that I can analyze my performance in one place.
**Acceptance Criteria:**
*   The two separate trade tables are replaced with a single "All Trades" table.
*   The table is placed within a collapsible section, which is collapsed by default.
*   The table includes all the new, specified columns: `Buy Date`, `Symbol`, `Entry Date/Time`, `Exit Date/Time`, `Entry Price`, `Exit Price`, `P&L`, `High Water Mark (Signal)`, `Highest Price During Hold (Market)`, `Peak Capture %`, `Highest % Change`, `Lowest Price During Hold`, `Lowest % Change`, `Exit Reason`.
**Status:** Complete

#### US-D9.2: As a user, I want to be able to interact with the "All Trades" table to filter, sort, and search for specific trades so that I can conduct detailed, ad-hoc analysis.
**Acceptance Criteria:**
*   Controls are added to filter the table by `Symbol`, date range, and `Exit Reason`.
*   All columns in the table are sortable.
*   A search box is provided to filter the table based on user input.
*   Rows are color-coded based on P&L (green for profit, red for loss).
**Status:** Complete

#### US-D9.3: As a user, I want the "HMW (Signal)" column to correctly display the high-water mark from the buy signal so that I can accurately assess trade data.
*   **Status:** Complete

# Epic: Advanced Analytics and Usability Enhancements

**Description:** A comprehensive upgrade to the dashboard focused on delivering deeper, more actionable insights, improving financial accuracy, and enhancing long-term usability. This epic introduces advanced performance metrics for buy strategies, visualizes capital allocation, and implements dynamic UI controls for handling larger datasets.

---

## Component 10: Enhanced Chart Readability
**Status:** Complete

### User Stories:

#### US-D10.1: As a user, I want to see data labels on all charts so that I can quickly read exact values without hovering.
*   **Status:** Complete

---

## Component 11: Buy Strategy Performance Analysis
**Status:** Complete

### User Stories:

#### US-D11.1: As a user, I want to see a "Buy Strategy Performance" chart so that I can compare the effectiveness of different buy strategies.
*   **Description:** A chart that breaks down performance by buy signal reason (e.g., 'Bullish Momentum', 'Intra-candle'). It will show the total number of closed positions and the total P&L for each strategy.
*   **Status:** Complete

#### US-D11.2: As a user, I want to see a "Buy Strategy P&L Over Time" chart so that I can track the cumulative performance of each buy strategy independently.
*   **Status:** Complete

---

## Component 12: Capital Allocation Insights
**Status:** Complete

### User Stories:

#### US-D12.1: As a user, I want to see a "Peak Concurrent Open Positions" trend chart so that I can understand my maximum capital allocation over time.
*   **Status:** Complete

---

## Component 13: Dynamic Time Aggregation
Status: Complete

### User Stories:

#### US-D13.1: As a user, I want to switch the time aggregation for all trend charts between Daily, Weekly, and Monthly views so that the dashboard remains readable as data grows over time.
*   **Status:** Complete

#### US-D13.2: As a user, I want the weekly and monthly time aggregations to be calculated correctly so that I can analyze trends over standard, predictable periods.
*   **Status:** Complete

---

## Component 14: Financial Accuracy
**Status:** Complete

### User Stories:

#### US-D14.1: As a user, I want to see the "Total Commission Incurred" as a separate KPI on the scorecard so that I can understand my total trading costs without altering the gross P&L figures.
*   **Description:** This involves calculating the total commission (0.4% of the buy value + 0.4% of the sell value for every trade) and displaying it as a new card at the top of the dashboard. The existing P&L calculations will not be modified.
*   **Status:** Complete

---

## Component 15: UI/UX Enhancements
Status: In Progress

### User Stories:

#### US-D15.1: As a user, I want the "All Trades" table to be paginated so that the dashboard loads quickly and remains responsive even with thousands of trades.
*   **Description:** Implement server-side pagination for the "All Trades" table. The backend will handle slicing the data, and the frontend will display page navigation controls.
*   **Status:** In Progress

#### US-D15.2: As a user, I want the dashboard to have a dark mode toggle so that I can switch to a less bright interface for comfortable viewing in low-light environments.
*   **Status:** Planning

#### US-D15.3: As a user, I want the dashboard to automatically refresh every 5 minutes so that I can see the latest performance without manual intervention.
*   **Status:** Planning

#### US-D15.4: As a user, I want to be able to export the "All Trades" table to a CSV file so that I can perform my own offline analysis in tools like Excel.
*   **Status:** Planning

#### US-D15.5: As a user, I want all chart gridlines removed and chart heights standardized so that the dashboard has a cleaner and more consistent visual appearance.
*   **Status:** Complete

---

## Component 16: Advanced Strategy Optimization Insights
**Status:** Planning

### User Stories:

#### US-D16.1: As a user, I want the Strategy Optimization results to be presented in a heatmap so that I can easily visualize the relationship between different parameter combinations and their resulting P&L.
*   **Status:** Planning

#### US-D16.2: As a user, I want to see the "Max Drawdown" and "Win Rate" for each tested strategy in the optimization results so that I can make a more informed decision based on risk and consistency, not just P&L.
*   **Status:** Planning

---

## Component 17: Real-time Open Position Monitoring
**Status:** Planning

### User Stories:

#### US-D17.1: As a user, I want to see a real-time view of my open positions, including their current unrealized P&L, so that I can monitor my active trades directly from the dashboard.
*   **Description:** This will require the dashboard to periodically fetch the latest market prices for symbols with open positions and calculate the current P&L.
*   **Status:** Planning

---

## Component 18: Interactive and Transparent Optimization
Status: In Progress

### User Stories:

#### US-D18.1: As a user, I want to be able to input my own parameter ranges for the sell-side and full strategy optimizations so that I can test my own specific hypotheses.
*   **Status:** In Progress

#### US-D18.2: As a user, I want to see the progress of a running optimization (e.g., "Combination 50 of 500") so that I have a clear idea of how long the process will take.
*   **Status:** In Progress


## Issue 1:
✦ The dashboard is now visible, which is progress! However, the optimization still fails with the same Invalid comparison
  between dtype=datetime64[ns] and Timestamp error.

  Root Cause Analysis:

  This error occurs because Pandas cannot directly compare "naive" (timezone-unaware) datetime objects with
  "timezone-aware" datetime objects.

  In analysis_engine.py:
   * _get_completed_trades() correctly converts Signal_Timestamp to timezone-aware IST.
   * However, within run_sell_strategy_optimization and run_full_strategy_optimization, candles_df['candle_start_time']
     is converted to datetime but not localized to a timezone. When candles_df['candle_start_time'] (naive) is compared
     with trade['Signal_Timestamp_buy'] (timezone-aware IST), the error is triggered.

  The Fix: I need to ensure candles_df['candle_start_time'] is also timezone-aware and in IST before any comparisons
  are made.

  Action Plan:

   1. [ ] Fix Optimization Error (`analysis_engine.py`):
       * Task 1.1: Read analysis_engine.py.
       * Task 1.2: In run_sell_strategy_optimization and run_full_strategy_optimization, modify the line that converts
         candle_start_time to explicitly localize it to UTC and then convert it to IST.
           * Change: candles_df['candle_start_time'] = pd.to_datetime(candles_df['candle_start_time'], unit='ms')
           * To: candles_df['candle_start_time'] = pd.to_datetime(candles_df['candle_start_time'],
             unit='ms').dt.tz_localize('UTC').dt.tz_convert(IST)
       * Task 1.3: Replace the modified functions.
   2. [ ] Silence `FutureWarning` (`analysis_engine.py`):
       * Task 2.1: Read analysis_engine.py.
       * Task 2.2: Add observed=False to the groupby call in get_insights_data that is causing the warning.
       * Task 2.3: Replace the modified function.
   3. [ ] Verify Dashboard Functionality:
       * Task 3.1: After fixing the above, ask the user to verify the dashboard.