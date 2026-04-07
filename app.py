from flask import Flask, request, jsonify, Response
import psycopg2, os, re
import pandas as pd
from io import BytesIO

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lista(
        id SERIAL PRIMARY KEY,
        obra TEXT,
        codigo TEXT,
        qtde INTEGER
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
# IMPORTAR LISTA
# =========================
@app.route('/importar_lista', methods=['POST'])
def importar_lista():
    file = request.files['file']
    df = pd.read_excel(file)

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lista")

    for _, row in df.iterrows():
        cur.execute("""
        INSERT INTO lista (obra, codigo, qtde)
        VALUES (%s,%s,%s)
        """, (str(row['OBRA']), str(row['CODIGO']), int(row['QTDE'])))

    conn.commit()
    cur.close()
    conn.close()

    return {"ok": True}

# =========================
# SCAN
# =========================
@app.route('/scan', methods=['POST'])
def scan():
    texto = request.json.get('code','').strip()
    usuario = request.json.get('usuario','OPERADOR')
    pacotes = request.json.get('pacotes', [])

    texto_up = texto.upper()

    # PACOTE
    if "PACOTE" in texto_up:
        nums = re.findall(r"\d+", texto_up)
        if nums:
            return {"novo_pacote": nums[0]}

    if not pacotes:
        return {"erro":"sem pacote"}

    codigo, obra = tratar_codigo(texto_up)

    conn = db()
    cur = conn.cursor()

    # VALIDA NA LISTA
    cur.execute("SELECT qtde FROM lista WHERE codigo=%s", (codigo,))
    existe = cur.fetchone()

    if not existe:
        return {"erro_lista": True, "codigo": codigo}

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

    return {"ok": True}

# =========================
# EXPORTAR EXCEL COMPLETO
# =========================
@app.route('/exportar_excel')
def exportar_excel():
    conn = db()
    df = pd.read_sql("""
        SELECT obra, pacote, codigo, usuario, data
        FROM leituras
        ORDER BY obra, pacote
    """, conn)

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')

    for obra in df['obra'].dropna().unique():
        df_obra = df[df['obra'] == obra]
        df_obra.to_excel(writer, sheet_name=f"OBRA_{obra}", index=False)

    writer.close()
    output.seek(0)

    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":"attachment;filename=expedicao.xlsx"}
    )

# =========================
# EXPORTAR SEPARAÇÃO (LUIZ)
# =========================
@app.route('/exportar_obra')
def exportar_obra():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT obra, pacote, codigo
    FROM leituras
    ORDER BY obra, pacote
    """)

    dados = cur.fetchall()

    estrutura = {}

    for obra, pacote, codigo in dados:
        estrutura.setdefault(obra, {})
        estrutura[obra].setdefault(pacote, [])
        estrutura[obra][pacote].append(codigo)

    texto = ""

    for obra in estrutura:
        texto += f"OBRA: {obra}\n\n"

        for pacote in estrutura[obra]:
            texto += f"VOLUME {pacote}\n"
            for cod in estrutura[obra][pacote]:
                texto += f"- {cod}\n"
            texto += "\n"

        texto += "\n---------------------\n\n"

    cur.close()
    conn.close()

    return Response(
        texto,
        mimetype="text/plain",
        headers={"Content-Disposition":"attachment;filename=separacao.txt"}
    )

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
# UI COMPLETA
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
body { margin:0; background:#111; color:white; font-family:Arial; }
.btn { padding:10px; margin:5px; background:#00c853; border:none; border-radius:8px; color:white; }
.tag { display:inline-block; background:#2962ff; padding:5px 10px; margin:3px; border-radius:20px; }
.lista { padding:10px; max-height:250px; overflow:auto; }
</style>
</head>

<body>

<input id="user" placeholder="Usuário"><br>

<input type="file" id="file">
<button class="btn" onclick="upload()">📥 Importar Lista</button>

<div id="reader"></div>

<div>
<b>Volumes:</b>
<div id="volumes"></div>
<button class="btn" onclick="limpar()">Limpar</button>
</div>

<button class="btn" onclick="excel()">📊 Excel</button>
<button class="btn" onclick="obra()">📦 Separação</button>

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

function upload(){
    let f = document.getElementById("file").files[0];
    let form = new FormData();
    form.append("file", f);

    fetch('/importar_lista',{method:'POST', body:form})
    .then(()=>alert("Lista importada"));
}

function excel(){
    window.open('/exportar_excel');
}

function obra(){
    window.open('/exportar_obra');
}

function atualizarLista(){
    fetch('/realtime')
    .then(r=>r.json())
    .then(d=>{
        let html="";
        d.forEach(i=>{
            html+=`<div>📦 ${i[0]} | 🔢 ${i[1]} | 👤 ${i[2]}</div>`;
        });
        document.getElementById("lista").innerHTML = html;
    });
}

setInterval(atualizarLista,2000);

function vibrar(){
    if(navigator.vibrate) navigator.vibrate(100);
}

function onScanSuccess(txt){
    fetch('/scan',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            code: txt,
            usuario: document.getElementById("user").value,
            pacotes: volumes
        })
    })
    .then(r=>r.json())
    .then(res=>{
        if(res.novo_pacote){
            volumes.push(res.novo_pacote);
            atualizarTela();
        }
        else if(res.erro_lista){
            alert("🚨 PEÇA ERRADA: " + res.codigo);
        }
        else if(res.duplicado){
            alert("⚠️ DUPLICADO");
        }
        else{
            vibrar();
        }
    });
}

const html5QrCode = new Html5Qrcode("reader");
Html5Qrcode.getCameras().then(devices=>{
    html5QrCode.start(devices[0].id,{fps:10,qrbox:250},onScanSuccess);
});
</script>

</body>
</html>
"""

if __name__ == "__main__":
    app.run()
