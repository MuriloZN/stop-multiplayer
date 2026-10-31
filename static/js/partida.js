
const socket = io();

// ==========================================
// DADOS DO JOGADOR
// ==========================================

const codigo = sessionStorage.getItem("codigoSala");
const token = sessionStorage.getItem("tokenJogador");

const letraAtual = document.getElementById("letra-atual");
const rodadaAtual = document.getElementById("rodada-atual");
const cronometro = document.getElementById("cronometro");

const areaRespostas = document.getElementById("area-respostas");
const camposRespostas = document.getElementById("campos-respostas");
const botaoStop = document.getElementById("btn-stop");

const areaVotacao = document.getElementById("area-votacao");
const cronometroVotacao = document.getElementById("cronometro-votacao");
const listaRespostasVotacao = document.getElementById("lista-respostas-votacao");

const areaResultado = document.getElementById("area-resultado");
const resultadoRespostas = document.getElementById("resultado-respostas");

const mensagem = document.getElementById("mensagem-partida");
const ranking = document.getElementById("ranking-jogadores");

let intervalo = null;
let intervaloVotacao = null;

let tempoRestante = 0;
let rodadaEncerrada = false;
let faseAtual = "aguardando";

let respostasVotacao = {};
let respostasVotadas = new Set();
let controlesVotacao = {};

if (!codigo || !token) {
    window.location.href = "/";
}


// ==========================================
// FUNÇÕES AUXILIARES
// ==========================================

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

function limparIntervalos() {
    clearInterval(intervalo);
    clearInterval(intervaloVotacao);
}

function formatarTempo(tempo) {
    const minutos = Math.floor(tempo / 60);
    const segundos = tempo % 60;

    return (
        String(minutos).padStart(2, "0") +
        ":" +
        String(segundos).padStart(2, "0")
    );
}


// ==========================================
// CRIAR CAMPOS DE RESPOSTA
// ==========================================

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

        input.addEventListener("input", () => {
            atualizarBotaoStop();

            const respostas = {};

            camposRespostas.querySelectorAll("input").forEach(campo => {
                respostas[campo.id] = campo.value.trim();
            });

            socket.emit(
                "atualizar_respostas",
                enviarDados({ respostas })
            );
        });

        grupo.appendChild(label);
        grupo.appendChild(input);

        camposRespostas.appendChild(grupo);
    });

    atualizarBotaoStop();
}


// ==========================================
// VERIFICAR RESPOSTAS PREENCHIDAS
// ==========================================

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


// ==========================================
// CRONÔMETRO DA RODADA
// ==========================================

function iniciarCronometro(tempo) {
    clearInterval(intervalo);

    tempoRestante = tempo;

    cronometro.textContent = formatarTempo(tempoRestante);

    if (tempoRestante <= 0) {
        encerrarLocalmente(
            "Tempo encerrado! Aguardando o servidor..."
        );
        return;
    }

    intervalo = setInterval(() => {
        tempoRestante--;

        cronometro.textContent = formatarTempo(tempoRestante);

        if (tempoRestante <= 0) {
            encerrarLocalmente(
                "Tempo encerrado! Aguardando resultado..."
            );
        }
    }, 1000);
}


// ==========================================
// BLOQUEAR CAMPOS
// ==========================================

function bloquearCampos() {
    camposRespostas.querySelectorAll("input").forEach(campo => {
        campo.disabled = true;
    });

    botaoStop.disabled = true;
}


// ==========================================
// MOSTRAR RODADA
// ==========================================

function mostrarRodada(dados) {
    limparIntervalos();

    faseAtual = "respondendo";
    rodadaEncerrada = false;

    areaRespostas.hidden = false;
    areaVotacao.hidden = true;
    areaResultado.hidden = true;

    letraAtual.textContent = dados.letra;

    rodadaAtual.textContent =
        dados.rodada + " / " + dados.total_rodadas;

    criarCampos(dados.temas);

    mostrarMensagem("Preencha todas as categorias!");

    iniciarCronometro(dados.tempo);
}


// ==========================================
// ENCERRAR LOCALMENTE
// ==========================================

function encerrarLocalmente(texto) {
    rodadaEncerrada = true;

    clearInterval(intervalo);

    bloquearCampos();

    mostrarMensagem(texto);
}


// ==========================================
// BOTÃO STOP
// ==========================================

botaoStop.addEventListener("click", () => {
    if (rodadaEncerrada || faseAtual !== "respondendo") {
        return;
    }

    atualizarBotaoStop();

    if (botaoStop.disabled) {
        return;
    }

    const respostas = {};

    camposRespostas.querySelectorAll("input").forEach(campo => {
        respostas[campo.id] = campo.value.trim();
    });

    rodadaEncerrada = true;

    clearInterval(intervalo);

    bloquearCampos();

    mostrarMensagem("STOP solicitado! Encerrando rodada...");

    socket.emit(
        "parar_rodada",
        enviarDados({ respostas })
    );
});


