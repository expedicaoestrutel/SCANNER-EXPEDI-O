from flask import Flask, request, render_template_string, jsonify, send_file
from datetime import datetime
import re
from openpyxl import Workbook
import io

app = Flask(__name__)

leituras = []

# =========================
# SCANNER
# =========================
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

<br>
<a href="/dashboard">📊 Ir para Painel</a>

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
# SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    raw = request.json.get('code', '')
    texto = raw.upper()

    agora = datetime.now().strftime("%H:%M:%S")

    match = re.search(r"PACOTE\\s*N.?\\s*(\\d+)\\s*-\\s*(\\d+)", texto)

    if match:
        pacote = match.group(1)
        obra = match.group(2)
        caixa = "1"
    else:
        numeros = re.findall(r"\\d+", texto)
        if len(numeros) >= 2:
            pacote = numeros[0]
            obra = numeros[1]
            caixa = "1"
        else:
            return {"msg": "❌ NÃO RECONHECIDO"}

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

# =========================
# DADOS
# =========================
@app.route('/dados')
def dados():
    return jsonify(leituras)

# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Painel</title>
</head>

<body style="font-family:Arial">

<h2>📊 Painel de Expedição</h2>

<input type="text" id="busca" placeholder="Pesquisar..." onkeyup="filtrar()">

<br><br>

<button onclick="exportar()">📥 Exportar Excel</button>
<button onclick="limpar()">🗑 Limpar</button>

<h3 id="total"></h3>

<table border="1" id="tabela">
<thead>
<tr>
<th>Código</th>
<th>Obra</th>
<th>Pacote</th>
<th>Hora</th>
</tr>
</thead>
<tbody></tbody>
</table>

<script>
function carregar(){
    fetch('/dados')
    .then(r=>r.json())
    .then(lista=>{

        let tbody = document.querySelector("#tabela tbody");
        tbody.innerHTML = "";

        let contagem = {};

        lista.forEach(item=>{

            let tr = `<tr>
                <td>${item.codigo}</td>
                <td>${item.obra}</td>
                <td>${item.pacote}</td>
                <td>${item.hora}</td>
            </tr>`;

            tbody.innerHTML += tr;

            contagem[item.obra] = (contagem[item.obra] || 0) + 1;
        });

        let texto = "Totais: ";
        for (let o in contagem){
            texto += `Obra ${o}: ${contagem[o]} | `;
        }

        document.getElementById("total").innerText = texto;
    });
}

function filtrar(){
    let input = document.getElementById("busca").value.toLowerCase();
    let linhas = document.querySelectorAll("#tabela tbody tr");

    linhas.forEach(l=>{
        l.style.display = l.innerText.toLowerCase().includes(input) ? "" : "none";
    });
}

function exportar(){
    window.location.href = "/exportar";
}

function limpar(){
    fetch('/limpar').then(()=>carregar());
}

setInterval(carregar, 2000);
carregar();
</script>

</body>
</html>
""")

# =========================
# EXPORTAR EXCEL
# =========================
@app.route('/exportar')
def exportar():
    wb = Workbook()
    ws = wb.active

    ws.append(["Código", "Obra", "Pacote", "Hora"])

    for l in leituras:
        ws.append([l["codigo"], l["obra"], l["pacote"], l["hora"]])

    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    return send_file(file, download_name="expedicao.xlsx", as_attachment=True)

# =========================
# LIMPAR
# =========================
@app.route('/limpar')
def limpar():
    leituras.clear()
    return {"msg":"ok"}

if __name__ == '__main__':
    app.run()
