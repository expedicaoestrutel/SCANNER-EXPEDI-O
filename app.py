from flask import Flask, request, jsonify, Response
import psycopg2, os, re
import pandas as pd
from io import BytesIO

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

def db():
    return psycopg2.connect(DATABASE_URL)

def criar():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leituras(
        id SERIAL PRIMARY KEY,
        pacote TEXT,
        codigo TEXT,
        obra TEXT,
        usuario TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

criar()

def tratar_codigo(txt):
    txt = txt.upper()
    obra = None
    codigo = txt

    obra_match = re.search(r'OBRA\s*(\d+)', txt)
    cod_match = re.findall(r'\d+', txt)

    if obra_match:
        obra = obra_match.group(1)

    if cod_match:
        codigo = cod_match[0]

    return codigo, obra

@app.route('/scan', methods=['POST'])
def scan():
    texto = request.json.get('code','').strip()
    usuario = request.json.get('usuario','OPERADOR')
    pacotes = request.json.get('pacotes', [])

    texto_up = texto.upper()

    if "PACOTE" in texto_up:
        nums = re.findall(r"\d+", texto_up)
        if nums:
            return {"novo_pacote": nums[0]}

    if not pacotes:
        return {"erro":"sem pacote"}

    codigo, obra = tratar_codigo(texto_up)

    conn = db()
    cur = conn.cursor()

    duplicado = False

    for p in pacotes:
        cur.execute("""
        SELECT 1 FROM leituras
        WHERE pacote=%s AND codigo=%s
        """,(p,codigo))

        if cur.fetchone():
            duplicado = True
        else:
            cur.execute("""
            INSERT INTO leituras (pacote,codigo,obra,usuario)
            VALUES (%s,%s,%s,%s)
            """,(p,codigo,obra,usuario))

    conn.commit()
    cur.close()
    conn.close()

    if duplicado:
        return {"duplicado": True}

    return {"ok": True}

@app.route('/exportar_excel')
def exportar_excel():
    conn = db()
    df = pd.read_sql("SELECT * FROM leituras", conn)

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')

    if not df.empty:
        for obra in df['obra'].dropna().unique():
            df[df['obra']==obra].to_excel(writer, sheet_name=f"OBRA_{obra}", index=False)

    writer.close()
    output.seek(0)

    return Response(output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":"attachment;filename=expedicao.xlsx"})

@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://unpkg.com/html5-qrcode"></script>

<style>
body { margin:0; background:#111; color:white; font-family:Arial; }

.header { padding:10px; background:#222; display:flex; flex-wrap:wrap; }

.btn { padding:8px; margin:3px; background:#00c853; border:none; border-radius:6px; color:white; }

.volume { margin:10px; padding:10px; border-radius:10px; opacity:0.5; }
.ativo { border:2px solid #00e5ff; opacity:1; }

.item { display:flex; justify-content:space-between; padding:5px; border-bottom:1px solid #333; }

.ok { color:#00e676; }
</style>
</head>

<body>

<div class="header">
<input id="user" placeholder="Usuário">
<button class="btn" onclick="prev()">⬅</button>
<button class="btn" onclick="next()">➡</button>
<button class="btn" onclick="trocarCamera()">📷</button>
<button class="btn" onclick="sync()">🔄</button>
<button class="btn" onclick="limpar()">🗑</button>
</div>

<div id="reader"></div>
<div id="lista"></div>

<script>
let dados = JSON.parse(localStorage.getItem("dados") || "{}");
let atual = null;

function salvar(){ localStorage.setItem("dados", JSON.stringify(dados)); }

function atualizar(){
    let html = "";
    let volumes = Object.keys(dados);

    volumes.forEach(v=>{
        let vol = dados[v];
        let ativo = (v === atual) ? "volume ativo" : "volume";

        html += `<div class="${ativo}" onclick="setAtual('${v}')">
        <b>📦 ${v} (${vol.pecas.length})</b>`;

        vol.pecas.forEach((p,i)=>{
            html += `<div class="item">
                <span>${p}</span>
                <span>
                    <button onclick="ok('${v}',${i})">✔</button>
                    <button onclick="del('${v}',${i})">❌</button>
                </span>
            </div>`;
        });

        html += "</div>";
    });

    document.getElementById("lista").innerHTML = html;
}

function setAtual(v){ atual = v; atualizar(); }

function prev(){
    let vols = Object.keys(dados);
    let i = vols.indexOf(atual);
    if(i>0){ atual = vols[i-1]; atualizar(); }
}

function next(){
    let vols = Object.keys(dados);
    let i = vols.indexOf(atual);
    if(i<vols.length-1){ atual = vols[i+1]; atualizar(); }
}

function limpar(){
    if(atual && confirm("Limpar volume?")){
        dados[atual].pecas = [];
        salvar(); atualizar();
    }
}

function del(v,i){
    dados[v].pecas.splice(i,1);
    salvar(); atualizar();
}

function ok(v,i){
    alert("Conferido ✔");
}

function onScanSuccess(txt){
    txt = txt.toUpperCase();

    if(txt.includes("PACOTE")){
        let n = txt.match(/\\d+/);
        if(n){
            atual = n[0];
            if(!dados[atual]) dados[atual] = {pecas:[]};
            salvar(); atualizar();
            return;
        }
    }

    let cod = txt.match(/\\d+/);
    if(!cod || !atual){ alert("Selecione volume"); return; }

    cod = cod[0];

    if(!dados[atual].pecas.includes(cod)){
        dados[atual].pecas.push(cod);
    } else {
        alert("Duplicado");
    }

    salvar(); atualizar();
}

// CAMERA
let cameras=[], currentCamera=0;
let html5QrCode = new Html5Qrcode("reader");

function iniciarCamera(){
    Html5Qrcode.getCameras().then(devices=>{
        cameras = devices;
        let back = devices.find(d=>d.label.toLowerCase().includes("back"));
        currentCamera = back ? devices.indexOf(back) : 0;
        start(cameras[currentCamera].id);
    });
}

function start(id){
    html5QrCode.start(id,{fps:10,qrbox:250},onScanSuccess);
}

function trocarCamera(){
    currentCamera = (currentCamera+1)%cameras.length;
    html5QrCode.stop().then(()=>start(cameras[currentCamera].id));
}

// SYNC
function sync(){
    let user = document.getElementById("user").value;

    for(let v in dados){
        dados[v].pecas.forEach(c=>{
            fetch('/scan',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({code:c,usuario:user,pacotes:[v]})
            });
        });
    }

    alert("Enviado");
}

iniciarCamera();
atualizar();
</script>

</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