// ==========================================
// MOSTRAR FASE DE VOTAÇÃO
// ==========================================

function mostrarVotacao(dados) {
    limparIntervalos();

    faseAtual = "votacao";
    rodadaEncerrada = true;

    areaRespostas.hidden = true;
    areaVotacao.hidden = false;
    areaResultado.hidden = true;

    letraAtual.textContent = dados.letra;

    respostasVotacao = {};
    respostasVotadas.clear();

    listaRespostasVotacao.innerHTML = "";

    // Agrupa as respostas em uma coluna/seção para cada tema.
    const gruposPorTema = new Map();

    dados.respostas.forEach(item => {
        respostasVotacao[item.id] = item;

        if (!gruposPorTema.has(item.tema)) {
            const grupo = document.createElement("section");
            grupo.className = "grupo-tema-votacao";

            const tituloTema = document.createElement("h3");
            tituloTema.className = "titulo-tema-votacao";
            tituloTema.textContent = item.tema;

            const listaTema = document.createElement("div");
            listaTema.className = "respostas-do-tema";

            grupo.appendChild(tituloTema);
            grupo.appendChild(listaTema);
            listaRespostasVotacao.appendChild(grupo);
            gruposPorTema.set(item.tema, listaTema);
        }

        const card = document.createElement("article");
        card.className = "campo-resposta resposta-votacao";

        const jogador = document.createElement("p");
        jogador.textContent = "Jogador: " + item.jogador;

        const resposta = document.createElement("div");
        resposta.className = "resposta-destaque-votacao";

        const rotuloResposta = document.createElement("span");
        rotuloResposta.className = "rotulo-resposta-votacao";
        rotuloResposta.textContent = "RESPOSTA";

        const textoResposta = document.createElement("strong");
        textoResposta.className = "texto-resposta-votacao";
        textoResposta.textContent = item.resposta;

        resposta.appendChild(rotuloResposta);
        resposta.appendChild(textoResposta);

        const votos = document.createElement("p");
        votos.id = "votos-" + item.id;
        votos.textContent =
            `${item.votos} / ${dados.votos_necessarios} votos para invalidar`;

        const acoesVoto = document.createElement("div");
        acoesVoto.className = "acoes-votacao";

        const botao = document.createElement("button");
        botao.type = "button";
        botao.className = "btn-secondary";
        botao.textContent = "Votar para invalidar";

        const botaoRemover = document.createElement("button");
        botaoRemover.type = "button";
        botaoRemover.className = "btn-remover-voto";
        botaoRemover.textContent = "Remover voto";
        botaoRemover.hidden = true;

        botao.addEventListener("click", () => {
            if (respostasVotadas.has(item.id)) return;
            respostasVotadas.add(item.id);
            botao.disabled = true;
            botaoRemover.hidden = false;
            socket.emit("votar_resposta", enviarDados({ resposta_id: item.id }));
        });

        botaoRemover.addEventListener("click", () => {
            if (!respostasVotadas.has(item.id)) return;
            respostasVotadas.delete(item.id);
            botaoRemover.disabled = true;
            socket.emit("remover_voto_resposta", enviarDados({ resposta_id: item.id }));
        });

        controlesVotacao[item.id] = { card, botao, botaoRemover };
        acoesVoto.appendChild(botao);
        acoesVoto.appendChild(botaoRemover);

        if (!item.valida_letra) {
            const aviso = document.createElement("p");
            aviso.className = "aviso-resposta-invalida";
            aviso.textContent = "Não começa com a letra sorteada.";
            card.appendChild(aviso);
        }

        card.appendChild(jogador);
        card.appendChild(resposta);
        card.appendChild(votos);
        card.appendChild(acoesVoto);

        gruposPorTema.get(item.tema).appendChild(card);
    });

    mostrarMensagem("Vote nas respostas que considerar incorretas.");

    iniciarCronometroVotacao(dados.tempo);
}


// ==========================================
// CRONÔMETRO DA VOTAÇÃO
// ==========================================

function iniciarCronometroVotacao(tempo) {
    clearInterval(intervaloVotacao);

    let restante = tempo;

    cronometroVotacao.textContent =
        "Tempo para votar: " + restante + " segundos";

    intervaloVotacao = setInterval(() => {
        restante--;

        cronometroVotacao.textContent =
            "Tempo para votar: " + Math.max(0, restante) + " segundos";

        if (restante <= 0) {
            clearInterval(intervaloVotacao);
        }
    }, 1000);
}


