
const socket = io();

const codigo = sessionStorage.getItem("codigoSala");
const token = sessionStorage.getItem("tokenJogador");

const listaJogadores = document.getElementById("lista-jogadores");
const contador = document.getElementById("contador-jogadores");
const mensagem = document.getElementById("mensagem-sala");
const botaoCopiar = document.getElementById("btn-copiar");
const botaoIniciar = document.getElementById("btn-iniciar");

let souAnfitriao = false;

if (!codigo || !token) {
    window.location.href = "/";
}

socket.on("connect", () => {
    socket.emit("reconectar_sala", {
        codigo: codigo,
        token: token
    });
});

function atualizarLista(jogadores) {
    listaJogadores.innerHTML = "";

    contador.textContent =
        jogadores.length + (jogadores.length === 1 ? " jogador" : " jogadores");

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

        listaJogadores.appendChild(item);
    });
}

socket.on("sala_reconectada", (dados) => {
    souAnfitriao = dados.anfitriao;

    atualizarLista(dados.jogadores);

    mensagem.textContent = souAnfitriao
        ? "Você é o anfitrião desta sala."
        : "Você entrou na sala. Aguarde o anfitrião.";

    mensagem.style.color = "#a78bfa";
});

socket.on("atualizar_jogadores", (dados) => {
    atualizarLista(dados.jogadores);
});

socket.on("erro", (dados) => {
    mensagem.textContent = dados.mensagem;
    mensagem.style.color = "#f87171";
});

botaoCopiar.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(codigo);

        botaoCopiar.textContent = "COPIADO!";
        
        setTimeout(() => {
            botaoCopiar.textContent = "COPIAR CÓDIGO";
        }, 2000);

    } catch (erro) {
        mensagem.textContent = "Não foi possível copiar o código.";
    }
});
