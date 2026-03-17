console.log("graph.js loaded")

let chart = null
let liveTimer = null
let LIVE_WINDOW = 120
let liveMode = false

//--------------------------------------------------
// MEDIAN FILTER
//--------------------------------------------------

function medianFilter(data, window = 5) {

    const half = Math.floor(window / 2)
    let result = []

    for (let i = 0; i < data.length; i++) {

        let arr = []

        for (let j = i - half; j <= i + half; j++) {
            if (j >= 0 && j < data.length)
                arr.push(data[j])
        }

        arr.sort((a, b) => a - b)
        result.push(arr[Math.floor(arr.length / 2)])
    }

    return result
}

//--------------------------------------------------
// AUTOSCALE
//--------------------------------------------------

function autoScale(minVal, maxVal) {

    if (!isFinite(minVal) || !isFinite(maxVal))
        return { min: 0, max: 1 }

    let minScaled = minVal >= 0 ? minVal * 0.8 : minVal * 1.2
    let maxScaled = maxVal >= 0 ? maxVal * 1.2 : maxVal * 0.8

    let range = maxScaled - minScaled
    let minRange = Math.max(Math.abs(maxVal - minVal) * 0.1, 0.5)

    if (range < minRange) {

        let center = (maxVal + minVal) / 2
        minScaled = center - minRange / 2
        maxScaled = center + minRange / 2

    }

    return { min: minScaled, max: maxScaled }
}

//--------------------------------------------------
// SELECTED CHANNELS
//--------------------------------------------------

function getSelected(prefix) {

    let result = []

    document.querySelectorAll("input[type=checkbox]").forEach(cb => {

        if (!cb.checked) return

        const v = cb.value.toLowerCase()

        if (v.startsWith(prefix))
            result.push(v)

    })

    return result
}

//--------------------------------------------------
// RANGE PARSER
//--------------------------------------------------

function getRange() {

    const val = document.getElementById("range").value

    if (val.endsWith("m"))
        return { minutes: parseInt(val), hours: null }

    if (val.endsWith("h"))
        return { minutes: null, hours: parseInt(val) }

    return { minutes: null, hours: 24 }
}

//--------------------------------------------------
// LIVE BUTTON STYLE
//--------------------------------------------------

function setLiveButton(state){

    const btn = document.getElementById("btnLive")
    if(!btn) return

    if(state){

        btn.classList.remove("btn-live")
        btn.classList.add("btn-live-active")
        btn.textContent = "LIVE ON"

    }else{

        btn.classList.remove("btn-live-active")
        btn.classList.add("btn-live")
        btn.textContent = "LIVE"
    }
}

//--------------------------------------------------
// LOAD GRAPH
//--------------------------------------------------

