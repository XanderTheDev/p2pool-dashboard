let history;
let hashrateChart, priceChart;
let currentRangeHours = 24;

const PERIOD_MULT = { hour: 1/24, day: 1, week: 7, month: 30, year: 365 };

function scaleHashrate(v){
    if(v>=1e9) return (v/1e9).toFixed(2)+" GH/s";
    if(v>=1e6) return (v/1e6).toFixed(2)+" MH/s";
    if(v>=1e3) return (v/1e3).toFixed(2)+" kH/s";
    return Math.round(v)+" H/s";
}

async function fetchJSON(url){
    const r = await fetch(url);
    if(!r.ok) throw new Error(url);
    return r.json();
}

function sliceHistory(hours, hist) {
    const now = Date.now()/1000;
    const cutoff = now - hours*3600;
    const idx = hist.timestamps.findIndex(t => t>=cutoff);
    const i = idx === -1 ? 0 : idx;
    return {
        labels: hist.timestamps.slice(i).map(t => t*1000),
        myHash: hist.myHash.slice(i),
        poolHash: hist.poolHash.slice(i),
        netHash: hist.netHash.slice(i),
        price: hist.price.slice(i)
    };
}

// Moving average over a given time window in seconds (e.g., 600 = 10min)
function movingAverage(timestamps, values, windowSeconds = 600) {
    if(!timestamps || !values || timestamps.length === 0) return 0;
    let smoothed = [];
    for(let i = 0; i < values.length; i++){
        const start = timestamps[i] - windowSeconds;
        let sum = 0, count = 0;
        for(let j = 0; j <= i; j++){
            if(timestamps[j] >= start){
                sum += values[j];
                count++;
            }
        }
        smoothed.push(count ? sum / count : values[i]);
    }
    return smoothed.at(-1);
}

function updateCharts(){
    if(!history) return;
    const d = sliceHistory(currentRangeHours, history);

    // HASHRATE CHART
    if(!hashrateChart){
        hashrateChart = new Chart(document.getElementById("hashrateChart"),{
            type:"line",
            data:{
                labels:d.labels,
                datasets:[{label:"Your Hashrate", data:d.myHash}]
            },
            options:{
                scales:{
                    x:{type:"time"},
                    y:{ticks:{callback:scaleHashrate}}
                },
                elements:{point:{radius:0}, line:{tension:0.25}}
            }
        });
    } else {
        hashrateChart.data.labels = d.labels;
        hashrateChart.data.datasets[0].data = d.myHash;
        hashrateChart.update();
    }

    // PRICE CHART
    if(!priceChart){
        priceChart = new Chart(document.getElementById("priceChart"),{
            type:"line",
            data:{
                labels:d.labels,
                datasets:[{label:"XMR Price (EUR)", data:d.price}]
            },
            options:{
                scales:{x:{type:"time"}},
                elements:{point:{radius:0}, line:{tension:0.25}}
            }
        });
    } else {
        priceChart.data.labels = d.labels;
        priceChart.data.datasets[0].data = d.price;
        priceChart.update();
    }
}

