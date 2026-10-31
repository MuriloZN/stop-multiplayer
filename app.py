
import os
import secrets
import string
import random
import time
import unicodedata

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit


# ==========================================
# CONFIGURAÇÃO DO SERVIDOR
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "chave-temporaria-desenvolvimento"
)

socketio = SocketIO(app)

salas = {}

TEMPO_VOTACAO = 15
TEMPO_RESULTADO = 5


# ==========================================
# PÁGINAS
# ==========================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/sala/<codigo>")
def pagina_sala(codigo):
    if codigo not in salas:
        return "Sala não encontrada ou encerrada.", 404

    return render_template("sala.html", codigo=codigo)


@app.route("/partida/<codigo>")
def pagina_partida(codigo):
    if codigo not in salas:
        return "Partida não encontrada.", 404

    return render_template("partida.html", codigo=codigo)


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def gerar_codigo():
    caracteres = string.ascii_uppercase + string.digits

    while True:
        codigo = "".join(
            secrets.choice(caracteres) for _ in range(6)
        )

        if codigo not in salas:
            return codigo


def validar_nome(nome):
    return (
        isinstance(nome, str)
        and 0 < len(nome.strip()) <= 20
    )


def obter_jogador(dados):
    if not isinstance(dados, dict):
        return None, None, None

    codigo = dados.get("codigo", "")

    if not isinstance(codigo, str):
        return None, None, None

    codigo = codigo.strip().upper()
    token = dados.get("token", "")

    sala = salas.get(codigo)

    if not sala or token not in sala["jogadores"]:
        return None, None, None

    return codigo, sala, token


def normalizar_resposta(texto):
    texto = texto.strip().casefold()

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return texto


def criar_ranking(sala):
    return sorted(
        [
            {
                "nome": jogador["nome"],
                "pontos": jogador["pontos"]
            }
            for jogador in sala["jogadores"].values()
        ],
        key=lambda jogador: jogador["pontos"],
        reverse=True
    )


def listar_jogadores(codigo):
    sala = salas[codigo]

    return [
        {
            "nome": jogador["nome"],
            "pontos": jogador["pontos"],
            "conectado": jogador["sid"] is not None
        }
        for jogador in sala["jogadores"].values()
    ]


def atualizar_jogadores(codigo):
    if codigo not in salas:
        return

    socketio.emit(
        "atualizar_jogadores",
        {"jogadores": listar_jogadores(codigo)},
        to=codigo
    )


def enviar_estado_sala(codigo):
    sala = salas[codigo]

    socketio.emit(
        "estado_sala",
        {
            "temas": sala["temas"],
            "configuracoes": sala["configuracoes"],
            "anfitriao": sala["anfitriao"]
        },
        to=codigo
    )


def obter_respostas_do_jogador(sala, dados):
    respostas = dados.get("respostas")

    if not isinstance(respostas, dict):
        return None

    respostas_por_tema = {}

    for indice, tema in enumerate(sala["temas"]):
        resposta = respostas.get(f"resposta-{indice}", "")

        if isinstance(resposta, str):
            respostas_por_tema[tema] = resposta.strip()[:100]
        else:
            respostas_por_tema[tema] = ""

    return respostas_por_tema


# ==========================================
# CRIAR SALA
# ==========================================

