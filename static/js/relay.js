async function fetchJSON(url){
  const r = await fetch(url, {cache: "no-store"});
  if(!r.ok) throw new Error("HTTP " + r.status);
  return await r.json();
}

async function postJSON(url, data){
  const r = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
  });
  return await r.json();
}

function renderRelayControl(el, data){

  let html = `
    <tr>
      <th>Name</th>
      <th>State</th>
      <th>Mode</th>
      <th>Action</th>
    </tr>
  `;

  for(let i=0;i<data.r.length;i++){

    const name = data.r_names[i];
    const state = data.r[i] === 1;
    const mode = data.r_modes[i];

    const stateTxt = state
      ? '<span class="relay-on">ON</span>'
      : '<span class="relay-off">OFF</span>';

    let actionTxt = "";

    if(mode === "manual"){
      actionTxt = `
        <button onclick="setRelay('${"r"+(i+1)}',1)">ON</button>
        <button onclick="setRelay('${"r"+(i+1)}',0)">OFF</button>
      `;
    } else {
      actionTxt = '<span class="badge-auto">AUTO</span>';
    }

    html += `
      <tr>
        <td>${name}</td>
        <td>${stateTxt}</td>
        <td>${mode.toUpperCase()}</td>
        <td>${actionTxt}</td>
      </tr>
    `;
  }

  el.innerHTML = html;
}

async function setRelay(name, state){
  await postJSON("/api/relay/set", {name:name, state:state});
  tick();
}

async function tick(){
  try{
    const data = await fetchJSON("/api/latest");

    document.getElementById("lastUpdate").textContent = data.server_time;
    document.getElementById("refreshMs").textContent = data.refresh_ms;

    renderRelayControl(
      document.getElementById("relayControlTable"),
      data
    );

  }catch(e){
    document.getElementById("lastUpdate").textContent = "ERROR";
  }
}

tick();
setInterval(tick, REFRESH_MS);
