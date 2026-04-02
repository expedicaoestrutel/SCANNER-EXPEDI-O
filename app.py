from flask import Flask, request, jsonify, send_file, redirect
import psycopg2
import os
import re
from datetime import datetime
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
    return redirect('/app')

# =========================
# CRIAR TABELA
# =========================
def criar():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leituras(
        id SERIAL PRIMARY KEY,
        pacote TEXT,
        codigo TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

criar()

# =========================
# LISTA DE VOLUMES
# =========================
@app.route('/dados')
def dados():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT pacote, COUNT(*) 
    FROM leituras
    GROUP BY pacote
    ORDER BY pacote
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    lista = []

    for r in rows:
        lista.append({
            "pacote": r[0],
            "total": r[1]
        })

    return jsonify(lista)

# =========================
# DETALHE DO VOLUME
# =========================
@app.route('/volume/<pacote>')
def volume(pacote):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT codigo FROM leituras
    WHERE pacote=%s
    ORDER BY id DESC
    """,(pacote,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify([r[0] for r in rows])

# =========================
# SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():

    texto = request.json.get('code','').upper().strip()

    conn = get_db()
    cur = conn.cursor()

    # PACOTE
    if "PACOTE" in texto:

        nums = re.findall(r"\d+", texto)

        if nums:
            return {"pacote": nums[0]}

    # PEÇA
    pacote = request.json.get('pacote')

    if not pacote:
        return {"msg":"sem pacote"}

    cur.execute("""
    INSERT INTO leituras (pacote,codigo)
    VALUES (%s,%s)
    """,(pacote,texto))

    conn.commit()

    cur.close()
    conn.close()

    return {"ok": True}

# =========================
# EXPORTAR EXCEL POR VOLUME
# =========================
@app.route('/exportar/<pacote>')
def exportar(pacote):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT codigo, data FROM leituras
    WHERE pacote=%s
    """,(pacote,))

    rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Código","Data"])

    for r in rows:
        ws.append(r)

    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    return send_file(file,
        download_name=f"volume_{pacote}.xlsx",
        as_attachment=True)

# =========================
# UI PRINCIPAL (ESTILO APP)
# =========================
@app.route('/app')
def app_ui():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>
body { margin:0; font-family:Arial; background:#eee; }

.header {
    background:#d32f2f;
    color:white;
    padding:15px;
    font-size:20px;
    text-align:center;
}

.card {
    background:white;
    margin:10px;
    padding:15px;
    border-radius:10px;
}

.fab {
    position:fixed;
    bottom:20px;
    right:20px;
    background:#f44336;
    width:60px;
    height:60px;
    border-radius:50%;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:28px;
    color:white;
}
</style>
</head>

<body>

<div class="header">Sessões de leitura</div>

<div id="lista"></div>

<div class="fab" onclick="window.location='/scanner'">📷</div>

<script>
function carregar(){

    fetch('/dados')
    .then(r=>r.json())
    .then(d=>{

        let html="";

        d.forEach(v=>{

            html+=`
            <div class="card" onclick="abrir('${v.pacote}')">
                <b>📦 PACOTE ${v.pacote}</b><br>
                Leituras: ${v.total}<br>
                <button onclick="exportar('${v.pacote}')">Excel</button>
            </div>
            `;
        });

        document.getElementById("lista").innerHTML=html;
    });
}

function abrir(p){
    window.location='/detalhe/'+p;
}

function exportar(p){
    window.location='/exportar/'+p;
}

carregar();
</script>

</body>
</html>
"""

# =========================
# DETALHE
# =========================
@app.route('/detalhe/<pacote>')
def detalhe(pacote):
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family:Arial; }}
.item {{ padding:10px; border-bottom:1px solid #ccc; }}
</style>
</head>

<body>

<h3>📦 PACOTE {pacote}</h3>

<div id="lista"></div>

<script>
fetch('/volume/{pacote}')
.then(r=>r.json())
.then(d=>{{
    let html="";
    d.forEach(p=>html+=`<div class="item">${{p}}</div>`);
    document.getElementById("lista").innerHTML=html;
}});
</script>

</body>
</html>
"""

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
<script src="https://unpkg.com/html5-qrcode"></script>

<body>

<h3>Scanner</h3>
<div id="reader"></div>

<script>
let scanner;
let pacote="";

function iniciar(){
    scanner = new Html5Qrcode("reader");

    scanner.start(
        { facingMode:"environment" },
        { fps:20, qrbox:250 },
        (text)=>{

            fetch('/scan',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({code:text, pacote:pacote})
            })
            .then(r=>r.json())
            .then(d=>{

                if(d.pacote){
                    pacote = d.pacote;
                    alert("PACOTE "+pacote);
                }

            });

            new Audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3").play();
        }
    );
}

iniciar();
</script>

</body>
</html>
"""

# =========================
if __name__ == '__main__':
    app.run()
