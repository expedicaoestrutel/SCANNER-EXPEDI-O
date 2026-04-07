from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://unpkg.com/html5-qrcode"></script>

<style>
body { margin:0; font-family:Arial; background:#f1f1f1; }

/* HEADER */
.header {
    background:#d32f2f;
    color:white;
    padding:15px;
    font-size:18px;
}

/* SEARCH */
.search {
    padding:10px;
}
.search input {
    width:100%;
    padding:12px;
    border-radius:10px;
    border:none;
}

/* LIST */
.card {
    background:white;
    margin:10px;
    padding:15px;
    border-radius:10px;
    box-shadow:0 2px 5px rgba(0,0,0,0.2);
}

/* FAB */
.fab {
    position:fixed;
    bottom:20px;
    right:20px;
    background:#d32f2f;
    color:white;
    width:65px;
    height:65px;
    border-radius:50%;
    font-size:26px;
    border:none;
}

/* SCANNER */
#scanner {
    display:none;
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background:black;
}

#reader { width:100%; }

/* TOP BAR */
.top {
    position:absolute;
    top:0;
    width:100%;
    background:#d32f2f;
    padding:10px;
    color:white;
    display:flex;
    justify-content:space-between;
}

/* MIRA */
.mira {
    position:absolute;
    top:50%;
    left:50%;
    width:250px;
    height:250px;
    margin-left:-125px;
    margin-top:-125px;
    border:3px solid #00e5ff;
    border-radius:10px;
}

/* FEEDBACK */
.feedback {
    position:absolute;
    top:0;
    left:0;
    width:100%;
    height:100%;
    opacity:0;
}

.ok { background:rgba(0,255,0,0.3); }
.erro { background:rgba(255,0,0,0.3); }
</style>
</head>

<body>

<div class="header">📦 Barcode PRO</div>

<div class="search">
<input placeholder="Pesquisar volume ou peça..." oninput="pesquisar(this.value)">
</div>

<div id="lista"></div>

<button class="fab" onclick="abrir()">📷</button>

<!-- SCANNER -->
<div id="scanner">

    <div class="top">
        <button onclick="fechar()">⬅</button>
        <span>Leitura</span>
        <button onclick="flash()">🔦</button>
    </div>

    <div id="reader"></div>
    <div class="mira"></div>
    <div id="fb" class="feedback"></div>

</div>

<script>
let dados = JSON.parse(localStorage.getItem("dados") || "{}");
let html5QrCode;
let flashOn=false;

// =========================
// SOM
// =========================
function beep(){
    let audio = new Audio("https://actions.google.com/sounds/v1/beeps/beep_short.ogg");
    audio.play();
}

// =========================
// VIBRAR
// =========================
function vibrar(){
    if(navigator.vibrate) navigator.vibrate(100);
}

// =========================
// LISTA
// =========================
function atualizar(filtro=""){
    let html="";

    for(let v in dados){

        let itens = dados[v];

        if(filtro){
            if(!v.includes(filtro) && !itens.join().includes(filtro)){
                continue;
            }
        }

        html+=`
        <div class="card">
            <b>📦 Volume ${v}</b><br>
            Peças: ${itens.length}
        </div>`;
    }

    document.getElementById("lista").innerHTML=html;
}

function pesquisar(v){
    atualizar(v.toUpperCase());
}

// =========================
// SCANNER
// =========================
function abrir(){

    document.getElementById("scanner").style.display="block";

    html5QrCode = new Html5Qrcode("reader");

    Html5Qrcode.getCameras().then(devices=>{

        let cam = devices.find(d =>
            d.label.toLowerCase().includes("back") ||
            d.label.toLowerCase().includes("environment")
        );

        html5QrCode.start(
            cam ? cam.id : devices[0].id,
            { fps:15, qrbox:250 },
            scan
        );
    });
}

function fechar(){
    html5QrCode.stop().then(()=>{
        document.getElementById("scanner").style.display="none";
    });
}

// =========================
// FEEDBACK
// =========================
function feedback(tipo){
    let el = document.getElementById("fb");
    el.className = "feedback " + tipo;
    el.style.opacity=1;

    setTimeout(()=>{
        el.style.opacity=0;
    },200);
}

// =========================
// LEITURA
// =========================
function scan(txt){

    txt = txt.toUpperCase();

    if(txt.includes("PACOTE")){
        let n = txt.match(/\\d+/);
        if(n){
            let v = n[0];
            if(!dados[v]) dados[v]=[];
            salvar(); atualizar();
            vibrar(); beep(); feedback("ok");
            return;
        }
    }

    let cod = txt.match(/\\d+/);
    if(!cod) return;

    cod = cod[0];

    let vols = Object.keys(dados);
    if(vols.length===0){
        feedback("erro");
        return;
    }

    vols.forEach(v=>{
        if(!dados[v].includes(cod)){
            dados[v].push(cod);
        }else{
            feedback("erro");
            return;
        }
    });

    salvar(); atualizar();
    vibrar(); beep(); feedback("ok");
}

// =========================
// FLASH
// =========================
function flash(){
    let track = html5QrCode.getRunningTrack();
    if(!track) return;

    let cap = track.getCapabilities();
    if(!cap.torch){
        alert("Sem flash");
        return;
    }

    flashOn = !flashOn;

    track.applyConstraints({
        advanced:[{torch:flashOn}]
    });
}

// =========================
function salvar(){
    localStorage.setItem("dados", JSON.stringify(dados));
}

atualizar();
</script>

</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)
