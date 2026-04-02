from flask import Flask, request, jsonify, Response
import psycopg2, os, re
import pandas as pd

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

    # Leituras
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

    # Lista oficial
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

    obra_match = re.search(r'OBRA\\s*(\\d+)', txt)
    cod_match = re.findall(r'\\d+', txt)

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
        nums = re.findall(r"\\d+", texto_up)
        if nums:
            return {"novo_pacote": nums[0]}

    if not pacotes:
        return {"erro":"sem pacote"}

    codigo, obra = tratar_codigo(texto_up)

    conn = db()
    cur = conn.cursor()

    # 🔥 VALIDAÇÃO NA LISTA
    cur.execute("""
    SELECT qtde FROM lista
    WHERE codigo=%s
    """,(codigo,))

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
# EXPORTAR COMPARAÇÃO
# =========================
@app.route('/comparacao')
def comparacao():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT l.obra, l.codigo, l.qtde,
           COUNT(le.codigo) as conferido
    FROM lista l
    LEFT JOIN leituras le
    ON l.codigo = le.codigo
    GROUP BY l.obra, l.codigo, l.qtde
    """)

    dados = cur.fetchall()

    csv = "OBRA,CODIGO,QTDE,CONFERIDO,STATUS\n"

    for d in dados:
        status = "OK" if d[3] == d[2] else "FALTANDO"
        csv += f"{d[0]},{d[1]},{d[2]},{d[3]},{status}\n"

    cur.close()
    conn.close()

    return Response(csv, mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=comparacao.csv"})

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
body { margin:0; background:#111; color:white; font-family:Arial; }
.btn { padding:10px; margin:5px; background:#00c853; border:none; border-radius:8px; color:white; }
</style>
</head>

<body>

<input id="user" placeholder="Usuário"><br>

<input type="file" id="file">
<button class="btn" onclick="upload()">📥 Importar Lista</button>

<div id="reader"></div>

<script>
let volumes = [];

function upload(){
    let f = document.getElementById("file").files[0];
    let form = new FormData();
    form.append("file", f);

    fetch('/importar_lista',{method:'POST', body:form})
    .then(()=>alert("Lista importada"));
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
        }
        else if(res.erro_lista){
            alert("🚨 PEÇA NÃO ESPERADA: " + res.codigo);
        }
        else if(res.duplicado){
            alert("⚠️ DUPLICADO");
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
