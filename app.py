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
body { margin:0; font-family:Arial; background:#f5f5f5; }

/* HEADER */
.header {
    background:#e53935;
    color:white;
    padding:15px;
    font-size:20px;
    display:flex;
    align-items:center;
}

/* LISTA */
.lista {
    padding:10px;
}

.card {
    background:white;
    padding:15px;
    margin-bottom:10px;
    border-radius:10px;
    box-shadow:0 2px 5px rgba(0,0,0,0.2);
}

/* BOTÃO FLUTUANTE */
.fab {
    position:fixed;
    bottom:20px;
    right:20px;
    background:#e53935;
    color:white;
    border:none;
    width:60px;
    height:60px;
    border-radius:50%;
    font-size:25px;
}

/* TELA LEITURA */
#scannerTela {
    display:none;
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background:black;
}

#reader { width:100%; }

/* TOPO LEITOR */
.topoScanner {
    position:absolute;
    top:0;
    width:100%;
    background:#e53935;
    padding:10px;
    color:white;
    display:flex;
    justify-content:space-between;
}
</style>
</head>

<body>

<div class="header">
☰ Sessões de leitura
</div>

<div class="lista" id="lista"></div>

<button class="fab" onclick="abrirScanner()">📷</button>

<!-- TELA SCANNER -->
<div id="scannerTela">

    <div class="topoScanner">
        <button onclick="fecharScanner()">⬅</button>
        <span>Leitura</span>
        <button onclick="toggleFlash()">🔦</button>
    </div>

    <div id="reader"></div>
</div>

<script>
let dados = JSON.parse(localStorage.getItem("dados") || "{}");

// =========================
// LISTA
// =========================
function atualizarLista(){
    let html = "";

    for(let v in dados){
        html += `
        <div class="card">
            <b>RELATÓRIO VOLUME ${v}</b><br>
            Leituras: ${dados[v].length}
        </div>`;
    }

    document.getElementById("lista").innerHTML = html;
}

// =========================
// SCANNER
// =========================
let html5QrCode;
let flashOn = false;

function abrirScanner(){
    document.getElementById("scannerTela").style.display = "block";

    html5QrCode = new Html5Qrcode("reader");

    Html5Qrcode.getCameras().then(devices => {

        let back = devices.find(d =>
            d.label.toLowerCase().includes("back") ||
            d.label.toLowerCase().includes("environment")
        );

        let cam = back ? back.id : devices[0].id;

        html5QrCode.start(
            cam,
            { fps:10, qrbox:250 },
            onScan
        );
    });
}

function fecharScanner(){
    html5QrCode.stop().then(()=>{
        document.getElementById("scannerTela").style.display = "none";
    });
}

// =========================
// LEITURA
// =========================
function onScan(txt){

    txt = txt.toUpperCase();

    // volume
    if(txt.includes("PACOTE")){
        let n = txt.match(/\\d+/);
        if(n){
            let v = n[0];
            if(!dados[v]) dados[v] = [];
            salvar();
            atualizarLista();
            vibrar();
            return;
        }
    }

    let cod = txt.match(/\\d+/);
    if(!cod) return;

    cod = cod[0];

    let vols = Object.keys(dados);
    if(vols.length === 0){
        alert("Leia um volume primeiro");
        return;
    }

    vols.forEach(v=>{
        if(!dados[v].includes(cod)){
            dados[v].push(cod);
        }
    });

    salvar();
    atualizarLista();
    vibrar();
}

// =========================
// FLASH
// =========================
function toggleFlash(){

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
// VIBRAR
// =========================
function vibrar(){
    if(navigator.vibrate){
        navigator.vibrate(100);
    }
}

// =========================
function salvar(){
    localStorage.setItem("dados", JSON.stringify(dados));
}

atualizarLista();
</script>

</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)
