<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Leitor QR - Expedição</title>

<script src="https://unpkg.com/@zxing/browser@0.1.1"></script>

<style>
body {
    margin: 0;
    font-family: Arial;
    background: #f2f2f2;
}

/* HEADER */
.header {
    background: #25346A;
    color: white;
    padding: 15px;
    font-size: 18px;
}

/* BUSCA */
.search {
    padding: 10px;
    background: white;
}

.search input {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #ccc;
}

/* VIDEO */
#video {
    width: 100%;
    height: 250px;
    object-fit: cover;
    display: none;
}

/* SEÇÕES */
.section-title {
    padding: 10px;
    font-weight: bold;
    color: #555;
}

/* ITEM */
.item {
    background: white;
    margin: 5px 10px;
    padding: 15px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
}

/* BOTÕES */
.btn-camera {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #25346A;
    width: 65px;
    height: 65px;
    border-radius: 50%;
    color: white;
    font-size: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-flash {
    position: fixed;
    bottom: 100px;
    right: 20px;
    background: #333;
    color: white;
    padding: 12px;
    border-radius: 50%;
}
</style>
</head>

<body>

<div class="header">RELATÓRIO DE CARGA</div>

<div class="search">
    <input type="text" placeholder="🔎 Buscar volume..." onkeyup="filtrar(this.value)">
</div>

<video id="video"></video>

<div id="lista"></div>

<div class="btn-camera" onclick="iniciar()">📷</div>
<div class="btn-flash" onclick="toggleFlash()">⚡</div>

<script>
let codeReader = new ZXing.BrowserMultiFormatReader();
let lista = [];
let listaFiltrada = [];
let ativo = false;
let streamAtual = null;
let flashLigado = false;

/* INICIAR CAMERA */
async function iniciar() {

    const video = document.getElementById("video");
    video.style.display = "block";

    try {
        const devices = await ZXing.BrowserCodeReader.listVideoInputDevices();

        const traseira = devices[devices.length - 1].deviceId;

        streamAtual = await navigator.mediaDevices.getUserMedia({
            video: {
                deviceId: traseira,
                facingMode: "environment"
            }
        });

        video.srcObject = streamAtual;

        codeReader.decodeFromVideoElement(video, (result, err) => {

            if (result && !ativo) {
                ativo = true;

                let texto = result.getText();

                navigator.vibrate(200);

                if (!lista.includes(texto)) {
                    lista.push(texto);
                    listaFiltrada = lista;
                    atualizarLista();
                }

                setTimeout(() => ativo = false, 1000);
            }
        });

    } catch (e) {
        alert("Erro ao acessar câmera: " + e);
    }
}

/* FLASH REAL */
function toggleFlash() {

    if (!streamAtual) return;

    let track = streamAtual.getVideoTracks()[0];

    let capabilities = track.getCapabilities();

    if (!capabilities.torch) {
        alert("Flash não suportado neste aparelho");
        return;
    }

    flashLigado = !flashLigado;

    track.applyConstraints({
        advanced: [{ torch: flashLigado }]
    });
}

/* FILTRO */
function filtrar(texto) {
    texto = texto.toLowerCase();

    listaFiltrada = lista.filter(item =>
        item.toLowerCase().includes(texto)
    );

    atualizarLista();
}

/* CLASSIFICAÇÃO */
function classificar(item) {
    let t = item.toLowerCase();

    if (t.includes("caixa")) return "CAIXA";
    if (t.includes("pacote")) return "PACOTE";
    return "OUTROS";
}

/* ATUALIZAR LISTA */
function atualizarLista() {

    let div = document.getElementById("lista");
    div.innerHTML = "";

    let caixas = [];
    let pacotes = [];
    let outros = [];

    listaFiltrada.forEach((item, index) => {

        let tipo = classificar(item);

        if (tipo === "CAIXA") caixas.push({item, index});
        else if (tipo === "PACOTE") pacotes.push({item, index});
        else outros.push({item, index});
    });

    montar("CAIXAS", caixas, div);
    montar("PACOTES", pacotes, div);
    montar("OUTROS", outros, div);
}

/* MONTAR SEÇÃO */
function montar(titulo, lista, div) {

    if (lista.length === 0) return;

    div.innerHTML += `<div class="section-title">${titulo}</div>`;

    lista.forEach(obj => {
        div.innerHTML += `
        <div class="item" onclick="editar(${obj.index})">
            <span>${obj.item}</span>
            <span>✔</span>
        </div>`;
    });
}

/* EDITAR */
function editar(index) {

    let novo = prompt("Editar volume:", lista[index]);

    if (novo) {
        lista[index] = novo;
        filtrar("");
    }
}
</script>

</body>
</html>
