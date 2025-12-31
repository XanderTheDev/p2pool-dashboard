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

function sliceHistory(hours){
    const cutoff = Date.now()/1000 - hours*3600;
    const idx = history.timestamps.findIndex(t => t>=cutoff);
    const i = idx===-1?0:idx;
    return {
        labels: history.timestamps.slice(i).map(t=>t*1000),
        myHash: history.myHash.slice(i),
        price: history.price.slice(i)
    };
}

function updateCharts(){
    const d = sliceHistory(currentRangeHours);

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
        const [xmrig, pool, network] = await Promise.all([
            fetchJSON("/xmrig_summary"),
            fetchJSON("/pool/stats"),
            fetchJSON("/network/stats")
        ]);

        const myHash = xmrig.hashrate.total[0];
        const poolHash = pool.pool_statistics.hashRate;
        const netHash = network.difficulty/120;
        const blockReward = network.reward/1e12;

        document.getElementById("myHashrate").textContent = scaleHashrate(myHash);
        document.getElementById("poolHashrate").textContent = scaleHashrate(poolHash);
        document.getElementById("netHashrate").textContent = scaleHashrate(netHash);
        document.getElementById("blockReward").textContent = blockReward.toFixed(6);

        const poolShare = (myHash/poolHash)*100;
        document.getElementById("poolShare").textContent = poolShare.toFixed(4)+"%";

        const price = history.price.at(-1) || 0;
        document.getElementById("price").textContent = "€"+price.toFixed(2);

        // Earnings
        const blocksPerDay = 720;
        const myNetShare = myHash/netHash;
        const xmrPerDay = myNetShare*blocksPerDay*blockReward;
        const period = document.getElementById("earnPeriod").value;
        const xmr = xmrPerDay*PERIOD_MULT[period];
        document.getElementById("earnXMR").textContent = xmr.toFixed(6)+" XMR";
        document.getElementById("earnEUR").textContent = "≈ €"+(xmr*price).toFixed(2);

        // Payout interval
        const moneroBlockTime = 120;
        const fracPool = myHash/poolHash;
        const etaSeconds = moneroBlockTime/(fracPool||1);
        const h=Math.floor(etaSeconds/3600);
        const m=Math.floor((etaSeconds%3600)/60);
        const s=Math.floor(etaSeconds%60);
        document.getElementById("payoutInterval").textContent = `${h}h ${m}m ${s}s`;

    } catch(e){
        console.error("Error fetching stats:", e);
    }
}

// Dropdown for earnings
document.getElementById("earnPeriod").onchange = updateStats;

(async()=>{
    history = await fetchJSON("/stats_log.json");
    updateCharts();
    updateStats();
    setInterval(updateStats,5000);
})();
