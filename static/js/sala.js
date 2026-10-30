
const socket = io();

// DADOS DO JOGADOR

const codigo = sessionStorage.getItem("codigoSala");
const token = sessionStorage.getItem("tokenJogador");

const listaJogadores = document.getElementById("lista-jogadores");
const contador = document.getElementById("contador-jogadores");
const mensagem = document.getElementById("mensagem-sala");

const botaoCopiar = document.getElementById("btn-copiar");
const botaoIniciar = document.getElementById("btn-iniciar");

const temaInput = document.getElementById("tema-input");
const botaoAdicionarTema = document.getElementById("btn-adicionar-tema");
const listaTemas = document.getElementById("lista-temas");

const tempoRodada = document.getElementById("tempo-rodada");
const numeroRodadas = document.getElementById("numero-rodadas");

let souAnfitriao = false;
let temasAtuais = [];
let partidaIniciada = false;

if (!codigo || !token) {
    window.location.href = "/";
}


// FUNÇÕES AUXILIARES

function enviarDados(dados = {}) {
    return {
        codigo: codigo,
        token: token,
        ...dados
    };
}

function mostrarMensagem(texto, erro = false) {
    mensagem.textContent = texto;
    mensagem.style.color = erro ? "#f87171" : "#a78bfa";
}


// LISTA DE JOGADORES

function atualizarLista(jogadores) {
    listaJogadores.innerHTML = "";

    contador.textContent =
        jogadores.length +
        (jogadores.length === 1 ? " jogador" : " jogadores");

    jogadores.forEach((jogador, indice) => {
        const item = document.createElement("div");
        item.className = "player-item";

        const avatar = document.createElement("div");
        avatar.className = "player-avatar";
        avatar.textContent = jogador.nome.charAt(0).toUpperCase();

        const nome = document.createElement("span");
        nome.className = "player-name";
        nome.textContent = jogador.nome;

        item.appendChild(avatar);
        item.appendChild(nome);

        if (indice === 0) {
            const anfitriao = document.createElement("span");
            anfitriao.textContent = " 👑";
            nome.appendChild(anfitriao);
        }

        if (!jogador.conectado) {
            const status = document.createElement("small");
            status.textContent = " (desconectado)";
            nome.appendChild(status);
        }

        listaJogadores.appendChild(item);
    });
}


// TEMAS

function atualizarTemas(temas) {
    temasAtuais = temas;
    listaTemas.innerHTML = "";

    if (temas.length === 0) {
        listaTemas.textContent = "Nenhum tema adicionado.";
    }

    temas.forEach((tema, indice) => {
        const item = document.createElement("div");
        item.className = "player-item";

        const nome = document.createElement("span");
        nome.textContent = `${indice + 1}. ${tema}`;

        item.appendChild(nome);

        if (souAnfitriao && !partidaIniciada) {
            const remover = document.createElement("button");
            remover.textContent = "Remover";
            remover.type = "button";

            remover.addEventListener("click", () => {
                socket.emit(
                    "remover_tema",
                    enviarDados({ indice: indice })
                );
            });

            item.appendChild(remover);
        }

        listaTemas.appendChild(item);
    });

    temaInput.disabled = partidaIniciada || temas.length >= 10;
    botaoAdicionarTema.disabled =
        partidaIniciada || temas.length >= 10;

    atualizarBotaoIniciar();
}

function adicionarTema() {
    const tema = temaInput.value.trim();

    if (!tema) {
        mostrarMensagem("Digite um tema antes de adicionar.", true);
        return;
    }

    if (tema.length > 30) {
        mostrarMensagem("O tema deve ter até 30 caracteres.", true);
        return;
    }

    socket.emit(
        "adicionar_tema",
        enviarDados({ tema: tema })
    );

    temaInput.value = "";
}

botaoAdicionarTema.addEventListener("click", adicionarTema);

temaInput.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") {
        adicionarTema();
    }
});


// CONFIGURAÇÕES

function alterarConfiguracoes() {
    if (!souAnfitriao || partidaIniciada) return;

    socket.emit(
        "alterar_configuracoes",
        enviarDados({
            configuracoes: {
                tempo: Number(tempoRodada.value),
                rodadas: Number(numeroRodadas.value)
            }
        })
    );
}

tempoRodada.addEventListener("change", alterarConfiguracoes);
numeroRodadas.addEventListener("change", alterarConfiguracoes);


// BOTÃO DE INICIAR

function atualizarBotaoIniciar() {
    botaoIniciar.disabled =
        !souAnfitriao ||
        temasAtuais.length === 0 ||
        partidaIniciada;
}

botaoIniciar.addEventListener("click", () => {
    if (!souAnfitriao || temasAtuais.length === 0) return;

    botaoIniciar.disabled = true;
    mostrarMensagem("Preparando a partida...");

    socket.emit("iniciar_partida", enviarDados());
});


// COPIAR CÓDIGO

botaoCopiar.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(codigo);

        botaoCopiar.textContent = "COPIADO!";

        setTimeout(() => {
            botaoCopiar.textContent = "COPIAR CÓDIGO";
        }, 2000);

    } catch (erro) {
        mostrarMensagem("Não foi possível copiar o código.", true);
    }
});


// CONEXÃO COM O SERVIDOR

socket.on("connect", () => {
    socket.emit(
        "reconectar_sala",
        enviarDados()
    );
});

socket.on("sala_reconectada", (dados) => {
    souAnfitriao = dados.anfitriao;

    atualizarLista(dados.jogadores);

    mostrarMensagem(
        souAnfitriao
            ? "Você é o anfitrião desta sala."
            : "Você entrou na sala. Aguarde o anfitrião."
    );
});

socket.on("atualizar_jogadores", (dados) => {
    atualizarLista(dados.jogadores);
});

socket.on("estado_sala", (dados) => {
    atualizarTemas(dados.temas);

    const configuracoes = dados.configuracoes;

    tempoRodada.value = configuracoes.tempo;
    numeroRodadas.value = configuracoes.rodadas;

    tempoRodada.disabled = !souAnfitriao || partidaIniciada;
    numeroRodadas.disabled = !souAnfitriao || partidaIniciada;

    atualizarBotaoIniciar();
});

socket.on("partida_pronta", (dados) => {
    partidaIniciada = true;

    atualizarTemas(dados.temas);

    temaInput.disabled = true;
    botaoAdicionarTema.disabled = true;
    tempoRodada.disabled = true;
    numeroRodadas.disabled = true;
    botaoIniciar.disabled = true;

    mostrarMensagem(
        "Configurações confirmadas! Preparando a partida..."
    );
});

socket.on("rodada_iniciada", () => {
    window.location.href = "/partida/" + codigo;
});

socket.on("erro", (dados) => {
    mostrarMensagem(dados.mensagem, true);
    atualizarBotaoIniciar();
});

socket.on("connect_error", () => {
    mostrarMensagem("Erro de conexão com o servidor.", true);
});
