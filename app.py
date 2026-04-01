from flask import Flask, request, render_template_string, jsonify
from datetime import datetime
import re

app = Flask(__name__)

leituras = []

@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Scanner</title>
<script src="https://unpkg.com/html5-qrcode"></script>
</head>

<body style="text-align:center;font-family:Arial">

<h2>📷 Scanner</h2>

<div id="reader" style="width:300px;margin:auto;"></div>

<br>
<button onclick="trocarCamera()">🔄 Trocar Câmera</button>

<h2 id="status">Aguardando leitura...</h2>
<h3 id="raw"></h3>

<script>
let scanner;
let cameras = [];
let cameraIndex = 0;

function iniciar(cameraId){
    scanner = new Html5Qrcode("reader");

    scanner.start(cameraId, { fps:10, qrbox:250 }, (text)=>{

        document.getElementById("raw").innerText = "RAW: " + text;

        fetch('/scan', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({code:text})
        })
        .then(r=>r.json())
        .then(resp=>{
            document.getElementById("status").innerText = resp.msg;
        });

        let audio = new Audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3");
        audio.play();
    });
}

function start(){
    Html5Qrcode.getCameras().then(devices => {

        cameras = devices;

        let traseira = devices.find(d =>
            d.label.toLowerCase().includes("back")
        );

        cameraIndex = traseira ? devices.indexOf(traseira) : 0;

        iniciar(devices[cameraIndex].id);
    });
}

function trocarCamera(){
    scanner.stop().then(() => {
        cameraIndex = (cameraIndex + 1) % cameras.length;
        iniciar(cameras[cameraIndex].id);
    });
}

start();
</script>

</body>
</html>
""")

# =========================
# SCAN AJUSTADO PRO SEU QR
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    raw = request.json.get('code', '')
    texto = raw.upper()

    agora = datetime.now().strftime("%H:%M:%S")

    # 🔥 CASO: PACOTE Nº29 - 1143
    match = re.search(r"PACOTE\\s*N.?\\s*(\\d+)\\s*-\\s*(\\d+)", texto)

    if match:
        pacote = match.group(1)
        obra = match.group(2)
        caixa = "1"
        total = "?"

    else:
        # fallback universal
        numeros = re.findall(r"\\d+", texto)

        if len(numeros) >= 2:
            pacote = numeros[0]
            obra = numeros[1]
            caixa = "1"
            total = "?"
        else:
            return {"msg": f"❌ NÃO RECONHECIDO"}

    codigo = f"{obra}.{caixa}-{pacote}"

    for l in leituras:
        if l["codigo"] == codigo:
            return {"msg": f"⚠️ DUPLICADO: {codigo}"}

    leituras.append({
        "codigo": codigo,
        "obra": obra,
        "caixa": caixa,
        "pacote": pacote,
        "hora": agora
    })

    return {"msg": f"✅ {codigo}"}

@app.route('/dados')
def dados():
    return jsonify(leituras)

if __name__ == '__main__':
    app.run()
