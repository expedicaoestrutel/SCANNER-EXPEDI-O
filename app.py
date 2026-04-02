from flask import Flask, request, jsonify, send_file, redirect
import psycopg2, os, re, io
from datetime import datetime
from openpyxl import Workbook

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

def db():
    return psycopg2.connect(DATABASE_URL)

# =========================
# CRIAR TABELAS
# =========================
def criar():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leituras(
        id SERIAL PRIMARY KEY,
        pacote TEXT,
        codigo TEXT,
        usuario TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS metas(
        pacote TEXT PRIMARY KEY,
        quantidade INTEGER
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

criar()

# =========================
# DASHBOARD
# =========================
@app.route('/dados')
def dados():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT l.pacote,
           COUNT(l.codigo) as lidos,
           COALESCE(m.quantidade,0) as meta
    FROM leituras l
    LEFT JOIN metas m ON l.pacote = m.pacote
    GROUP BY l.pacote, m.quantidade
    ORDER BY l.pacote
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = []
    for p, lidos, meta in rows:
        if meta == 0:
            status = "andamento"
        elif lidos >= meta:
            status = "completo"
        else:
            status = "faltando"

        result.append({
            "pacote": p,
            "lidos": lidos,
            "meta": meta,
            "status": status
        })

    return jsonify(result)

# =========================
# SALVAR META
# =========================
@app.route('/meta', methods=['POST'])
def meta():
    pacote = request.json['pacote']
    qtd = request.json['qtd']

    conn = db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO metas (pacote, quantidade)
    VALUES (%s,%s)
    ON CONFLICT (pacote)
    DO UPDATE SET quantidade=%s
    """,(pacote,qtd,qtd))

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}

# =========================
# SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    texto = request.json.get('code','').upper().strip()
    usuario = request.json.get('usuario','SEM NOME')

    if "PACOTE" in texto:
        nums = re.findall(r"\d+", texto)
        if nums:
            return {"pacote": nums[0]}

    pacote = request.json.get('pacote')
    if not pacote:
        return {"erro":"sem pacote"}

    conn = db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO leituras (pacote,codigo,usuario)
    VALUES (%s,%s,%s)
    """,(pacote,texto,usuario))

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}

# =========================
# DETALHE VOLUME
# =========================
@app.route('/volume/<pacote>')
def volume(pacote):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT codigo, usuario, data
    FROM leituras
    WHERE pacote=%s
    ORDER BY id DESC
    """,(pacote,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(rows)

# =========================
# EXPORTAR
# =========================
@app.route('/exportar/<pacote>')
def exportar(p):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT codigo, usuario, data
    FROM leituras
    WHERE pacote=%s
    """,(p,))

    rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Código","Usuário","Data"])

    for r in rows:
        ws.append(r)

    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    return send_file(file,
        download_name=f"{p}.xlsx",
        as_attachment=True)

# =========================
# UI PRINCIPAL
# =========================
@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family:Arial; background:#eee; margin:0; }
.header { background:#1e88e5; color:white; padding:15px; text-align:center; }
.card { padding:15px; margin:10px; border-radius:10px; color:white; }
.verde { background:#2e7d32; }
.vermelho { background:#c62828; }
.amarelo { background:#f9a825; color:black; }
</style>
</head>

<body>

<div class="header">📊 DASHBOARD</div>

<div style="padding:10px;">
<input id="user" placeholder="Seu nome">
</div>

<div id="lista"></div>

<script>
function cor(status){
    if(status=="completo") return "verde";
    if(status=="faltando") return "vermelho";
    return "amarelo";
}

function carregar(){
fetch('/dados')
.then(r=>r.json())
.then(d=>{
    let html="";
    d.forEach(v=>{
        html+=`
        <div class="card ${cor(v.status)}" onclick="abrir('${v.pacote}')">
            📦 ${v.pacote}<br>
            ${v.lidos} / ${v.meta}<br>
            ${v.status}
        </div>`;
    });
    document.getElementById("lista").innerHTML=html;
});
}

function abrir(p){
    let user = document.getElementById("user").value || "OPERADOR";
    window.location='/volume-ui/'+p+'?user='+user;
}

carregar();
</script>

</body>
</html>
"""

# =========================
# TELA VOLUME
# =========================
@app.route('/volume-ui/<pacote>')
def volume_ui(pacote):
    return f"""
<!DOCTYPE html>
<html>
<body>

<h3>📦 Volume {pacote}</h3>

<input id="meta" placeholder="Qtd esperada">
<button onclick="salvarMeta()">Salvar Meta</button>

<input placeholder="Pesquisar..." onkeyup="filtrar(this.value)">

<div id="lista"></div>

<script>
const url = new URL(window.location.href);
const user = url.searchParams.get("user");

let dados=[];

function carregar(){
fetch('/volume/{pacote}')
.then(r=>r.json())
.then(d=>{
    dados=d;
    mostrar(d);
});
}

function mostrar(lista){
    let html="";
    lista.forEach(r=>{
        html+=`<div>${{r[0]}} - 👷 ${{r[1]}}</div>`;
    });
    document.getElementById("lista").innerHTML=html;
}

function filtrar(txt){
    txt = txt.toUpperCase();
    let f = dados.filter(x=>x[0].includes(txt));
    mostrar(f);
}

function salvarMeta(){
    let qtd = document.getElementById("meta").value;
    fetch('/meta',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({pacote:"{pacote}", qtd:qtd})
    }).then(()=>alert("Meta salva"));
}

carregar();
</script>

</body>
</html>
"""

# =========================
if __name__ == "__main__":
    app.run()
