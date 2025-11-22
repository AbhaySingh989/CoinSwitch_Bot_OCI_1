document.addEventListener('DOMContentLoaded', function() {

    // --- Element Selectors ---
    const scorecardContainer = document.getElementById('scorecard-container');
    const dataTimestamp = document.getElementById('data-timestamp');
    const refreshButton = document.getElementById('refresh-button');
    const allTradesBody = document.getElementById('all-trades-body');
    const allTradesTable = document.querySelector('.table');
    const sellOptimizationButton = document.getElementById('run-sell-optimization-button');
    const fullOptimizationButton = document.getElementById('run-full-optimization-button');
    const optimizationResultsContainer = document.getElementById('optimization-results');
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    const sidebar = document.getElementById('sidebar');
    const timeframeSelector = document.querySelector('.btn-group[aria-label="Timeframe Selector"]');

    // --- Chart Instances ---
    let dailyPnlChart = null;
    let cumulativePnlChart = null;
    let pnlByExitReasonChart = null;
    let holdingPeriodChart = null;
    let dailyWinRateChart = null;
    let dailyCompletedPositionsChart = null;
    let buyStrategyPerformanceChart = null;
    let buyStrategyTrendingChart = null;
    let peakConcurrentPositionsChart = null;
    let avgPnlByHoldingPeriodChart = null;

    // --- Data & State ---
    let allTradesData = [];
    let sortState = { key: 'entry_datetime', direction: 'desc' };
    let currentPeriod = 'D'; // Default period

    // --- Main Functions ---

    /**
     * Fetches all dashboard data and updates the UI.
     */
    function refreshAllData() {
        fetchScorecardData();
        fetchPnlChartsData();
        fetchInsightsData();
        fetchDailyWinRateData();
        fetchDailyCompletedPositionsData();
        fetchAllTradesData();
        fetchBuyStrategyData();
        fetchPeakConcurrentPositionsData();
    }

    /**
     * Fetches and displays scorecard data.
     */
    function fetchScorecardData() {
        dataTimestamp.textContent = 'Computing...';
        scorecardContainer.innerHTML = '';

        fetch('/api/scorecard')
            .then(response => response.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                const updatedDate = new Date(data.last_updated);
                dataTimestamp.textContent = `Last updated: ${updatedDate.toLocaleString()}`;

                let cardsHtml = '';
                cardsHtml += createKpiCard('Total Realized P&L', `${data.total_realized_pnl.toFixed(2)} USD`, 'fas fa-dollar-sign');
                cardsHtml += createKpiCard('Total Commission', `${data.total_commission_incurred.toFixed(2)} USD`, 'fas fa-file-invoice-dollar');
                cardsHtml += createKpiCard('Win Rate', `${data.win_rate.toFixed(2)} %`, 'fas fa-trophy');
                cardsHtml += createKpiCard('Avg. Holding Time', `${data.average_holding_period_minutes.toFixed(1)} min`, 'fas fa-clock');
                cardsHtml += createKpiCard('Completed Positions', data.total_completed_positions, 'fas fa-check-circle');
                cardsHtml += createKpiCard('Open Positions', data.total_open_positions, 'fas fa-folder-open');
                scorecardContainer.innerHTML = cardsHtml;
            })
            .catch(handleFetchError('scorecard', scorecardContainer, 7));
    }

    function fetchPnlChartsData() {
        fetch(`/api/pnl_charts?period=${currentPeriod}`)
            .then(response => response.json()).then(data => { if (data.error) throw new Error(data.error); renderPnlCharts(data); })
            .catch(error => console.error('Error fetching P&L chart data:', error));
    }

    function fetchInsightsData() {
        fetch('/api/insights')
            .then(response => response.json()).then(data => { 
                if (data.error) throw new Error(data.error); 
                renderPnlByExitReasonChart(data.pnl_by_exit_reason); 
                renderHoldingPeriodChart(data.holding_period_distribution); 
                renderAvgPnlByHoldingPeriodChart(data.pnl_by_holding_period);
            })
            .catch(error => console.error('Error fetching insights data:', error));
    }

    function fetchDailyWinRateData() {
        fetch(`/api/daily_win_rate?period=${currentPeriod}`)
            .then(response => response.json()).then(data => { if (data.error) throw new Error(data.error); renderDailyWinRateChart(data); })
            .catch(error => console.error('Error fetching daily win rate data:', error));
    }

    function fetchDailyCompletedPositionsData() {
        fetch(`/api/daily_completed_positions?period=${currentPeriod}`)
            .then(response => response.json()).then(data => { if (data.error) throw new Error(data.error); renderDailyCompletedPositionsChart(data); })
            .catch(error => console.error('Error fetching daily completed positions data:', error));
    }

    function fetchBuyStrategyData() {
        fetch(`/api/buy_strategy_data?period=${currentPeriod}`)
            .then(response => response.json()).then(data => { if (data.error) throw new Error(data.error); renderBuyStrategyCharts(data); })
            .catch(error => console.error('Error fetching buy strategy data:', error));
    }

    function fetchPeakConcurrentPositionsData() {
        fetch(`/api/peak_concurrent_positions?period=${currentPeriod}`)
            .then(response => response.json()).then(data => { if (data.error) throw new Error(data.error); renderPeakConcurrentPositionsChart(data); })
            .catch(error => console.error('Error fetching peak concurrent positions data:', error));
    }

    function fetchAllTradesData() {
        allTradesBody.innerHTML = '<tr><td colspan="13">Loading...</td></tr>';
        fetch('/api/all_trades')
            .then(response => response.json()).then(data => { if (data.error) throw new Error(data.error); allTradesData = data; sortAllTradesData(); renderAllTradesTable(); })
            .catch(handleFetchError('all trades', allTradesBody, 13));
    }

    // --- UI Rendering ---

    function renderAllTradesTable() {
        allTradesBody.innerHTML = '';
        if (allTradesData.length === 0) {
            allTradesBody.innerHTML = '<tr><td colspan="13">No trades to display.</td></tr>';
            return;
        }
        const tradesByDate = groupBy(allTradesData, 'buy_date');
        for (const date in tradesByDate) {
            const trades = tradesByDate[date];
            const dateRow = `<tr class="date-header" data-bs-toggle="collapse" data-bs-target="#trades-${date}"><td colspan="13"><i class="fas fa-calendar-alt"></i> ${date} (${trades.length} trades)</td></tr>`;
            allTradesBody.innerHTML += dateRow;
            trades.forEach(trade => {
                const tradeRow = `<tr id="trades-${date}" class="collapse ${trade.pnl > 0 ? 'table-success' : 'table-danger'}"><td>${trade.symbol}</td><td>${trade.entry_datetime}</td><td>${trade.exit_datetime}</td><td>${trade.hold_time_mins.toFixed(2)}</td><td>${trade.entry_price.toFixed(4)}</td><td>${trade.exit_price.toFixed(4)}</td><td>${trade.pnl.toFixed(1)}</td><td>${trade.high_water_mark_signal.toFixed(4)}</td><td>${trade.highest_price_market.toFixed(4)}</td><td>${trade.peak_capture_perc.toFixed(2)}%</td><td>${trade.highest_perc_change.toFixed(2)}%</td><td>${trade.lowest_perc_change.toFixed(2)}%</td><td>${trade.exit_reason}</td></tr>`;
                allTradesBody.innerHTML += tradeRow;
            });
        }
    }

    function sortAllTradesData() {
        allTradesData.sort((a, b) => {
            const aVal = a[sortState.key];
            const bVal = b[sortState.key];
            if (sortState.key.includes('datetime') || sortState.key.includes('date')) {
                const dateA = new Date(aVal); const dateB = new Date(bVal);
                if (dateA < dateB) return sortState.direction === 'asc' ? -1 : 1;
                if (dateA > dateB) return sortState.direction === 'asc' ? 1 : -1;
                return 0;
            }
            if (typeof aVal === 'number' && typeof bVal === 'number') {
                if (aVal < bVal) return sortState.direction === 'asc' ? -1 : 1;
                if (aVal > bVal) return sortState.direction === 'asc' ? 1 : -1;
                return 0;
            }
            if (aVal < bVal) return sortState.direction === 'asc' ? -1 : 1;
            if (aVal > bVal) return sortState.direction === 'asc' ? 1 : -1;
            return 0;
        });
    }

    function createKpiCard(title, value, icon) {
        return `<div class="col-xl-2 col-md-4 col-sm-6 mb-4"><div class="card scorecard-card h-100"><div class="card-body"><div class="icon"><i class="${icon}"></i></div><h6 class="card-title">${title}</h6><p class="card-text">${value}</p></div></div></div>`;
    }

    const chartOptions = {
        plugins: {
            datalabels: {
                anchor: 'end',
                align: 'top',
                formatter: (value) => Math.round(value),
                font: { weight: 'bold' }
            }
        },
        scales: {
            x: {
                offset: true,
                grid: { display: false }
            },
            y: {
                grid: { display: false }
            }
        }
    };

    function renderPnlCharts(data) {
        if(dailyPnlChart) dailyPnlChart.destroy();
        if(cumulativePnlChart) cumulativePnlChart.destroy();
        const dailyCtx = document.getElementById('daily-pnl-chart').getContext('2d');
        dailyPnlChart = new Chart(dailyCtx, { type: 'bar', data: { labels: data.labels, datasets: [{ label: 'Daily P&L (USD)', data: data.daily_pnl, backgroundColor: data.daily_pnl.map(pnl => pnl >= 0 ? 'rgba(75, 192, 192, 0.6)' : 'rgba(255, 99, 132, 0.6)') }] }, options: chartOptions });
        const cumulativeCtx = document.getElementById('cumulative-pnl-chart').getContext('2d');
        cumulativePnlChart = new Chart(cumulativeCtx, { type: 'line', data: { labels: data.labels, datasets: [{ label: 'Cumulative P&L (USD)', data: data.cumulative_pnl, fill: false, borderColor: 'rgb(75, 192, 192)', tension: 0.1 }] }, options: chartOptions });
    }

    function renderPnlByExitReasonChart(data) {
        if(pnlByExitReasonChart) pnlByExitReasonChart.destroy();
        const ctx = document.getElementById('pnl-by-exit-reason-chart').getContext('2d');
        pnlByExitReasonChart = new Chart(ctx, { type: 'bar', data: { labels: Object.keys(data), datasets: [{ label: 'Total P&L by Exit Reason', data: Object.values(data), backgroundColor: Object.values(data).map(pnl => pnl >= 0 ? 'rgba(40, 167, 69, 0.7)' : 'rgba(220, 53, 69, 0.7)') }] }, options: chartOptions });
    }

    function renderHoldingPeriodChart(data) {
        if(holdingPeriodChart) holdingPeriodChart.destroy();
        const ctx = document.getElementById('holding-period-chart').getContext('2d');
        const orderedLabels = ['0-1h', '1-4h', '4-12h', '12-24h', '1-2d', '2-7d', '>7d'];
        const mappedData = {};
        orderedLabels.forEach(label => { mappedData[label] = data[label] || 0; });
        holdingPeriodChart = new Chart(ctx, { type: 'bar', data: { labels: orderedLabels, datasets: [{ label: 'Number of Trades', data: orderedLabels.map(label => mappedData[label]), backgroundColor: 'rgba(0, 123, 255, 0.7)' }] }, options: { ...chartOptions, scales: { x: { title: { display: true, text: 'Holding Period Buckets' } } } } });
    }

    function renderAvgPnlByHoldingPeriodChart(data) {
        if(avgPnlByHoldingPeriodChart) avgPnlByHoldingPeriodChart.destroy();
        const ctx = document.getElementById('avg-pnl-by-holding-period-chart').getContext('2d');
        const orderedLabels = ['0-1h', '1-4h', '4-12h', '12-24h', '1-2d', '2-7d', '>7d'];
        const mappedData = {};
        orderedLabels.forEach(label => { mappedData[label] = data[label] || 0; });
        avgPnlByHoldingPeriodChart = new Chart(ctx, { type: 'bar', data: { labels: orderedLabels, datasets: [{ label: 'Average P&L (USD)', data: orderedLabels.map(label => mappedData[label]), backgroundColor: orderedLabels.map(label => (mappedData[label] || 0) >= 0 ? 'rgba(75, 192, 192, 0.6)' : 'rgba(255, 99, 132, 0.6)') }] }, options: { ...chartOptions, scales: { x: { title: { display: true, text: 'Holding Period Buckets' } } } } });
    }

    function renderDailyWinRateChart(data) {
        if(dailyWinRateChart) dailyWinRateChart.destroy();
        const ctx = document.getElementById('daily-win-rate-chart').getContext('2d');
        dailyWinRateChart = new Chart(ctx, { type: 'line', data: { labels: data.labels, datasets: [{ label: 'Daily Win Rate (%)', data: data.win_rate, fill: false, borderColor: 'rgb(255, 159, 64)', tension: 0.1 }] }, options: chartOptions });
    }

    function renderDailyCompletedPositionsChart(data) {
        if(dailyCompletedPositionsChart) dailyCompletedPositionsChart.destroy();
        const ctx = document.getElementById('daily-completed-positions-chart').getContext('2d');
        dailyCompletedPositionsChart = new Chart(ctx, { type: 'bar', data: { labels: data.labels, datasets: [{ label: 'Completed Positions', data: data.positions, backgroundColor: 'rgba(153, 102, 255, 0.6)' }] }, options: chartOptions });
    }

    function renderBuyStrategyCharts(data) {
        if(buyStrategyPerformanceChart) buyStrategyPerformanceChart.destroy();
        if(buyStrategyTrendingChart) buyStrategyTrendingChart.destroy();
        const summaryCtx = document.getElementById('buy-strategy-performance-chart').getContext('2d');
        buyStrategyPerformanceChart = new Chart(summaryCtx, { type: 'bar', data: { labels: data.strategy_summary.labels, datasets: [{ label: 'Trade Count', data: data.strategy_summary.trade_counts, yAxisID: 'y', backgroundColor: 'rgba(54, 162, 235, 0.6)', datalabels: { anchor: 'center', align: 'center', color: 'white', font: { weight: 'bold' } } }, { label: 'Total PnL (USD)', data: data.strategy_summary.pnl_values, yAxisID: 'y1', type: 'line', borderColor: 'rgba(255, 99, 132, 1)', tension: 0.1, datalabs: { anchor: 'end', align: 'top', color: 'rgba(255, 99, 132, 1)', offset: 8 } }] }, options: { ...chartOptions, scales: { y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Trade Count' } }, y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'PnL (USD)' }, grid: { drawOnChartArea: false } } } } });
        const trendingCtx = document.getElementById('buy-strategy-trending-chart').getContext('2d');
        buyStrategyTrendingChart = new Chart(trendingCtx, { type: 'line', data: { labels: data.strategy_trending.labels, datasets: data.strategy_trending.datasets.map((ds, i) => ({ ...ds, borderColor: `hsl(${i * 60}, 70%, 50%)`, tension: 0.1 })) }, options: chartOptions });
    }

    function renderPeakConcurrentPositionsChart(data) {
        if(peakConcurrentPositionsChart) peakConcurrentPositionsChart.destroy();
        const ctx = document.getElementById('peak-concurrent-positions-chart').getContext('2d');
        peakConcurrentPositionsChart = new Chart(ctx, { type: 'line', data: { labels: data.labels, datasets: [{ label: 'Peak Concurrent Open Positions', data: data.data, borderColor: 'rgba(255, 206, 86, 1)', fill: true, backgroundColor: 'rgba(255, 206, 86, 0.2)', tension: 0.1 }] }, options: chartOptions });
    }

    // --- Optimization Rendering ---
    // --- Optimization Rendering ---
    function handleOptimization(endpoint, button, renderer, isFullOptimization = false) {
        button.disabled = true; 
        sellOptimizationButton.disabled = true;
        fullOptimizationButton.disabled = true;

        let params = {};
        if (isFullOptimization) {
            params = {
                momentum: document.getElementById('full-momentum').value,
                wick: document.getElementById('full-wick').value,
                tpp: document.getElementById('full-tpp').value,
                tslp: document.getElementById('full-tslp').value,
                ptp: document.getElementById('full-ptp').value
            };
        } else {
            params = {
                tpp: document.getElementById('sell-tpp').value,
                tslp: document.getElementById('sell-tslp').value,
                ptp: document.getElementById('sell-ptp').value
            };
        }

        optimizationResultsContainer.innerHTML = `<div class="text-center"><div class="spinner-border" role="status"></div><p class="mt-2" id="optimization-progress-text">Running optimization... This may take several minutes.</p></div>`;

        fetch(endpoint, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        }).then(response => response.json()).then(result => {
            if (!result.job_id) throw new Error(result.message || 'Failed to start optimization job.');
            const jobId = result.job_id;
            const startTime = new Date();

            const interval = setInterval(() => {
                fetch(`/api/optimization_status/${jobId}`)
                    .then(response => response.json()).then(statusResult => {
                        if (statusResult.status === 'complete') {
                            clearInterval(interval);
                            button.disabled = false; 
                            sellOptimizationButton.disabled = false;
                            fullOptimizationButton.disabled = false;
                            renderer(statusResult.data);
                        } else if (statusResult.status === 'error') {
                            clearInterval(interval);
                            button.disabled = false; 
                            sellOptimizationButton.disabled = false;
                            fullOptimizationButton.disabled = false;
                            throw new Error(statusResult.message);
                        } else if (statusResult.status === 'running') {
                            const progressTextElement = document.getElementById('optimization-progress-text');
                            if (progressTextElement) {
                                const current = statusResult.progress.current;
                                const total = statusResult.progress.total;
                                const elapsedSeconds = (new Date() - startTime) / 1000;
                                const combinationsPerSecond = current > 0 ? elapsedSeconds / current : 0;
                                const remainingCombinations = total - current;
                                const etaSeconds = combinationsPerSecond > 0 ? remainingCombinations * combinationsPerSecond : 'N/A';

                                let etaMessage = '';
                                if (typeof etaSeconds === 'number') {
                                    const etaMinutes = Math.ceil(etaSeconds / 60);
                                    etaMessage = ` (ETA: ~${etaMinutes} min)`;
                                }
                                progressTextElement.textContent = `Running optimization... Processed ${current} of ${total} combinations${etaMessage}`;
                            }
                        }
                    })
                    .catch(err => { 
                        console.error('Polling error:', err); 
                        clearInterval(interval); 
                        button.disabled = false; 
                        sellOptimizationButton.disabled = false;
                        fullOptimizationButton.disabled = false;
                        optimizationResultsContainer.innerHTML = `<div class="alert alert-danger">Error checking optimization status: ${err.message}</div>`; 
                    });
            }, 2000); // Poll every 2 seconds
        }).catch(error => { 
            console.error('Error starting optimization:', error); 
            optimizationResultsContainer.innerHTML = `<div class="alert alert-danger">Failed to start optimization: ${error.message}</div>`; 
            button.disabled = false; 
            sellOptimizationButton.disabled = false;
            fullOptimizationButton.disabled = false;
        });
    }

    function renderSellOptimizationResults(data) {
        if (data.error) { optimizationResultsContainer.innerHTML = `<div class="alert alert-danger">Optimization failed: ${data.error}</div>`; return; }
        const improvement = data.optimized_pnl - data.original_pnl;
        const improvement_percent = data.original_pnl !== 0 ? (improvement / Math.abs(data.original_pnl)) * 100 : 0;
        optimizationResultsContainer.innerHTML = `<div class="card"><div class="card-header fw-bold text-white bg-primary">Sell-Side Strategy Optimization Complete</div><div class="card-body"><h5 class="card-title">Optimal Parameter Set - Sell Strategy</h5><ul class="list-group list-group-flush"><li class="list-group-item">Optimal Take-Profit Percentage: <strong>${data.best_params.tpp}%</strong></li><li class="list-group-item">Optimal Trailing Stop-Loss: <strong>${data.best_params.tslp}%</strong></li><li class="list-group-item">Optimal Profit-Trail Percentage: <strong>${data.best_params.ptp}%</strong></li></ul><hr><div class="row text-center"><div class="col-md-6"><h6>Original Strategy</h6><p>Total P&L: <span class="fw-bold ${data.original_pnl >= 0 ? 'text-success' : 'text-danger'}">${data.original_pnl.toFixed(2)} USD</span></p></div><div class="col-md-6"><h6>Optimized Strategy (Simulated)</h6><p>Projected P&L: <span class="fw-bold ${data.optimized_pnl >= 0 ? 'text-success' : 'text-danger'}">${data.optimized_pnl.toFixed(2)} USD</span></p></div></div><hr><h5 class="card-title text-center">Improvement Metrics</h5><p class="text-center fs-4">Net P&L Improvement: <span class="fw-bold text-success">+${improvement.toFixed(2)} USD (+${improvement_percent.toFixed(2)}%)</span></p></div></div>`;
    }

    function renderFullOptimizationResults(data) {
        if (!data || !data.summary || !data.details) { optimizationResultsContainer.innerHTML = `<div class="alert alert-danger">Error: Invalid data structure received from server.</div>`; return; }
        const summary = data.summary; const details = data.details;
        const summaryHtml = `<div class="card border-success"><div class="card-header fw-bold text-white bg-success">Full Strategy Optimization Complete</div><div class="card-body"><h5 class="card-title">Top Recommended Strategy</h5><ul class="list-group list-group-flush"><li class="list-group-item">Bullish Momentum: <strong>${summary.best_params.buy.momentum}%</strong></li><li class="list-group-item">Bullish Wick: <strong>${summary.best_params.buy.wick}%</strong></li></ul></div><div class="col-md-6"><h6>Sell Parameters</h6><ul class="list-group list-group-flush"><li class="list-group-item">Take-Profit: <strong>${summary.best_params.sell.tpp}%</strong></li><li class="list-group-item">Trailing Stop-Loss: <strong>${summary.best_params.sell.tslp}%</strong></li><li class="list-group-item">Profit-Trail: <strong>${summary.best_params.sell.ptp}%</strong></li></ul></div></div><hr><div class="row text-center mt-3"><div class="col-md-6"><h6>Original Strategy P&L</h6><p class="fs-5 ${summary.original_pnl >= 0 ? 'text-info' : 'text-danger'}">${summary.original_pnl.toFixed(2)} USD</p></div><div class="col-md-6"><h6>Optimized Strategy P&L</h6><p class="fs-5 fw-bold ${summary.best_pnl >= 0 ? 'text-success' : 'text-danger'}">${summary.best_pnl.toFixed(2)} USD</p></div></div></div></div>`;
        let detailsHtml = `<div class="card mt-4"><div class="card-header">Detailed Strategy Analysis</div><div class="card-body"><div class="table-responsive"><table class="table table-striped table-sm table-hover"><thead><tr><th>PnL (USD)</th><th>Win Rate (%)</th><th>Max Drawdown (USD)</th><th>Total Trades</th><th>Momentum %</th><th>Wick %</th><th>Take-Profit %</th><th>Trailing Stop %</th><th>Profit Trail %</th></tr></thead><tbody>`;
        details.forEach(run => { detailsHtml += `<tr><td class="fw-bold ${run.pnl >= 0 ? 'text-success' : 'text-danger'}">${run.pnl.toFixed(2)}</td><td>${run.win_rate.toFixed(2)}</td><td class="text-danger">${run.max_drawdown.toFixed(2)}</td><td>${run.trade_count}</td><td>${run.momentum_perc}</td><td>${run.wick_perc}</td><td>${run.tpp}</td><td>${run.tslp}</td><td>${run.ptp}</td></tr>`; });
        detailsHtml += `</tbody></table></div></div></div>`;
        optimizationResultsContainer.innerHTML = summaryHtml + detailsHtml;
    }

    function handleFetchError(context, element, colspan) {
        return error => { console.error(`Error fetching ${context}:`, error); const errorMsg = `<tr><td colspan="${colspan}" class="text-danger">Error loading data: ${error.message}</td></tr>`; if (element.tagName === 'TBODY') { element.innerHTML = errorMsg; } else { element.innerHTML = `<div class="col"><div class="alert alert-danger">Failed to load ${context}: ${error.message}</div></div>`; } };
    }

    function groupBy(array, key) {
        return array.reduce((result, currentValue) => { (result[currentValue[key]] = result[currentValue[key]] || []).push(currentValue); return result; }, {});
    }

    // --- Event Listeners ---
    refreshButton.addEventListener('click', refreshAllData);
    sidebarCollapse.addEventListener('click', () => sidebar.classList.toggle('active'));
    sellOptimizationButton.addEventListener('click', () => handleOptimization('/api/run_sell_optimization', sellOptimizationButton, renderSellOptimizationResults));
    fullOptimizationButton.addEventListener('click', () => handleOptimization('/api/run_full_optimization', fullOptimizationButton, renderFullOptimizationResults, true));
    allTradesTable.addEventListener('click', e => { if (e.target.matches('th[data-sort]')) { const sortKey = e.target.dataset.sort; if (sortState.key === sortKey) { sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc'; } else { sortState.key = sortKey; sortState.direction = 'asc'; } sortAllTradesData(); renderAllTradesTable(); } });
    timeframeSelector.addEventListener('change', e => {
        if (e.target.name === 'timeframe') {
            currentPeriod = e.target.value;
            // Re-fetch data for all time-sensitive charts
            fetchPnlChartsData();
            fetchDailyWinRateData();
            fetchDailyCompletedPositionsData();
            fetchBuyStrategyData();
            fetchPeakConcurrentPositionsData();
        }
    });

    // --- Initial Load ---
    Chart.register(ChartDataLabels);
    refreshAllData();

});

    