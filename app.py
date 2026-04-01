from flask import Flask, request, render_template_string, jsonify, send_file
from datetime import datetime
import psycopg2
import os
import re
from openpyxl import Workbook

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

# =========================
# 🔗 BANCO OU MODO LOCAL
# =========================
def get_db():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return None

leituras_memoria = []

# =========================
# 📷 SCANNER
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

<h2>📷 Scanner Expedição</h2>

<div id="reader" style="width:320px;margin:auto;"></div>

<h2 id="status">Aguardando leitura...</h2>

<br>
<a href="/dashboard">📊 Painel</a> |
<a href="/relatorio">📑 Relatório</a>

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
# 📥 SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    codigo_raw = request.json.get('code', '').strip()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    texto = codigo_raw.upper().replace("\n", " ")

    match_caixa = re.search(r"CAIXA\s*N[ºO]?\s*(\d+)\.(\d+)", texto)
    match_pacote = re.search(r"PACOTE\s*N[ºO]?\s*(\d+)(?:/(\d+))?", texto)

    if match_caixa and match_pacote:
        obra = match_caixa.group(1)
        caixa = match_caixa.group(2)
        pacote = match_pacote.group(1)
        total = match_pacote.group(2) if match_pacote.group(2) else "?"

        codigo = f"{obra}.{caixa}-{pacote}"

        conn = get_db()

        # 🔹 COM BANCO
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS leituras (
                        id SERIAL PRIMARY KEY,
                        codigo TEXT UNIQUE,
                        obra TEXT,
                        caixa TEXT,
                        pacote TEXT,
                        total TEXT,
                        data TEXT
                    )
                """)

                cur.execute("""
                    INSERT INTO leituras (codigo, obra, caixa, pacote, total, data)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (codigo, obra, caixa, pacote, total, agora))

                conn.commit()
            except:
                conn.rollback()
                return {"msg": f"⚠️ DUPLICADO: {codigo}"}
            finally:
                cur.close()
                conn.close()

        # 🔹 SEM BANCO (MEMÓRIA)
        else:
            for item in leituras_memoria:
                if item["codigo"] == codigo:
                    return {"msg": f"⚠️ DUPLICADO: {codigo}"}

            leituras_memoria.append({
                "codigo": codigo,
                "obra": obra,
                "caixa": caixa,
                "pacote": pacote,
                "total": total
            })

        return {"msg": f"✅ {codigo} → {pacote}/{total}"}

    return {"msg": "❌ QR não reconhecido"}

# =========================
# 📊 DADOS
# =========================
@app.route('/dados')
def dados():
    conn = get_db()

    if conn:
        cur = conn.cursor()
        cur.execute("SELECT obra, caixa, pacote, total FROM leituras")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        lista = [{"obra": r[0], "caixa": r[1], "pacote": r[2], "total": r[3]} for r in rows]
    else:
        lista = leituras_memoria

    return jsonify({"lista": lista})

# =========================
# 🖥️ DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    return render_template_string("""
<html>
<head>
<style>
body { background:#0f172a; color:white; font-family:Arial; }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(250px,1fr)); gap:20px; padding:20px;}
.card { background:#1e293b; padding:20px; border-radius:15px;}
.ok { color:#22c55e;}
.andamento { color:#facc15;}
</style>
</head>

<body>
<h1>📦 PAINEL DE EXPEDIÇÃO</h1>
<div class="grid" id="grid"></div>

<script>
function atualizar(){
fetch('/dados')
.then(r=>r.json())
.then(data=>{
    let grid = document.getElementById("grid");
    grid.innerHTML = "";

    let grupos = {};

    data.lista.forEach(item=>{
        let chave = item.obra+"-"+item.caixa;

        if(!grupos[chave]){
            grupos[chave]={...item,lidos:0};
        }

        grupos[chave].lidos++;
    });

    for(let g in grupos){
        let item = grupos[g];
        let status = (item.lidos == item.total) ? "ok" : "andamento";

        let div = document.createElement("div");
        div.className="card";
        div.innerHTML = `
        <h2>Obra ${item.obra}</h2>
        <h3>Caixa ${item.caixa}</h3>
        <h1 class="${status}">${item.lidos}/${item.total}</h1>
        `;
        grid.appendChild(div);
    }
});
}

setInterval(atualizar,1000);
</script>
</body>
</html>
""")

# =========================
# 📑 RELATÓRIO
# =========================
@app.route('/relatorio')
def relatorio():
    return render_template_string("""
<html>
<body style="font-family:Arial">

<h2>📑 Relatório</h2>

<a href="/exportar">
<button>📥 Exportar Excel</button>
</a>

<br><br>
<a href="/dashboard">Voltar</a>

</body>
</html>
""")

# =========================
# 📥 EXPORTAR
# =========================
@app.route('/exportar')
def exportar():
    conn = get_db()

    if conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM leituras")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    else:
        rows = [(i, d["codigo"], d["obra"], d["caixa"], d["pacote"], d["total"], "") for i, d in enumerate(leituras_memoria, 1)]

    wb = Workbook()
    ws = wb.active

    ws.append(["ID","Código","Obra","Caixa","Pacote","Total","Data"])

    for r in rows:
        ws.append(r)

    arquivo = "relatorio.xlsx"
    wb.save(arquivo)

    return send_file(arquivo, as_attachment=True)

# =========================
# START
# =========================
if __name__ == '__main__':
    app.run()
