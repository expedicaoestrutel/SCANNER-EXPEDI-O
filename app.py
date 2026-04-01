from flask import Flask, request, render_template_string, jsonify, session, redirect
from openpyxl import Workbook, load_workbook
from datetime import datetime
import os
import re

app = Flask(__name__)
app.secret_key = "segredo123"

arquivo = "leituras.xlsx"
leituras = []

# =========================
# 📄 CRIAR EXCEL
# =========================
if not os.path.exists(arquivo):
    wb = Workbook()
    ws = wb.active
    ws.append(["Código", "Data/Hora", "Operador", "Obra", "Caixa", "Pacote", "Total"])
    wb.save(arquivo)

# =========================
# 🔐 LOGIN AUTOMÁTICO
# =========================
@app.route('/login')
def login():
    session['user'] = "Gissandro"
    return redirect('/')

# =========================
# 📷 SCANNER
# =========================
@app.route('/')
def index():
    if 'user' not in session:
        return redirect('/login')

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Scanner</title>
<script src="https://unpkg.com/html5-qrcode"></script>
</head>

<body style="text-align:center; font-family:Arial">

<h2>📷 Scanner Expedição</h2>
<h3>👤 Gissandro</h3>

<div id="reader" style="width:320px; margin:auto;"></div>

<h2 id="status">Aguardando leitura...</h2>

<br>
<a href="/dashboard">📊 Painel</a>

<script>
let ultima = "";

function onScanSuccess(decodedText) {

    let codigo = decodedText.trim();

    if (codigo === ultima) return;
    ultima = codigo;

    fetch('/scan', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code: codigo})
    })
    .then(r => r.json())
    .then(resp => {
        document.getElementById("status").innerText = resp.msg;
    });

    let audio = new Audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3");
    audio.play();
}

let scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
scanner.render(onScanSuccess);
</script>

</body>
</html>
""")

# =========================
# 📥 SCAN INTELIGENTE
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    if 'user' not in session:
        return {"msg": "Erro de sessão"}

    codigo = request.json.get('code', '').strip()
    operador = session['user']
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    texto = codigo.upper().replace("\n", " ")

    # 🔍 CAPTURA
    match_caixa = re.search(r"CAIXA\s*N[ºO]?\s*(\d+)\.(\d+)", texto)
    match_pacote = re.search(r"PACOTE\s*N[ºO]?\s*(\d+)(?:/(\d+))?", texto)

    if match_caixa and match_pacote:
        obra = match_caixa.group(1)
        caixa = match_caixa.group(2)

        pacote = match_pacote.group(1)
        total = match_pacote.group(2) if match_pacote.group(2) else "?"

        codigo_final = f"{obra}.{caixa}-{pacote}"

        wb = load_workbook(arquivo)
        ws = wb.active
        ws.append([codigo_final, agora, operador, obra, caixa, pacote, total])
        wb.save(arquivo)

        leituras.insert(0, {
            "codigo": codigo_final,
            "obra": obra,
            "caixa": caixa,
            "pacote": pacote,
            "total": total,
            "operador": operador,
            "hora": agora
        })

        return {"msg": f"📦 {obra}.{caixa} → {pacote}/{total}"}

    return {"msg": f"❌ QR não reconhecido"}

# =========================
# 📊 DADOS
# =========================
@app.route('/dados')
def dados():
    return jsonify({
        "lista": leituras[:200]
    })

# =========================
# 🖥️ DASHBOARD PROFISSIONAL
# =========================
@app.route('/dashboard')
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Painel Expedição</title>

<style>
body {
    background:#0f172a;
    color:white;
    font-family:Arial;
}

h1 {
    text-align:center;
    font-size:40px;
}

.grid {
    display:grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap:20px;
    padding:20px;
}

.card {
    background:#1e293b;
    padding:20px;
    border-radius:15px;
}

.titulo {
    font-size:22px;
    color:#38bdf8;
}

.contador {
    font-size:40px;
    margin-top:10px;
}

.ok {
    color:#22c55e;
}

.andamento {
    color:#facc15;
}
</style>

</head>

<body>

<h1>📦 PAINEL DE EXPEDIÇÃO</h1>

<div class="grid" id="grid"></div>

<script>
function atualizar(){
fetch('/dados')
.then(r => r.json())
.then(data => {

    let grid = document.getElementById("grid");
    grid.innerHTML = "";

    let grupos = {};

    data.lista.forEach(item => {
        let chave = item.obra + "-" + item.caixa;

        if(!grupos[chave]){
            grupos[chave] = {
                obra: item.obra,
                caixa: item.caixa,
                total: item.total,
                lidos: 0
            };
        }

        grupos[chave].lidos++;
    });

    for(let chave in grupos){

        let g = grupos[chave];

        let card = document.createElement("div");
        card.className = "card";

        let status = "andamento";
        let texto = g.lidos + "/" + (g.total || "?");

        if(g.total && g.lidos == g.total){
            status = "ok";
        }

        card.innerHTML = `
            <div class="titulo">🏗️ Obra ${g.obra}</div>
            <div class="titulo">📦 Caixa ${g.caixa}</div>
            <div class="contador ${status}">${texto}</div>
        `;

        grid.appendChild(card);
    }

});
}

setInterval(atualizar, 1000);
</script>

</body>
</html>
""")

# =========================
# 🚀 START
# =========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)