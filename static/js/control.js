/* ================= UTIL ================= */

async function fetchJSON(url){
  try {
    const r = await fetch(url);
    if(!r.ok){
      throw new Error("HTTP " + r.status);
    }
    return await r.json();
  } catch(err){
    console.error("Fetch failed:", err);
    return {};
  }
}

async function postData(url, data){
  try {
    const r = await fetch(url, {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(data)
    });

    if(!r.ok){
      throw new Error("HTTP " + r.status);
    }

    return await r.json();

  } catch(err){
    console.error("POST error:", err);
    return { status: "ERROR", detail: err.message };
  }
}

/* ================= SAFE HELPERS ================= */

function getValueSafe(id){
  const el = document.getElementById(id);
  if(!el){
    console.warn("Missing element:", id);
    return null;
  }
  return el.value;
}

function setValueSafe(id, value){
  const el = document.getElementById(id);
  if(!el){
    console.warn("Missing element:", id);
    return;
  }
  el.value = value ?? "";
}

/* ================= LOAD VALUES ================= */

async function loadControlValues(){

  if(!document.getElementById("pwm_period")){
    return;
  }

  const data = await fetchJSON("/api/control/latest");

  setValueSafe("pwm_period", data.pwm_period);
  setValueSafe("pwm_duty", data.pwm_duty);

  setValueSafe("pid_t_set", data.pid_t_set);
  setValueSafe("pid_t_full", data.pid_t_full);
  setValueSafe("pid_t_move", data.pid_t_move);
}

/* ================= SAVE ALL ================= */

async function saveAll(){

  const period = Number(getValueSafe("pwm_period"));
  const duty   = Number(getValueSafe("pwm_duty"));

  const t_set  = Number(getValueSafe("pid_t_set"));
  const t_full = Number(getValueSafe("pid_t_full"));
  const t_move = Number(getValueSafe("pid_t_move"));

  const result = await postData("/api/control/save_all", {
    period: period,
    duty: duty,
    t_set: t_set,
    t_full: t_full,
    t_move: t_move
  });

  if(result.status === "OK"){
    alert("Control values saved");
  } else {
    alert("ERROR saving control values");
    console.error(result);
  }
}

/* ================= INIT ================= */

document.addEventListener("DOMContentLoaded", function() {
  loadControlValues();
});