async function loadGraph() {

    stopLive()

    const range = getRange()

    let url = ""

    if (range.minutes)
        url = `/api/live?minutes=${range.minutes}`
    else
        url = `/api/history?hours=${range.hours}`

    const r = await fetch(url, { cache: "no-store" })

    if (!r.ok) {
        console.error("API error")
        return
    }

    const data = await r.json()

    if (!data.time) {
        console.error("Invalid API response", data)
        return
    }

    let tChannels = getSelected("t")
    let pChannels = getSelected("p")

    let datasets = []

    let tempMin = Infinity
    let tempMax = -Infinity

    let pressMin = Infinity
    let pressMax = -Infinity

//--------------------------------------------------
// TEMPERATURE
//--------------------------------------------------

    for (const ch of tChannels) {

        if (!data.t || !data.t[ch]) continue

        let values = medianFilter(data.t[ch], 5)

        values.forEach(v => {
            if (v != null) {
                if (v < tempMin) tempMin = v
                if (v > tempMax) tempMax = v
            }
        })

        datasets.push({
            label: ch.toUpperCase(),
            data: values,
            yAxisID: "yTemp",
            pointRadius: 0,
            tension: 0.2
        })
    }

//--------------------------------------------------
// PRESSURE
//--------------------------------------------------

    for (const ch of pChannels) {

        if (!data.p || !data.p[ch]) continue

        let values = medianFilter(data.p[ch], 5)

        values.forEach(v => {
            if (v != null) {
                if (v < pressMin) pressMin = v
                if (v > pressMax) pressMax = v
            }
        })

        datasets.push({
            label: ch.toUpperCase(),
            data: values,
            yAxisID: "yPress",
            pointRadius: 0,
            tension: 0.2
        })
    }

    if (datasets.length === 0) {
        alert("No data selected")
        return
    }

    if (chart)
        chart.destroy()

    const tempScale = autoScale(tempMin, tempMax)
    const pressScale = autoScale(pressMin, pressMax)

    chart = new Chart(document.getElementById("chart"), {

        type: "line",

        data: {
            labels: data.time,
            datasets: datasets
        },

        options: {

            responsive: true,
            animation: false,

            interaction: {
                mode: "index",
                intersect: false
            },

            plugins: {

                legend: {
                    labels: {
                        font: {
                            size: 20
                        }
                    }
                },

                tooltip: {
                    titleFont: {
                        size: 20
                    },
                    bodyFont: {
                        size: 20
                    }
                }

            },

            scales: {

                x: {
                    type: "category",
                    ticks: {
                        font: { size: 20 },
                        maxTicksLimit: 8,
                        autoSkip: true,
                        maxRotation: 90,
                        minRotation: 90
                    },
                    grid: {
                        color: "rgba(200,200,200,0.2)"   // jemné mriežky
                    },
                    border: {
                        color: "#000",
                        width: 2
                    }
                },
                yPress: {
                    type: "linear",
                    position: "left",
                    min: pressScale.min,
                    max: pressScale.max,
                    title: {
                        display: true,
                        text: "Pressure",
                        font: { size: 20 }
                    },
                    ticks: {
                        font: { size: 20 }
                    },
                    grid: {
                        color: "rgba(200,200,200,0.2)"
                    },
                    border: {
                        color: "#000",
                        width: 2
                    }
                },
                yTemp: {
                    type: "linear",
                    position: "right",
                    min: tempScale.min,
                    max: tempScale.max,
                    title: {
                        display: true,
                        text: "Temperature",
                        font: { size: 20 }
                    },
                    ticks: {
                        font: { size: 20 }
                    },
                    grid: { 
                        drawOnChartArea: false 
                    },
                    border: {
                        color: "#000",
                        width: 2
                    }
                },

            }

        }

    })

}

//--------------------------------------------------
// LIVE UPDATE
//--------------------------------------------------

async function updateLive() {

    const r = await fetch("/api/live?minutes=10", { cache: "no-store" })

    if (!r.ok) return

    const data = await r.json()

    if (!chart || !data.time) return

    const lastIndex = data.time.length - 1
    const newTime = data.time[lastIndex]

    chart.data.labels.push(newTime)

    if (chart.data.labels.length > LIVE_WINDOW)
        chart.data.labels.shift()

    chart.data.datasets.forEach(ds => {

        let name = ds.label.toLowerCase()
        let newValue = null

        if (name.startsWith("t") && data.t[name])
            newValue = data.t[name][lastIndex]

        if (name.startsWith("p") && data.p[name])
            newValue = data.p[name][lastIndex]

        ds.data.push(newValue)

        if (ds.data.length > LIVE_WINDOW)
            ds.data.shift()
    })

    chart.update("none")
}

//--------------------------------------------------
// LIVE CONTROL
//--------------------------------------------------

function startLive() {

    if (liveTimer)
        return

    liveMode = true
    setLiveButton(true)

    const range = getRange()

    if (range.minutes)
        LIVE_WINDOW = Math.round(range.minutes * 60 / 5)

    if (range.hours)
        LIVE_WINDOW = Math.round(range.hours * 3600 / 5)

    updateLive()

    liveTimer = setInterval(updateLive, 5000)

}

function stopLive() {

    clearInterval(liveTimer)
    liveTimer = null

    liveMode = false
    setLiveButton(false)

}

//--------------------------------------------------
// TOGGLE LIVE
//--------------------------------------------------

function toggleLive(){

    if(liveMode)
        stopLive()
    else
        startLive()
}

//--------------------------------------------------
// INIT
//--------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {

    console.log("Graph page ready")

    loadGraph()

})