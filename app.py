from flask import Flask, request, jsonify, Response
import psycopg2, os, re

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

def db():
    return psycopg2.connect(DATABASE_URL)

# =========================
# BANCO
# =========================
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

# =========================
# TRATAR CODIGO
# =========================
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

# =========================
# SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    texto = request.json.get('code','').strip()
    usuario = request.json.get('usuario','OPERADOR')
    pacotes = request.json.get('pacotes', [])

    texto_up = texto.upper()

    # Detecta pacote
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
        return {"duplicado": True, "codigo": codigo}

    return {"ok": True, "codigo": codigo, "obra": obra}

# =========================
# TEMPO REAL
# =========================
@app.route('/realtime')
def realtime():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT pacote,codigo,usuario,data
    FROM leituras
    ORDER BY id DESC
    LIMIT 20
    """)

    dados = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(dados)

# =========================
# EXPORTAR DETALHADO
# =========================
@app.route('/exportar')
def exportar():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT pacote, obra, codigo, usuario, data
    FROM leituras
    ORDER BY pacote, obra
    """)

    dados = cur.fetchall()

    csv = "PACOTE,OBRA,CODIGO,USUARIO,DATA\n"

    for d in dados:
        csv += f"{d[0]},{d[1]},{d[2]},{d[3]},{d[4]}\n"

    cur.close()
    conn.close()

    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=expedicao.csv"}
    )

# =========================
# EXPORTAR RESUMO
# =========================
@app.route('/exportar_resumo')
def exportar_resumo():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT pacote, obra, COUNT(*) as total
    FROM leituras
    GROUP BY pacote, obra
    ORDER BY pacote
    """)

    dados = cur.fetchall()

    csv = "PACOTE,OBRA,TOTAL\n"

    for d in dados:
        csv += f"{d[0]},{d[1]},{d[2]}\n"

    cur.close()
    conn.close()

    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=resumo.csv"}
    )

# =========================
# UI
# =========================
@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://unpkg.com/html5-qrcode"></script>

<style>
body { margin:0; font-family:Arial; background:#111; color:white; }
.header { padding:10px; text-align:center; background:#222; }
.btn { padding:10px; margin:5px; border-radius:8px; background:#00c853; border:none; color:white; }
.tag { display:inline-block; background:#2962ff; padding:5px 10px; margin:3px; border-radius:20px; }
.lista { padding:10px; max-height:250px; overflow:auto; }
.item { border-bottom:1px solid #333; padding:5px; }
</style>
</head>

<body>

<div class="header">
<input id="user" placeholder="Usuário">
</div>

<div id="reader"></div>

<div style="padding:10px;">
<b>Volumes ativos:</b>
<div id="volumes"></div>

<button class="btn" onclick="limpar()">Limpar volumes</button>
<button class="btn" onclick="exportar()">📄 Exportar</button>
<button class="btn" onclick="exportarResumo()">📊 Resumo</button>
</div>

<div class="lista" id="lista"></div>

<script>
let volumes = [];

function atualizarTela(){
    let html="";
    volumes.forEach(v=>{
        html+=`<span class="tag">📦 ${v}</span>`;
    });
    document.getElementById("volumes").innerHTML = html;
}

function limpar(){
    volumes=[];
    atualizarTela();
}

function vibrar(){
    if(navigator.vibrate) navigator.vibrate(100);
}

function atualizarLista(){
    fetch('/realtime')
    .then(r=>r.json())
    .then(dados=>{
        let html="";
        dados.forEach(d=>{
            html+=`<div class="item">📦 ${d[0]} | 🔢 ${d[1]} | 👤 ${d[2]}</div>`;
        });
        document.getElementById("lista").innerHTML = html;
    });
}

setInterval(atualizarLista,2000);

function exportar(){
    window.open('/exportar','_blank');
}

function exportarResumo(){
    window.open('/exportar_resumo','_blank');
}

function onScanSuccess(decodedText) {
    fetch('/scan',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            code: decodedText,
            usuario: document.getElementById("user").value,
            pacotes: volumes
        })
    })
    .then(r=>r.json())
    .then(res=>{
        if(res.novo_pacote){
            if(!volumes.includes(res.novo_pacote)){
                volumes.push(res.novo_pacote);
                atualizarTela();
                vibrar();
            }
        }
        else if(res.duplicado){
            alert("⚠️ DUPLICADO: " + res.codigo);
        }
        else if(res.ok){
            vibrar();
        }
    });
}

const html5QrCode = new Html5Qrcode("reader");

Html5Qrcode.getCameras().then(devices => {
    let back = devices.find(d => d.label.toLowerCase().includes('back')) || devices[0];

    html5QrCode.start(
        back.id,
        { fps: 10, qrbox: 250 },
        onScanSuccess
    );
});
</script>

</body>
</html>
"""

if __name__ == "__main__":
    app.run()
