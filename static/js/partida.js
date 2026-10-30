
const socket = io();

// DADOS DO JOGADOR

const codigo = sessionStorage.getItem("codigoSala");
const token = sessionStorage.getItem("tokenJogador");

const letraAtual = document.getElementById("letra-atual");
const rodadaAtual = document.getElementById("rodada-atual");
const cronometro = document.getElementById("cronometro");

const camposRespostas = document.getElementById("campos-respostas");
const botaoStop = document.getElementById("btn-stop");
const mensagem = document.getElementById("mensagem-partida");

const ranking = document.getElementById("ranking-jogadores");

let tempoRestante = 0;
let intervalo = null;
let rodadaEncerrada = false;

if (!codigo || !token) {
    window.location.href = "/";
}


// FUNÇÕES AUXILIARES

function enviarDados(dados = {}) {
    return {
        codigo,
        token,
        ...dados
    };
}

function mostrarMensagem(texto, erro = false) {
    mensagem.textContent = texto;
    mensagem.style.color = erro ? "#f87171" : "#a78bfa";
}


// CRIAR CAMPOS DE RESPOSTA

function criarCampos(temas) {
    camposRespostas.innerHTML = "";

    temas.forEach((tema, indice) => {
        const grupo = document.createElement("div");
        grupo.className = "campo-resposta";

        const label = document.createElement("label");
        label.textContent = tema;
        label.htmlFor = "resposta-" + indice;

        const input = document.createElement("input");
        input.type = "text";
        input.id = "resposta-" + indice;
        input.name = "resposta-" + indice;
        input.maxLength = 100;
        input.placeholder = "Digite sua resposta...";
        input.autocomplete = "off";

        input.addEventListener("input", atualizarBotaoStop);

        grupo.appendChild(label);
        grupo.appendChild(input);

        camposRespostas.appendChild(grupo);
    });

    atualizarBotaoStop();
}


// VERIFICAR SE TODAS AS RESPOSTAS FORAM PREENCHIDAS

function atualizarBotaoStop() {
    const campos = camposRespostas.querySelectorAll("input");

    const todosPreenchidos =
        campos.length > 0 &&
        Array.from(campos).every(
            campo => campo.value.trim() !== ""
        );

    botaoStop.disabled =
        !todosPreenchidos || rodadaEncerrada;
}


// CRONÔMETRO

function iniciarCronometro(tempo) {
    clearInterval(intervalo);

    tempoRestante = tempo;
    atualizarCronometro();

    if (tempoRestante <= 0) {
        encerrarLocalmente();
        return;
    }

    intervalo = setInterval(() => {
        tempoRestante--;

        atualizarCronometro();

        if (tempoRestante <= 0) {
            encerrarLocalmente();
        }
    }, 1000);
}

function atualizarCronometro() {
    const minutos = Math.floor(tempoRestante / 60);
    const segundos = tempoRestante % 60;

    cronometro.textContent =
        String(minutos).padStart(2, "0") +
        ":" +
        String(segundos).padStart(2, "0");
}


// MOSTRAR RODADA

function mostrarRodada(dados) {
    rodadaEncerrada = false;

    letraAtual.textContent = dados.letra;

    rodadaAtual.textContent =
        dados.rodada + " / " + dados.total_rodadas;

    criarCampos(dados.temas);

    botaoStop.disabled = true;

    mostrarMensagem("Preencha todas as categorias!");

    iniciarCronometro(dados.tempo);
}


// ENCERRAR LOCALMENTE

function encerrarLocalmente() {
    rodadaEncerrada = true;

    clearInterval(intervalo);

    botaoStop.disabled = true;

    camposRespostas.querySelectorAll("input").forEach(campo => {
        campo.disabled = true;
    });

    mostrarMensagem("Tempo encerrado! Aguardando resultado...");
}


// BOTÃO STOP

botaoStop.addEventListener("click", () => {
    if (rodadaEncerrada) return;

    atualizarBotaoStop();

    if (botaoStop.disabled) return;

    const respostas = {};

    camposRespostas.querySelectorAll("input").forEach(campo => {
        respostas[campo.id] = campo.value.trim();
    });

    rodadaEncerrada = true;

    clearInterval(intervalo);

    botaoStop.disabled = true;

    camposRespostas.querySelectorAll("input").forEach(campo => {
        campo.disabled = true;
    });

    mostrarMensagem("STOP solicitado! Aguarde os outros jogadores.");

    socket.emit(
        "parar_rodada",
        enviarDados({ respostas })
    );
});


// CONEXÃO COM O SERVIDOR

socket.on("connect", () => {
    socket.emit(
        "carregar_partida",
        enviarDados()
    );
});

socket.on("estado_partida", (dados) => {
    mostrarRodada(dados);
});

socket.on("rodada_iniciada", (dados) => {
    mostrarRodada(dados);
});

socket.on("erro", (dados) => {
    mostrarMensagem(dados.mensagem, true);
});

socket.on("connect_error", () => {
    mostrarMensagem("Erro de conexão com o servidor.", true);
});
