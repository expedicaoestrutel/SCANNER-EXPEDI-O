from flask import Flask, request, jsonify, send_file, redirect
from datetime import datetime
import psycopg2
import os
import re
from openpyxl import Workbook
import io

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

# =========================
# HOME
# =========================
@app.route('/')
def home():
    return redirect('/scanner')

# =========================
# SCANNER
# =========================
@app.route('/scanner')
def scanner():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scanner</title>
<script src="https://unpkg.com/html5-qrcode"></script>

<style>
body { background:#0f172a; color:white; text-align:center; font-family:Arial; }
#reader { width:320px; margin:auto; border-radius:10px; overflow:hidden; }
button { padding:10px; border-radius:10px; margin:5px; border:none; }
.flash { background:orange; }
.painel { background:green; }
</style>
</head>

<body>

<h2>📷 Scanner</h2>

<div id="reader"></div>

<button class="flash" onclick="toggleFlash()">🔦 Flash</button>
<button class="painel" onclick="window.location='/dashboard'">📊 Painel</button>

<h3 id="status">Iniciando...</h3>
<div id="raw"></div>

<script>
let scanner;
let flashOn = false;
let ultimo = "";

function iniciar(){
    scanner = new Html5Qrcode("reader");

    scanner.start(
        { facingMode: "environment" },
        { fps:20, qrbox:{width:280,height:280} },
        (text)=>{
            if(text===ultimo) return;
            ultimo=text;

            fetch('/scan',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({code:text})
            })
            .then(r=>r.json())
            .then(d=>{
                document.getElementById("status").innerText=d.msg;
            });

            new Audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3").play();
            if(navigator.vibrate) navigator.vibrate(200);

            setTimeout(()=>{ultimo=""},1500);
        }
    );
}

function toggleFlash(){
    scanner.applyVideoConstraints({
        advanced: [{ torch: !flashOn }]
    });
    flashOn=!flashOn;
}

iniciar();
</script>

</body>
</html>
"""

# =========================
# SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():

    raw = request.json.get('code','')
    texto = raw.upper().strip()

    numeros = re.findall(r"\d+", texto)

    if len(numeros) >= 2:
        pacote = numeros[0]
        obra = numeros[1]
    else:
        return {"msg":"❌ NÃO RECONHECIDO"}

    codigo = f"{obra}.1-{pacote}"

    data = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M:%S")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leituras(
        id SERIAL PRIMARY KEY,
        codigo TEXT UNIQUE,
        obra TEXT,
        pacote TEXT,
        data TEXT,
        hora TEXT
    )
    """)

    try:
        cur.execute("""
        INSERT INTO leituras (codigo, obra, pacote, data, hora)
        VALUES (%s,%s,%s,%s,%s)
        """,(codigo,obra,pacote,data,hora))
        conn.commit()
    except:
        conn.rollback()
        return {"msg":f"⚠️ DUPLICADO {codigo}"}

    cur.close()
    conn.close()

    return {"msg":f"✅ {codigo}"}

# =========================
# DADOS AGRUPADOS
# =========================
@app.route('/dados')
def dados():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id,codigo,obra,pacote FROM leituras ORDER BY pacote")

    rows = cur.fetchall()

    cur.close()
    conn.close()

    agrupado = {}

    for r in rows:
        id, codigo, obra, pacote = r

        if pacote not in agrupado:
            agrupado[pacote] = []

        agrupado[pacote].append({
            "id": id,
            "codigo": codigo,
            "obra": obra
        })

    return jsonify(agrupado)

# =========================
# DELETE
# =========================
@app.route('/delete/<int:id>')
def delete(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM leituras WHERE id=%s",(id,))
    conn.commit()

    cur.close()
    conn.close()

    return "ok"

# =========================
# DASHBOARD ESTILO BARCODE
# =========================
@app.route('/dashboard')
def dashboard():
    return """
<h2>📦 Volumes</h2>

<div id="conteudo"></div>

<script>

function carregar(){
    fetch('/dados')
    .then(r=>r.json())
    .then(dados=>{
        let html="";

        for(let pacote in dados){

            let lista = dados[pacote];

            html+=`
            <div style="border:1px solid #ccc; margin:10px; padding:10px; border-radius:10px;">
                <h3>📦 PACOTE ${pacote} (${lista.length})</h3>
            `;

            lista.forEach(l=>{
                html+=`
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid #eee;">
                    <span>${l.codigo}</span>
                    <button onclick="del(${l.id})">🗑️</button>
                </div>
                `;
            });

            html+=`</div>`;
        }

        document.getElementById("conteudo").innerHTML = html;
    });
}

function del(id){
    fetch('/delete/'+id)
    .then(()=>carregar());
}

carregar();

</script>
"""

# =========================
# EXPORTAR
# =========================
@app.route('/exportar')
def exportar():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT codigo,obra,pacote,data FROM leituras")
    rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Código","Obra","Pacote","Data"])

    for r in rows:
        ws.append(r)

    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    return send_file(file, download_name="relatorio.xlsx", as_attachment=True)

if __name__ == '__main__':
    app.run()