@socketio.on("criar_sala")
def criar_sala(dados):
    if not isinstance(dados, dict):
        emit("erro", {"mensagem": "Dados inválidos."})
        return

    nome = dados.get("nome", "")

    if not isinstance(nome, str):
        emit("erro", {"mensagem": "Nome inválido."})
        return

    nome = nome.strip()

    if not validar_nome(nome):
        emit(
            "erro",
            {"mensagem": "O nome deve ter entre 1 e 20 caracteres."}
        )
        return

    codigo = gerar_codigo()
    jogador_id = secrets.token_urlsafe(24)

    salas[codigo] = {
        "anfitriao": jogador_id,

        "jogadores": {
            jogador_id: {
                "nome": nome,
                "pontos": 0,
                "sid": request.sid
            }
        },

        "estado": "aguardando",

        "configuracoes": {
            "tempo": 60,
            "rodadas": 10
        },

        "temas": [],

        "letras_disponiveis": list(string.ascii_uppercase),

        "rodada_atual": 0,
        "letra_atual": None,

        "respostas": {},
        "votos": {},

        "fim_rodada": None,
        "fim_votacao": None,

        "rodada_encerrada": False,
        "fase": "aguardando",

        "respostas_revisao": {},
        "total_jogadores_votacao": 0
    }

    join_room(codigo)

    emit(
        "sala_criada",
        {
            "codigo": codigo,
            "token": jogador_id,
            "jogadores": listar_jogadores(codigo),
            "anfitriao": True
        }
    )


# ==========================================
# ENTRAR EM UMA SALA
# ==========================================

@socketio.on("entrar_sala")
def entrar_sala(dados):
    if not isinstance(dados, dict):
        emit("erro", {"mensagem": "Dados inválidos."})
        return

    codigo = dados.get("codigo", "")
    nome = dados.get("nome", "")

    if not isinstance(codigo, str) or not isinstance(nome, str):
        emit("erro", {"mensagem": "Dados inválidos."})
        return

    codigo = codigo.strip().upper()
    nome = nome.strip()

    sala = salas.get(codigo)

    if not sala:
        emit("erro", {"mensagem": "Sala não encontrada."})
        return

    if sala["estado"] != "aguardando":
        emit("erro", {"mensagem": "A partida já começou."})
        return

    if not validar_nome(nome):
        emit(
            "erro",
            {"mensagem": "O nome deve ter entre 1 e 20 caracteres."}
        )
        return

    jogador_id = secrets.token_urlsafe(24)

    sala["jogadores"][jogador_id] = {
        "nome": nome,
        "pontos": 0,
        "sid": request.sid
    }

    join_room(codigo)

    emit(
        "entrou_sala",
        {
            "codigo": codigo,
            "token": jogador_id,
            "anfitriao": False
        }
    )

    atualizar_jogadores(codigo)
    enviar_estado_sala(codigo)


# ==========================================
# RECONECTAR JOGADOR
# ==========================================