// ==========================================
// ATUALIZAR VOTOS NA TELA
// ==========================================

socket.on("votacao_atualizada", dados => {
    const contador = document.getElementById("votos-" + dados.resposta_id);
    const controles = controlesVotacao[dados.resposta_id];

    if (contador) {
        contador.textContent =
            `${dados.votos} / ${dados.votos_necessarios} votos para invalidar`;
    }

    if (controles) {
        controles.card.classList.toggle(
            "votacao-em-disputa",
            dados.votos > 0 && dados.votos < dados.votos_necessarios
        );
        controles.card.classList.toggle(
            "votacao-invalidada",
            dados.votos >= dados.votos_necessarios
        );

        const jaVotou = respostasVotadas.has(dados.resposta_id);
        controles.botao.disabled = jaVotou;
        controles.botao.textContent = jaVotou ? "Voto enviado" : "Votar para invalidar";
        controles.botaoRemover.hidden = !jaVotou;
        controles.botaoRemover.disabled = false;
    }
});


// ==========================================
// MOSTRAR RESULTADO DA RODADA
// ==========================================

socket.on("resultado_rodada", dados => {
    limparIntervalos();

    faseAtual = "resultado";

    areaRespostas.hidden = true;
    areaVotacao.hidden = true;
    areaResultado.hidden = false;

    resultadoRespostas.innerHTML = "";

    dados.respostas.forEach(item => {
        const card = document.createElement("div");
        card.className = "campo-resposta";

        const titulo = document.createElement("strong");
        titulo.textContent = item.tema;

        const texto = document.createElement("p");
        texto.textContent =
            `${item.jogador}: ${item.resposta}`;

        const situacao = document.createElement("p");

        if (item.invalidada) {
            situacao.textContent = "Resposta invalidada pela votação.";
            situacao.style.color = "#f87171";
        } else if (!item.valida_letra) {
            situacao.textContent = "Resposta não começa com a letra sorteada.";
            situacao.style.color = "#f87171";
        } else {
            situacao.textContent = "Resposta válida.";
            situacao.style.color = "#a78bfa";
        }

        card.appendChild(titulo);
        card.appendChild(texto);
        card.appendChild(situacao);

        resultadoRespostas.appendChild(card);
    });

    mostrarMensagem("Pontuação da rodada calculada!");

    atualizarRanking(dados.ranking);
});


// ==========================================
// ATUALIZAR RANKING
// ==========================================

function atualizarRanking(jogadores) {
    ranking.innerHTML = "";

    jogadores.forEach((jogador, indice) => {
        const item = document.createElement("div");
        item.className = "player-item";

        item.textContent =
            `${indice + 1}º - ${jogador.nome}: ${jogador.pontos} pontos`;

        ranking.appendChild(item);
    });
}


// ==========================================
// EVENTOS DO SERVIDOR
// ==========================================

socket.on("connect", () => {
    socket.emit(
        "carregar_partida",
        enviarDados()
    );
});

socket.on("estado_partida", dados => {
    if (dados.fase === "resultado") {
        faseAtual = "resultado";
        areaRespostas.hidden = true;
        areaVotacao.hidden = true;
        areaResultado.hidden = false;
        mostrarMensagem("Aguardando a próxima rodada...");
        return;
    }

    mostrarRodada(dados);
});

socket.on("rodada_iniciada", dados => {
    mostrarRodada(dados);
});

socket.on("rodada_encerrada", () => {
    encerrarLocalmente("Rodada encerrada! Preparando votação...");
});

socket.on("fase_votacao", dados => {
    mostrarVotacao(dados);
});

socket.on("tempo_votacao", dados => {
    cronometroVotacao.textContent =
        "Tempo para votar: " + dados.tempo + " segundos";
});

socket.on("votacao_encerrada", () => {
    clearInterval(intervaloVotacao);
    mostrarMensagem("Votação encerrada! Calculando pontuação...");
});

socket.on("partida_finalizada", dados => {
    limparIntervalos();

    faseAtual = "finalizada";
    rodadaEncerrada = true;

    bloquearCampos();

    areaRespostas.hidden = true;
    areaVotacao.hidden = true;
    areaResultado.hidden = true;

    letraAtual.textContent = "🏆";

    mostrarMensagem("PARTIDA FINALIZADA!");

    atualizarRanking(dados.ranking);
});

socket.on("erro", dados => {
    mostrarMensagem(dados.mensagem, true);
});

socket.on("connect_error", () => {
    mostrarMensagem("Erro de conexão com o servidor.", true);
});
