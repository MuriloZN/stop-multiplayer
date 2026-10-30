
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

    return true;
}

// Criar sala
botaoCriar.addEventListener("click", () => {
    const nome = nomeCriar.value.trim();

    if (!validarNome(nome)) return;

    botaoCriar.disabled = true;
    mostrarMensagem("Criando sua sala...", false);

    socket.emit("criar_sala", {
        nome: nome
    });
});

// Entrar em uma sala
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
        nome: nome,
        codigo: codigo
    });
});

// Sala criada com sucesso
socket.on("sala_criada", (dados) => {
    sessionStorage.setItem("codigoSala", dados.codigo);
    sessionStorage.setItem("nomeJogador", nomeCriar.value.trim());
    sessionStorage.setItem("anfitriao", "true");

    mostrarMensagem("Sala criada! Código: " + dados.codigo, false);

    window.location.href = "/sala/" + dados.codigo;
});

// Entrada realizada com sucesso
socket.on("entrou_sala", (dados) => {
    sessionStorage.setItem("codigoSala", dados.codigo);
    sessionStorage.setItem("nomeJogador", nomeEntrar.value.trim());
    sessionStorage.setItem("anfitriao", "false");

    mostrarMensagem("Você entrou na sala!", false);

    window.location.href = "/sala/" + dados.codigo;
});

// Erros enviados pelo servidor
socket.on("erro", (dados) => {
    mostrarMensagem(dados.mensagem);

    botaoCriar.disabled = false;
    botaoEntrar.disabled = false;
});

// Problemas de conexão
socket.on("connect_error", () => {
    mostrarMensagem("Não foi possível conectar ao servidor.");

    botaoCriar.disabled = false;
    botaoEntrar.disabled = false;
});

// Reabilitar botões se houver desconexão
socket.on("disconnect", () => {
    botaoCriar.disabled = false;
    botaoEntrar.disabled = false;
});

// Permitir letras maiúsculas no código
codigoSala.addEventListener("input", () => {
    codigoSala.value = codigoSala.value.toUpperCase();
});
