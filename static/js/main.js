
const socket = io();

const botaoCriar = document.getElementById("btn-criar");
const botaoEntrar = document.getElementById("btn-entrar");

const nomeCriar = document.getElementById("nome-criar");
const nomeEntrar = document.getElementById("nome-entrar");
const codigoSala = document.getElementById("codigo-sala");

const mensagem = document.getElementById("mensagem");

function mostrarMensagem(texto, erro = true) {
    mensagem.textContent = texto;
    mensagem.style.color = erro ? "#f87171" : "#4ade80";
}

function validarNome(nome) {
    if (!nome.trim()) {
        mostrarMensagem("Digite seu nome para continuar.");
        return false;
    }

    if (nome.trim().length > 20) {
        mostrarMensagem("Seu nome deve ter até 20 caracteres.");
        return false;
    }

    return true;
}

botaoCriar.addEventListener("click", () => {
    const nome = nomeCriar.value.trim();

    if (!validarNome(nome)) return;

    botaoCriar.disabled = true;
    mostrarMensagem("Criando sua sala...", false);

    socket.emit("criar_sala", { nome });
});

botaoEntrar.addEventListener("click", () => {
    const nome = nomeEntrar.value.trim();
    const codigo = codigoSala.value.trim().toUpperCase();

    if (!validarNome(nome)) return;

    if (!codigo) {
        mostrarMensagem("Digite o código da sala.");
        return;
    }

    botaoEntrar.disabled = true;
    mostrarMensagem("Procurando sala...", false);

    socket.emit("entrar_sala", {
        nome,
        codigo
    });
});

socket.on("sala_criada", (dados) => {
    sessionStorage.setItem("codigoSala", dados.codigo);
    sessionStorage.setItem("tokenJogador", dados.token);
    sessionStorage.setItem("nomeJogador", nomeCriar.value.trim());

    window.location.href = "/sala/" + dados.codigo;
});

socket.on("entrou_sala", (dados) => {
    sessionStorage.setItem("codigoSala", dados.codigo);
    sessionStorage.setItem("tokenJogador", dados.token);
    sessionStorage.setItem("nomeJogador", nomeEntrar.value.trim());

    window.location.href = "/sala/" + dados.codigo;
});

socket.on("erro", (dados) => {
    mostrarMensagem(dados.mensagem);

    botaoCriar.disabled = false;
    botaoEntrar.disabled = false;
});

socket.on("connect_error", () => {
    mostrarMensagem("Erro de conexão com o servidor.");

    botaoCriar.disabled = false;
    botaoEntrar.disabled = false;
});

codigoSala.addEventListener("input", () => {
    codigoSala.value = codigoSala.value.toUpperCase();
});