@socketio.on("reconectar_sala")
def reconectar_sala(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit(
            "erro",
            {"mensagem": "Não foi possível recuperar sua vaga."}
        )
        return

    sala["jogadores"][jogador_id]["sid"] = request.sid

    join_room(codigo)

    emit(
        "sala_reconectada",
        {
            "codigo": codigo,
            "anfitriao": jogador_id == sala["anfitriao"],
            "jogadores": listar_jogadores(codigo)
        }
    )

    enviar_estado_sala(codigo)
    atualizar_jogadores(codigo)

    if sala["estado"] == "em_andamento":
        carregar_estado_partida(codigo, sala, jogador_id)


# ==========================================
# ADICIONAR TEMA
# ==========================================

@socketio.on("adicionar_tema")
def adicionar_tema(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Conexão com a sala não reconhecida."})
        return

    if sala["estado"] != "aguardando":
        emit("erro", {"mensagem": "A partida já foi iniciada."})
        return

    tema = dados.get("tema", "")

    if not isinstance(tema, str):
        emit("erro", {"mensagem": "Tema inválido."})
        return

    tema = tema.strip()

    if not tema or len(tema) > 30:
        emit(
            "erro",
            {"mensagem": "O tema deve ter entre 1 e 30 caracteres."}
        )
        return

    if len(sala["temas"]) >= 10:
        emit("erro", {"mensagem": "O limite de 10 temas foi atingido."})
        return

    if any(t.lower() == tema.lower() for t in sala["temas"]):
        emit("erro", {"mensagem": "Esse tema já foi adicionado."})
        return

    sala["temas"].append(tema)

    enviar_estado_sala(codigo)


# ==========================================
# REMOVER TEMA
# ==========================================

@socketio.on("remover_tema")
def remover_tema(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Conexão com a sala não reconhecida."})
        return

    if jogador_id != sala["anfitriao"]:
        emit(
            "erro",
            {"mensagem": "Somente o anfitrião pode remover temas."}
        )
        return

    indice = dados.get("indice")

    if not isinstance(indice, int) or isinstance(indice, bool):
        return

    if 0 <= indice < len(sala["temas"]):
        sala["temas"].pop(indice)
        enviar_estado_sala(codigo)


# ==========================================
# ALTERAR CONFIGURAÇÕES
# ==========================================

@socketio.on("alterar_configuracoes")
def alterar_configuracoes(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Conexão com a sala não reconhecida."})
        return

    if jogador_id != sala["anfitriao"]:
        emit(
            "erro",
            {"mensagem": "Somente o anfitrião pode alterar configurações."}
        )
        return

    if sala["estado"] != "aguardando":
        emit("erro", {"mensagem": "A partida já foi iniciada."})
        return

    configuracoes = dados.get("configuracoes", {})

    if not isinstance(configuracoes, dict):
        return

    tempo = configuracoes.get("tempo")
    rodadas = configuracoes.get("rodadas")

    if tempo not in [60, 90, 120] or rodadas not in [5, 10, 15]:
        emit("erro", {"mensagem": "Configurações inválidas."})
        return

    sala["configuracoes"] = {
        "tempo": tempo,
        "rodadas": rodadas
    }

    enviar_estado_sala(codigo)


# ==========================================
# INICIAR PARTIDA
# ==========================================

@socketio.on("iniciar_partida")
def iniciar_partida(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit(
            "erro",
            {"mensagem": "Conexão com a sala não reconhecida."}
        )
        return

    if jogador_id != sala["anfitriao"]:
        emit(
            "erro",
            {"mensagem": "Somente o anfitrião pode iniciar a partida."}
        )
        return

    if sala["estado"] != "aguardando":
        emit("erro", {"mensagem": "A partida já foi iniciada."})
        return

    if not sala["temas"]:
        emit(
            "erro",
            {"mensagem": "Adicione pelo menos um tema antes de iniciar."}
        )
        return

    sala["estado"] = "em_andamento"

    for jogador in sala["jogadores"].values():
        jogador["pontos"] = 0

    iniciar_rodada(codigo)


# ==========================================
# INICIAR RODADA
# ==========================================

def iniciar_rodada(codigo):
    sala = salas.get(codigo)

    if not sala:
        return

    if not sala["letras_disponiveis"]:
        sala["letras_disponiveis"] = list(string.ascii_uppercase)

    letra = random.choice(sala["letras_disponiveis"])
    sala["letras_disponiveis"].remove(letra)

    sala["rodada_atual"] += 1
    sala["letra_atual"] = letra

    sala["respostas"] = {}
    sala["votos"] = {}
    sala["respostas_revisao"] = {}

    sala["rodada_encerrada"] = False
    sala["fase"] = "respondendo"
    sala["fim_votacao"] = None

    sala["fim_rodada"] = (
        time.time() + sala["configuracoes"]["tempo"]
    )

    numero_rodada = sala["rodada_atual"]

    socketio.emit(
        "rodada_iniciada",
        {
            "letra": letra,
            "rodada": numero_rodada,
            "total_rodadas": sala["configuracoes"]["rodadas"],
            "tempo": sala["configuracoes"]["tempo"],
            "temas": sala["temas"]
        },
        to=codigo
    )

    socketio.start_background_task(
        controlar_tempo_rodada,
        codigo,
        numero_rodada
    )


# ==========================================
# ATUALIZAR RESPOSTAS ENQUANTO DIGITA
# ==========================================

@socketio.on("atualizar_respostas")
def atualizar_respostas(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Jogador ou sala não reconhecidos."})
        return

    if sala["estado"] != "em_andamento":
        return

    if sala["fase"] != "respondendo":
        return

    if time.time() >= sala["fim_rodada"]:
        finalizar_rodada(codigo, "tempo")
        return

    respostas = obter_respostas_do_jogador(sala, dados)

    if respostas is None:
        return

    sala["respostas"][jogador_id] = respostas


# ==========================================
# ENCERRAR RODADA
# ==========================================

@socketio.on("parar_rodada")
def parar_rodada(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Jogador ou sala não reconhecidos."})
        return

    if sala["estado"] != "em_andamento":
        emit("erro", {"mensagem": "Não existe uma rodada em andamento."})
        return

    if sala["fase"] != "respondendo":
        emit("erro", {"mensagem": "Esta rodada já foi encerrada."})
        return

    if time.time() >= sala["fim_rodada"]:
        finalizar_rodada(codigo, "tempo")
        return

    respostas = obter_respostas_do_jogador(sala, dados)

    if respostas is None:
        emit("erro", {"mensagem": "Respostas inválidas."})
        return

    sala["respostas"][jogador_id] = respostas

    finalizar_rodada(codigo, "stop")


# ==========================================
# FASE DE VOTAÇÃO
# ==========================================

def finalizar_rodada(codigo, motivo):
    sala = salas.get(codigo)

    if not sala or sala["estado"] != "em_andamento":
        return

    if sala["fase"] != "respondendo":
        return

    sala["rodada_encerrada"] = True
    sala["fase"] = "votacao"
    sala["fim_rodada"] = None

    letra = normalizar_resposta(sala["letra_atual"])

    respostas_revisao = {}
    sala["votos"] = {}

    for tema in sala["temas"]:
        respostas_revisao[tema] = []

    for jogador_id, respostas in sala["respostas"].items():
        for tema in sala["temas"]:
            resposta = respostas.get(tema, "").strip()

            if not resposta:
                continue

            resposta_id = secrets.token_urlsafe(12)
            normalizada = normalizar_resposta(resposta)

            respostas_revisao[tema].append({
                "id": resposta_id,
                "jogador_id": jogador_id,
                "jogador": sala["jogadores"][jogador_id]["nome"],
                "resposta": resposta,
                "valida_letra": normalizada.startswith(letra)
            })

            sala["votos"][resposta_id] = set()

    sala["respostas_revisao"] = respostas_revisao
    sala["total_jogadores_votacao"] = len(sala["jogadores"])
    sala["fim_votacao"] = time.time() + TEMPO_VOTACAO

    respostas_publicas = []

    for tema, respostas in respostas_revisao.items():
        for item in respostas:
            respostas_publicas.append({
                "id": item["id"],
                "tema": tema,
                "jogador": item["jogador"],
                "resposta": item["resposta"],
                "valida_letra": item["valida_letra"],
                "votos": 0
            })

    socketio.emit(
        "rodada_encerrada",
        {
            "motivo": motivo,
            "rodada": sala["rodada_atual"]
        },
        to=codigo
    )

    socketio.emit(
        "fase_votacao",
        {
            "rodada": sala["rodada_atual"],
            "letra": sala["letra_atual"],
            "tempo": TEMPO_VOTACAO,
            "respostas": respostas_publicas,
            "votos_necessarios": (
                sala["total_jogadores_votacao"] // 2 + 1
            )
        },
        to=codigo
    )

    socketio.start_background_task(
        controlar_tempo_votacao,
        codigo,
        sala["rodada_atual"]
    )


def controlar_tempo_votacao(codigo, numero_rodada):
    while True:
        socketio.sleep(0.5)

        sala = salas.get(codigo)

        if not sala:
            return

        if sala["estado"] != "em_andamento":
            return

        if sala["rodada_atual"] != numero_rodada:
            return

        if sala["fase"] != "votacao":
            return

        restante = sala["fim_votacao"] - time.time()

        if restante <= 0:
            calcular_pontuacao_rodada(codigo, numero_rodada)
            return

        socketio.emit(
            "tempo_votacao",
            {"tempo": max(0, int(restante))},
            to=codigo
        )


# ==========================================
# VOTAR PARA INVALIDAR UMA RESPOSTA
# ==========================================

@socketio.on("votar_resposta")
def votar_resposta(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Jogador ou sala não reconhecidos."})
        return

    if sala["fase"] != "votacao":
        emit("erro", {"mensagem": "Não existe uma votação em andamento."})
        return

    if time.time() >= sala["fim_votacao"]:
        calcular_pontuacao_rodada(codigo, sala["rodada_atual"])
        return

    resposta_id = dados.get("resposta_id")

    if resposta_id not in sala["votos"]:
        emit("erro", {"mensagem": "Resposta não encontrada."})
        return

    votos = sala["votos"][resposta_id]

    if jogador_id in votos:
        emit("erro", {"mensagem": "Você já votou nesta resposta."})
        return

    votos.add(jogador_id)

    total_votos = len(votos)

    socketio.emit(
        "votacao_atualizada",
        {
            "resposta_id": resposta_id,
            "votos": total_votos,
            "votos_necessarios": (
                sala["total_jogadores_votacao"] // 2 + 1
            )
        },
        to=codigo
    )


# ==========================================
# CALCULAR PONTUAÇÃO APÓS A VOTAÇÃO
# ==========================================

def calcular_pontuacao_rodada(codigo, numero_rodada):
    sala = salas.get(codigo)

    if not sala:
        return

    if sala["estado"] != "em_andamento":
        return

    if sala["rodada_atual"] != numero_rodada:
        return

    if sala["fase"] != "votacao":
        return

    sala["fase"] = "resultado"
    sala["fim_votacao"] = None

    votos_necessarios = (
        sala["total_jogadores_votacao"] // 2 + 1
    )

    pontuacao_rodada = {
        jogador_id: 0
        for jogador_id in sala["jogadores"]
    }

    resultados_respostas = []

    for tema, respostas in sala["respostas_revisao"].items():
        respostas_validas = []

        for item in respostas:
            votos = len(sala["votos"].get(item["id"], set()))

            invalidada = votos >= votos_necessarios

            if item["valida_letra"] and not invalidada:
                respostas_validas.append(item)

            resultados_respostas.append({
                "id": item["id"],
                "tema": tema,
                "jogador": item["jogador"],
                "resposta": item["resposta"],
                "votos": votos,
                "invalidada": invalidada,
                "valida_letra": item["valida_letra"]
            })

        contagem = {}

        for item in respostas_validas:
            chave = normalizar_resposta(item["resposta"])
            contagem[chave] = contagem.get(chave, 0) + 1

        for item in respostas_validas:
            chave = normalizar_resposta(item["resposta"])

            if contagem[chave] == 1:
                pontuacao_rodada[item["jogador_id"]] += 10
            else:
                pontuacao_rodada[item["jogador_id"]] += 5

    for jogador_id, pontos in pontuacao_rodada.items():
        sala["jogadores"][jogador_id]["pontos"] += pontos

    ranking = criar_ranking(sala)

    socketio.emit(
        "resultado_rodada",
        {
            "rodada": sala["rodada_atual"],
            "pontuacao": pontuacao_rodada,
            "ranking": ranking,
            "respostas": resultados_respostas
        },
        to=codigo
    )

    socketio.emit(
        "votacao_encerrada",
        {"rodada": sala["rodada_atual"]},
        to=codigo
    )

    socketio.start_background_task(
        avancar_partida,
        codigo,
        numero_rodada
    )


# ==========================================
# AVANÇAR PARTIDA
# ==========================================

def avancar_partida(codigo, numero_rodada):
    socketio.sleep(TEMPO_RESULTADO)

    sala = salas.get(codigo)

    if not sala:
        return

    if sala["estado"] != "em_andamento":
        return

    if sala["rodada_atual"] != numero_rodada:
        return

    if numero_rodada >= sala["configuracoes"]["rodadas"]:
        sala["estado"] = "finalizada"
        sala["fase"] = "finalizada"

        ranking = criar_ranking(sala)

        socketio.emit(
            "partida_finalizada",
            {"ranking": ranking},
            to=codigo
        )

        return

    iniciar_rodada(codigo)


# ==========================================
# CONTROLAR TEMPO DA RODADA
# ==========================================

def controlar_tempo_rodada(codigo, numero_rodada):
    while True:
        sala = salas.get(codigo)

        if not sala:
            return

        if sala["estado"] != "em_andamento":
            return

        if sala["rodada_atual"] != numero_rodada:
            return

        if sala["fase"] != "respondendo":
            return

        restante = sala["fim_rodada"] - time.time()

        if restante <= 0:
            finalizar_rodada(codigo, "tempo")
            return

        socketio.sleep(min(1, restante))


# ==========================================
# RECUPERAR ESTADO DA PARTIDA
# ==========================================

def carregar_estado_partida(codigo, sala, jogador_id):
    if sala["fase"] == "respondendo":
        tempo_restante = 0

        if sala["fim_rodada"]:
            tempo_restante = max(
                0,
                int(sala["fim_rodada"] - time.time())
            )

        emit(
            "estado_partida",
            {
                "fase": "respondendo",
                "letra": sala["letra_atual"],
                "rodada": sala["rodada_atual"],
                "total_rodadas": sala["configuracoes"]["rodadas"],
                "tempo": tempo_restante,
                "temas": sala["temas"]
            }
        )

    elif sala["fase"] == "votacao":
        respostas_publicas = []

        for tema, respostas in sala["respostas_revisao"].items():
            for item in respostas:
                respostas_publicas.append({
                    "id": item["id"],
                    "tema": tema,
                    "jogador": item["jogador"],
                    "resposta": item["resposta"],
                    "valida_letra": item["valida_letra"],
                    "votos": len(
                        sala["votos"].get(item["id"], set())
                    )
                })

        emit(
            "fase_votacao",
            {
                "rodada": sala["rodada_atual"],
                "letra": sala["letra_atual"],
                "tempo": max(
                    0,
                    int(sala["fim_votacao"] - time.time())
                ),
                "respostas": respostas_publicas,
                "votos_necessarios": (
                    sala["total_jogadores_votacao"] // 2 + 1
                )
            }
        )

    elif sala["fase"] == "resultado":
        emit(
            "estado_partida",
            {
                "fase": "resultado",
                "letra": sala["letra_atual"],
                "rodada": sala["rodada_atual"],
                "total_rodadas": sala["configuracoes"]["rodadas"],
                "temas": sala["temas"]
            }
        )


@socketio.on("carregar_partida")
def carregar_partida(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Não foi possível recuperar sua partida."})
        return

    if sala["estado"] != "em_andamento":
        emit("erro", {"mensagem": "A partida não está em andamento."})
        return

    # A tela da partida abre uma nova conexão Socket.IO após sair do lobby.
    # Reassociamos o socket à sala para que ele receba os eventos em broadcast
    # (fase_votacao, resultado_rodada, rodada_iniciada etc.).
    join_room(codigo)
    sala["jogadores"][jogador_id]["sid"] = request.sid

    carregar_estado_partida(codigo, sala, jogador_id)


# ==========================================
# DESCONECTAR JOGADOR
# ==========================================

@socketio.on("disconnect")
def desconectar():
    jogador_sid = request.sid

    for codigo, sala in list(salas.items()):
        for jogador in sala["jogadores"].values():

            if jogador["sid"] == jogador_sid:
                jogador["sid"] = None
                atualizar_jogadores(codigo)
                return


# ==========================================
# EXECUTAR SERVIDOR
# ==========================================

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
