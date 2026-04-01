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
# SCANNER PROFISSIONAL (FIX SAMSUNG)
# =========================
@app.route('/scanner')
def scanner():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scanner PRO</title>

<script src="https://unpkg.com/html5-qrcode"></script>

<style>
body { text-align:center; font-family:Arial; }
#reader { width:320px; margin:auto; }
</style>
</head>

<body>

<h2>📷 Scanner Profissional</h2>

<div id="reader"></div>

<h2 id="status">Iniciando câmera...</h2>
<h3 id="raw"></h3>

<br>
<a href="/dashboard">📊 Painel</a>

<script>

let ultimo = "";

// ======================
function iniciar(){

    let scanner = new Html5Qrcode("reader");

    scanner.start(
        { facingMode: "environment" },
        {
            fps: 20,
            qrbox: { width: 280, height: 280 }
        },
        (text) => {

            if(text === ultimo) return; // evita duplicado rápido
            ultimo = text;

            processar(text);

            setTimeout(()=>{ ultimo = ""; }, 1500);
        }
    ).then(()=>{
        document.getElementById("status").innerText = "📷 Pronto para leitura";
    }).catch(()=>{
        document.getElementById("status").innerText = "❌ Erro na câmera";
    });
}

// ======================
function processar(text){

    document.getElementById("raw").innerText = text;

    fetch('/scan',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({code:text})
    })
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("status").innerText = d.msg;
    });

    new Audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3").play();
}

iniciar();

</script>

</body>
</html>
"""

# =========================
# PROCESSAMENTO DO QR
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
        return {"msg":f"❌ NÃO RECONHECIDO"}

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
# DADOS
# =========================
@app.route('/dados')
def dados():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT codigo,obra,pacote,data,hora FROM leituras")

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify([{
        "codigo":r[0],
        "obra":r[1],
        "pacote":r[2],
        "data":r[3],
        "hora":r[4]
    } for r in rows])

# =========================
# DASHBOARD COM LUPA
# =========================
@app.route('/dashboard')
def dashboard():
    return """
<h2>📊 Painel</h2>

🔍 <input type="text" id="busca" placeholder="Pesquisar código ou obra">

<button onclick="exportar()">📥 Excel</button>

<h3 id="total"></h3>

<table border="1">
<thead>
<tr><th>Código</th><th>Obra</th><th>Pacote</th><th>Data</th></tr>
</thead>
<tbody id="tb"></tbody>

<script>
let listaGlobal = [];

function carregar(){
    fetch('/dados')
    .then(r=>r.json())
    .then(lista=>{
        listaGlobal = lista;
        render(lista);
    });
}

function render(lista){
    let tb=document.getElementById("tb");
    tb.innerHTML="";

    let cont={};

    lista.forEach(l=>{
        tb.innerHTML+=`<tr>
        <td>${l.codigo}</td>
        <td>${l.obra}</td>
        <td>${l.pacote}</td>
        <td>${l.data}</td>
        </tr>`;

        cont[l.obra]=(cont[l.obra]||0)+1;
    });

    let txt="";
    for(let o in cont){
        txt+=`Obra ${o}: ${cont[o]} | `;
    }

    document.getElementById("total").innerText=txt;
}

document.getElementById("busca").addEventListener("input", function(){
    let termo = this.value.toLowerCase();

    let filtrado = listaGlobal.filter(l =>
        l.codigo.toLowerCase().includes(termo) ||
        l.obra.toLowerCase().includes(termo)
    );

    render(filtrado);
});

function exportar(){
    window.location="/exportar";
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

    cur.execute("SELECT codigo,obra,pacote,data,hora FROM leituras")
    rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Código","Obra","Pacote","Data","Hora"])

    for r in rows:
        ws.append(r)

    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    return send_file(file, download_name="relatorio.xlsx", as_attachment=True)

if __name__ == '__main__':
    app.run()
