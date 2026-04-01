from flask import Flask, request, jsonify, send_file, redirect, session
from flask import render_template_string
from datetime import datetime
import psycopg2
import os
import re
from openpyxl import Workbook
import io

app = Flask(__name__)
app.secret_key = "expedicao123"

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

# =========================
# LOGIN
# =========================
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if request.form['user'] == "admin" and request.form['senha'] == "123":
            session['logado'] = True
            return redirect('/scanner')

    return """
    <h2>Login</h2>
    <form method="post">
        <input name="user" placeholder="Usuário"><br><br>
        <input name="senha" type="password" placeholder="Senha"><br><br>
        <button>Entrar</button>
    </form>
    """

def protegido():
    return 'logado' in session

# =========================
# SCANNER FORÇADO TRASEIRO
# =========================
@app.route('/scanner')
def scanner():
    if not protegido():
        return redirect('/')

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scanner PRO</title>
<script src="https://unpkg.com/html5-qrcode"></script>
</head>

<body style="text-align:center;font-family:Arial">

<h2>📷 Scanner (Traseira)</h2>

<video id="video" autoplay playsinline style="width:320px;"></video>
<div id="reader" style="width:320px;margin:auto;display:none;"></div>

<h2 id="status">Iniciando câmera traseira...</h2>
<h3 id="raw"></h3>

<br>
<a href="/dashboard">📊 Painel</a>

<script>
let video = document.getElementById("video");
let stream;

// ======================
async function iniciarCamera(){

    try{
        // FORÇA câmera traseira
        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { exact: "environment" }
            }
        });

    }catch(e){
        // fallback se não suportar exact
        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "environment"
            }
        });
    }

    video.srcObject = stream;

    iniciarLeitura();
}

// ======================
function iniciarLeitura(){

    if ('BarcodeDetector' in window) {

        const detector = new BarcodeDetector({
            formats: ['qr_code','code_128','ean_13']
        });

        document.getElementById("status").innerText = "Scanner rápido ativo";

        setInterval(async ()=>{
            try{
                let codes = await detector.detect(video);

                if(codes.length > 0){
                    processar(codes[0].rawValue);
                }
            }catch(e){}
        },500);

    } else {
        iniciarFallback();
    }
}

// ======================
function iniciarFallback(){

    document.getElementById("status").innerText = "Modo compatibilidade";

    video.style.display = "none";
    document.getElementById("reader").style.display = "block";

    let scanner = new Html5Qrcode("reader");

    scanner.start(
        { facingMode: "environment" },
        {
            fps: 15,
            qrbox: { width: 250, height: 250 }
        },
        (text) => processar(text)
    );
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

iniciarCamera();
</script>

</body>
</html>
"""

# =========================
# SCAN (MELHORADO)
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    if not protegido():
        return {"msg":"❌ login"}

    raw = request.json.get('code','')
    texto = raw.upper().strip()

    # 🔥 SUPER REGEX (aceita variações)
    match = re.search(r"(?:PACOTE\\s*N.?\\s*)?(\\d+)\\s*[-–]\\s*(\\d+)", texto)

    if match:
        pacote = match.group(1)
        obra = match.group(2)
    else:
        numeros = re.findall(r"\\d+", texto)
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
# DASHBOARD + EXPORTAÇÃO
# =========================
@app.route('/dados')
def dados():
    if not protegido():
        return []

    data = request.args.get('data')

    conn = get_db()
    cur = conn.cursor()

    if data:
        cur.execute("SELECT codigo,obra,pacote,data,hora FROM leituras WHERE data=%s",(data,))
    else:
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

@app.route('/dashboard')
def dashboard():
    if not protegido():
        return redirect('/')

    return """
<h2>📊 Painel</h2>

<input type="date" id="data">
<button onclick="carregar()">Filtrar</button>
<button onclick="exportar()">Excel</button>

<h3 id="total"></h3>

<table border="1">
<thead>
<tr><th>Código</th><th>Obra</th><th>Pacote</th><th>Data</th></tr>
</thead>
<tbody id="tb"></tbody>

<script>
function carregar(){
    let d=document.getElementById("data").value;

    fetch('/dados?data='+d)
    .then(r=>r.json())
    .then(lista=>{
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
    });
}

function exportar(){
    let d=document.getElementById("data").value;
    window.location="/exportar?data="+d;
}

carregar();
</script>
"""

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
