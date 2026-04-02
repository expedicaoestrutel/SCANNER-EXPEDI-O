from flask import Flask, request, jsonify, redirect
import psycopg2
import os
import re

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

# =========================
@app.route('/')
def home():
    return redirect('/scanner')

# =========================
# SCANNER + UI COMPLETA
# =========================
@app.route('/scanner')
def scanner():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://unpkg.com/html5-qrcode"></script>

<style>
body { background:#0f172a; color:white; font-family:Arial; text-align:center; }

#reader { width:280px; margin:auto; }

input {
    width:90%;
    padding:10px;
    margin:5px;
    border-radius:10px;
    border:none;
}

#volumes {
    display:flex;
    flex-wrap:wrap;
    justify-content:center;
}

.vol {
    padding:8px;
    margin:4px;
    background:#1f2937;
    border-radius:10px;
    cursor:pointer;
}

.ativo {
    background:#22c55e;
}

#pecas {
    max-height:200px;
    overflow:auto;
    background:#111827;
    margin:10px;
    padding:10px;
    border-radius:10px;
    text-align:left;
}

.item {
    border-bottom:1px solid #333;
    padding:6px;
}
</style>
</head>

<body>

<h3>📦 Volumes</h3>
<input id="buscaVol" placeholder="🔍 Buscar volume"/>

<div id="volumes"></div>

<h3>🔩 Peças</h3>
<input id="buscaPeca" placeholder="🔍 Buscar peça"/>

<div id="pecas"></div>

<div id="reader"></div>

<script>
let scanner;
let volumes = {};
let ativos = [];
let ultimo="";

// =========================
// SCANNER
// =========================
function iniciar(){
    scanner = new Html5Qrcode("reader");

    scanner.start(
        { facingMode:"environment" },
        { fps:20, qrbox:{width:250,height:250} },
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

                // PACOTE
                if(d.pacote){
                    if(!volumes[d.pacote]){
                        volumes[d.pacote]=[];
                        renderVolumes();
                    }
                }

                // PEÇA
                if(d.peca){

                    if(ativos.length==0){
                        alert("Selecione um volume");
                        return;
                    }

                    ativos.forEach(v=>{
                        volumes[v].push(d.peca);
                    });

                    renderPecas();
                }
            });

            new Audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3").play();
            if(navigator.vibrate) navigator.vibrate(100);

            setTimeout(()=>{ultimo=""},800);
        }
    );
}

// =========================
// RENDER VOLUMES
// =========================
function renderVolumes(){

    let busca = document.getElementById("buscaVol").value.toLowerCase();
    let html="";

    for(let v in volumes){

        if(!v.includes(busca)) continue;

        let ativo = ativos.includes(v) ? "ativo" : "";

        html+=`<div class="vol ${ativo}" onclick="toggle('${v}')">
        📦 ${v} (${volumes[v].length})
        </div>`;
    }

    document.getElementById("volumes").innerHTML=html;
}

function toggle(v){
    if(ativos.includes(v)){
        ativos = ativos.filter(x=>x!=v);
    } else {
        ativos.push(v);
    }
    renderVolumes();
}

// =========================
// RENDER PEÇAS (TIPO BARCODE)
// =========================
function renderPecas(){

    let busca = document.getElementById("buscaPeca").value.toLowerCase();
    let html="";

    ativos.forEach(v=>{

        html+=`<div><b>📦 ${v}</b></div>`;

        volumes[v].forEach(p=>{
            if(!p.toLowerCase().includes(busca)) return;

            html+=`<div class="item">🔩 ${p}</div>`;
        });
    });

    document.getElementById("pecas").innerHTML=html;
}

// =========================
// BUSCA
// =========================
document.getElementById("buscaVol").onkeyup=renderVolumes;
document.getElementById("buscaPeca").onkeyup=renderPecas;

// =========================
iniciar();
</script>

</body>
</html>
"""

# =========================
# BACKEND
# =========================
@app.route('/scan', methods=['POST'])
def scan():

    texto = request.json.get('code','').upper().strip()

    # PACOTE
    if "PACOTE" in texto:

        nums = re.findall(r"\d+", texto)

        if nums:
            return {"pacote": nums[0]}

    # PEÇA
    return {"peca": texto}

# =========================
if __name__ == '__main__':
    app.run()