async function updateStats(){
    try{
        const [xmrig, pool, network, thresholdObj, hist] = await Promise.all([
            fetchJSON("/xmrig_summary"),
            fetchJSON("/pool/stats"),
            fetchJSON("/network/stats"),
            fetchJSON("/min_payment_threshold"),
            fetchJSON("/stats_log.json")
        ]);

        history = hist;
        updateCharts();

        // Instantaneous readings
        const instMyHash = xmrig.hashrate.total[0];
        const instPoolHash = pool.pool_statistics.hashRate;
        const instNetHash = network.difficulty/120;
        const blockReward = network.reward/1e12;
        const minPaymentThreshold = thresholdObj.minPaymentThreshold;

        // Determine available window (max 24h)
        const now = Date.now()/1000;
        let avgWindowHours = 24;
        if(history && history.timestamps.length > 0){
            const earliest = history.timestamps[0];
            const availableHours = (now - earliest) / 3600;
            if(availableHours < 24) avgWindowHours = availableHours;
            if(avgWindowHours <= 0) avgWindowHours = 0;
        }

        // Compute moving averages
        let avgMyHash = instMyHash;
        let avgPoolHash = instPoolHash;
        let avgNetHash = instNetHash;
        if(avgWindowHours > 0){
            const sliced = sliceHistory(avgWindowHours, history);
            avgMyHash = movingAverage(sliced.labels.map(t => t/1000), sliced.myHash, 600);
            avgPoolHash = movingAverage(sliced.labels.map(t => t/1000), sliced.poolHash, 600);
            avgNetHash = movingAverage(sliced.labels.map(t => t/1000), sliced.netHash, 600);
        }

        // Update visible instantaneous values
        document.getElementById("myHashrate").textContent = scaleHashrate(instMyHash);
        document.getElementById("poolHashrate").textContent = scaleHashrate(instPoolHash);
        document.getElementById("netHashrate").textContent = scaleHashrate(instNetHash);
        document.getElementById("blockReward").textContent = blockReward.toFixed(6);

        const poolShare = (instMyHash/instPoolHash)*100;
        document.getElementById("poolShare").textContent = poolShare.toFixed(4)+"%";

        const price = history.price.at(-1) || 0;
        document.getElementById("price").textContent = "€"+price.toFixed(2);

        // Earnings (smoothed 24h)
        const blocksPerDay = 720;
        const myNetShareAvg = avgMyHash / avgNetHash;
        const xmrPerDayAvg = myNetShareAvg * blocksPerDay * blockReward;
        const period = document.getElementById("earnPeriod").value;
        const xmr = xmrPerDayAvg * PERIOD_MULT[period];
        const eur = xmr * price;

        // Update #earnXMR text without removing tooltip
        const earnXMRDiv = document.getElementById("earnXMR");
        earnXMRDiv.textContent = xmr.toFixed(6) + " XMR";

        // Update #earnEUR
        document.getElementById("earnEUR").textContent = `≈ €${eur.toFixed(2)}`;

        // Inject tooltip icon if missing
        let earnTooltip = document.getElementById("earnTooltip");
        if(!earnTooltip){
            earnTooltip = document.createElement("span");
            earnTooltip.id = "earnTooltip";
            earnTooltip.className = "tooltip-icon";
            earnTooltip.textContent = "ⓘ";
            earnXMRDiv.appendChild(earnTooltip);
        }

        // Tooltip content
        const avgWindowLabel = avgWindowHours >= 24 ? "24h moving average" : `${avgWindowHours.toFixed(1)}h moving average`;
        earnTooltip.title = `Estimated earnings based on ${avgWindowLabel}.
Avg your hashrate: ${scaleHashrate(avgMyHash)}
Avg pool hashrate: ${scaleHashrate(avgPoolHash)}
Avg network hashrate: ${scaleHashrate(avgNetHash)}`;

        // Legend
        const legendText = avgWindowHours >= 24 ? "Based on 24h moving average" : `Based on ${avgWindowHours.toFixed(1)}h moving average`;
        document.getElementById("earnLegend").textContent = legendText;

        // Last refreshed timestamp
        const date = new Date();
        document.getElementById("lastRefreshed").textContent = `Last refreshed: ${date.toLocaleString()}`;

        // Payout interval calculation
        let xmrPerBlock = myNetShareAvg * blockReward;
        let blocksNeeded = xmrPerBlock > 0 ? (minPaymentThreshold / xmrPerBlock) : Infinity;
        let avgDaysPerPayout = blocksNeeded / blocksPerDay;
        let expectedPayoutsPerDay = isFinite(avgDaysPerPayout) && avgDaysPerPayout > 0 ? (1 / avgDaysPerPayout) : 0;

        const intervalHours = isFinite(avgDaysPerPayout) ? (avgDaysPerPayout*24).toFixed(1) : "N/A";
        const intervalText = `${expectedPayoutsPerDay.toFixed(2)} payouts/day (~${intervalHours}h/payout)`;
        document.getElementById("payoutInterval").textContent = intervalText;

        const tooltipIcon = document.querySelector(".bottom-stats .tooltip-icon");
        if(tooltipIcon){
            tooltipIcon.title = `Average payout interval: ~${intervalHours} hours
Your actual payouts can be shorter or longer, depending on mining luck.`;
        }

    } catch(e){
        console.error("Error fetching stats:", e);
    }
}

// Dropdown for earnings
document.getElementById("earnPeriod").onchange = updateStats;

(async()=>{
    try {
        history = await fetchJSON("/stats_log.json");
    } catch(e){
        history = null;
    }
    updateCharts();
    updateStats();
    setInterval(updateStats, 5000);
})();
