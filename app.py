from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Scanner Expedição</title>

<script src="https://unpkg.com/@zxing/browser@0.1.1"></script>

<style>
body { margin:0; font-family:Arial; background:#f2f2f2; }

.header {
    background:#25346A;
    color:white;
    padding:15px;
    font-size:18px;
}

.search { padding:10px; background:white; }

.search input {
    width:100%;
    padding:12px;
    border-radius:8px;
    border:1px solid #ccc;
}

#video {
    width:100%;
    height:250px;
    display:none;
    object-fit:cover;
}

/* VOLUMES */
.volume {
    background:white;
    margin:10px;
    padding:15px;
    border-radius:10px;
}

.volume.active {
    border:3px solid green;
}

/* BOTÕES */
.btn {
    position:fixed;
    bottom:20px;
    right:20px;
    background:#25346A;
    width:65px;
    height:65px;
    border-radius:50%;
    color:white;
    font-size:28px;
    display:flex;
    align-items:center;
    justify-content:center;
}

.flash {
    bottom:100px;
    background:#333;
}
</style>
</head>

<body>

<div class="header">CONTROLE DE VOLUMES</div>

<div class="search">
<input placeholder="🔎 Buscar..." onkeyup="buscar(this.value)">
</div>

<video id="video" playsinline></video>

<div id="lista"></div>

<div class="btn" onclick="iniciar()">📷</div>
<div class="btn flash" onclick="toggleFlash()">⚡</div>

<script>
let reader = new ZXing.BrowserMultiFormatReader();

let volumes = JSON.parse(localStorage.getItem("volumes") || "{}");
let ativos = [];

let stream;
let travado = false;
let flashOn = false;

// 🔊 SOM PROFISSIONAL
function beep(){
    let audio = new Audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg");
    audio.play();
}

// 📳 VIBRAÇÃO
function vibrar(){
    if(navigator.vibrate) navigator.vibrate(100);
}

// 📷 INICIAR CAMERA (CORRIGIDO)
async function iniciar(){

    let video = document.getElementById("video");
    video.style.display="block";

    try{

        const constraints = {
            video: {
                facingMode: { ideal: "environment" },
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        };

        stream = await navigator.mediaDevices.getUserMedia(constraints);

        video.srcObject = stream;
        await video.play();

        reader.decodeFromVideoElement(video,(res,err)=>{

            if(res && !travado){

                travado = true;

                let txt = res.getText().toUpperCase();

                vibrar(); 
                beep();

                // 📦 SE FOR VOLUME
                if(txt.includes("PACOTE") || txt.includes("CAIXA")){

                    let num = txt.match(/\\d+/);

                    if(num){
                        let v = num[0];

                        if(!volumes[v]) volumes[v] = [];

                        if(!ativos.includes(v)){
                            ativos.push(v);
                        }
                    }

                } else {

                    if(ativos.length === 0){
                        alert("Leia um volume primeiro (CAIXA/PACOTE)");
                    }

                    ativos.forEach(v=>{
                        if(!volumes[v].includes(txt)){
                            volumes[v].push(txt);
                        }
                    });
                }

                atualizar();
                salvar();

                setTimeout(()=>travado=false,800);
            }
        });

    }catch(e){
        alert("Erro câmera: " + e.message);
    }
}

// 🔦 FLASH REAL
function toggleFlash(){

    if(!stream) return;

    let track = stream.getVideoTracks()[0];

    let cap = track.getCapabilities();

    if(!cap.torch){
        alert("Flash não suportado");
        return;
    }

    flashOn = !flashOn;

    track.applyConstraints({
        advanced: [{ torch: flashOn }]
    });
}

// 💾 SALVAR
function salvar(){
    localStorage.setItem("volumes", JSON.stringify(volumes));
}

// 🔎 BUSCAR
function buscar(txt){

    txt = txt.toLowerCase();

    let html = "";

    for(let v in volumes){

        if(!v.includes(txt)) continue;

        html += render(v);
    }

    document.getElementById("lista").innerHTML = html;
}

// 📊 ATUALIZAR
function atualizar(){

    let html = "";

    for(let v in volumes){
        html += render(v);
    }

    document.getElementById("lista").innerHTML = html;
}

// 📦 TEMPLATE
function render(v){

    let ativo = ativos.includes(v) ? "active" : "";

    return `
    <div class="volume ${ativo}" onclick="toggle('${v}')">
        <b>📦 Volume ${v}</b><br>
        Peças: ${volumes[v].length}
    </div>`;
}

// 🔄 ATIVAR/DESATIVAR
function toggle(v){

    if(ativos.includes(v)){
        ativos = ativos.filter(x => x !== v);
    } else {
        ativos.push(v);
    }

    atualizar();
}

atualizar();
</script>

</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
