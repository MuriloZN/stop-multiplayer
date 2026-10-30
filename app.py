
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

    codigo = dados.get("codigo", "").strip().upper()
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

@socketio.on("atualizar_respostas")
def atualizar_respostas(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Jogador ou sala não reconhecidos."})
        return

    if sala["estado"] != "em_andamento" or sala["rodada_encerrada"]:
        return

    if time.time() >= sala["fim_rodada"]:
        finalizar_rodada(codigo, "tempo")
        return

    respostas = dados.get("respostas")

    if not isinstance(respostas, dict):
        return

    respostas_validas = {}

    for indice, tema in enumerate(sala["temas"]):
        valor = respostas.get(f"resposta-{indice}", "")

        if isinstance(valor, str):
            respostas_validas[tema] = valor.strip()[:100]
        else:
            respostas_validas[tema] = ""

    sala["respostas"][jogador_id] = respostas_validas


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


# ==========================================
# CRIAR SALA
# ==========================================

@socketio.on("criar_sala")
def criar_sala(dados):
    if not isinstance(dados, dict):
        emit("erro", {"mensagem": "Dados inválidos."})
        return

    nome = dados.get("nome", "").strip()

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
        "rodada_encerrada": False
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

    codigo = dados.get("codigo", "").strip().upper()
    nome = dados.get("nome", "").strip()

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
# INICIAR RODADA
# ==========================================


def iniciar_rodada(codigo):
    sala = salas[codigo]

    if not sala["letras_disponiveis"]:
        sala["letras_disponiveis"] = list(string.ascii_uppercase)

    letra = random.choice(sala["letras_disponiveis"])
    sala["letras_disponiveis"].remove(letra)

    sala["rodada_atual"] += 1
    sala["letra_atual"] = letra

    sala["respostas"] = {}
    sala["votos"] = {}
    sala["rodada_encerrada"] = False

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


def finalizar_rodada(codigo, motivo):
    sala = salas.get(codigo)

    if not sala:
        return

    if sala["estado"] != "em_andamento":
        return

    if sala["rodada_encerrada"]:
        return

    sala["rodada_encerrada"] = True
    sala["fim_rodada"] = None

    letra = normalizar_resposta(sala["letra_atual"])

    respostas_por_tema = {
        tema: [] for tema in sala["temas"]
    }

    # ORGANIZAR AS RESPOSTAS POR TEMA

    for jogador_id, respostas in sala["respostas"].items():
        for tema in sala["temas"]:
            resposta = respostas.get(tema, "")

            if resposta:
                respostas_por_tema[tema].append({
                    "jogador_id": jogador_id,
                    "resposta": resposta
                })

    # CALCULAR A PONTUAÇÃO

    pontuacao_rodada = {
        jogador_id: 0
        for jogador_id in sala["jogadores"]
    }

    for tema, respostas in respostas_por_tema.items():
        respostas_validas = []

        for item in respostas:
            resposta = item["resposta"]
            resposta_normalizada = normalizar_resposta(resposta)

            if resposta_normalizada.startswith(letra):
                respostas_validas.append({
                    "jogador_id": item["jogador_id"],
                    "resposta": resposta,
                    "normalizada": resposta_normalizada
                })

        contagem = {}

        for item in respostas_validas:
            chave = item["normalizada"]
            contagem[chave] = contagem.get(chave, 0) + 1

        for item in respostas_validas:
            jogador_id = item["jogador_id"]
            chave = item["normalizada"]

            if contagem[chave] == 1:
                pontuacao_rodada[jogador_id] += 10
            else:
                pontuacao_rodada[jogador_id] += 5

    # SOMAR AOS PONTOS DA PARTIDA

    for jogador_id, pontos in pontuacao_rodada.items():
        sala["jogadores"][jogador_id]["pontos"] += pontos

    ranking = sorted(
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

    socketio.emit(
        "resultado_rodada",
        {
            "motivo": motivo,
            "rodada": sala["rodada_atual"],
            "pontuacao": pontuacao_rodada,
            "ranking": ranking
        },
        to=codigo
    )

    socketio.emit(
        "rodada_encerrada",
        {
            "motivo": motivo,
            "rodada": sala["rodada_atual"]
        },
        to=codigo
    )

    socketio.start_background_task(
        avancar_partida,
        codigo,
        sala["rodada_atual"]
    )

def avancar_partida(codigo, numero_rodada):
    socketio.sleep(5)

    sala = salas.get(codigo)

    if not sala:
        return

    if sala["estado"] != "em_andamento":
        return

    if sala["rodada_atual"] != numero_rodada:
        return

    if numero_rodada >= sala["configuracoes"]["rodadas"]:
        sala["estado"] = "finalizada"

        ranking = sorted(
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

        socketio.emit(
            "partida_finalizada",
            {"ranking": ranking},
            to=codigo
        )

        return

    iniciar_rodada(codigo)

def controlar_tempo_rodada(codigo, numero_rodada):
    while True:
        sala = salas.get(codigo)

        if not sala:
            return

        if sala["estado"] != "em_andamento":
            return

        if sala["rodada_atual"] != numero_rodada:
            return

        if sala["rodada_encerrada"]:
            return

        restante = sala["fim_rodada"] - time.time()

        if restante <= 0:
            finalizar_rodada(codigo, "tempo")
            return

        socketio.sleep(min(1, restante))

@socketio.on("parar_rodada")
def parar_rodada(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Jogador ou sala não reconhecidos."})
        return

    if sala["estado"] != "em_andamento":
        emit("erro", {"mensagem": "Não existe uma rodada em andamento."})
        return

    if sala["rodada_encerrada"]:
        emit("erro", {"mensagem": "Esta rodada já foi encerrada."})
        return

    if time.time() >= sala["fim_rodada"]:
        finalizar_rodada(codigo, "tempo")
        return

    respostas = dados.get("respostas")

    if not isinstance(respostas, dict):
        emit("erro", {"mensagem": "Respostas inválidas."})
        return

    if jogador_id in sala["respostas"]:
        emit("erro", {"mensagem": "Você já enviou suas respostas."})
        return

    respostas_por_tema = {}

for indice, tema in enumerate(sala["temas"]):
    resposta = respostas.get(f"resposta-{indice}", "")

    if isinstance(resposta, str):
        respostas_por_tema[tema] = resposta.strip()[:100]
    else:
        respostas_por_tema[tema] = ""

sala["respostas"][jogador_id] = respostas_por_tema

    finalizar_rodada(codigo, "stop")

# ==========================================
# RECUPERAR ESTADO DA PARTIDA
# ==========================================

@socketio.on("carregar_partida")
def carregar_partida(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Não foi possível recuperar sua partida."})
        return

    if sala["estado"] != "em_andamento":
        emit("erro", {"mensagem": "A partida ainda não começou."})
        return

    tempo_restante = 0

    if not sala["rodada_encerrada"] and sala["fim_rodada"]:
        tempo_restante = max(
            0,
            int(sala["fim_rodada"] - time.time())
    )

    emit(
        "estado_partida",
        {
            "letra": sala["letra_atual"],
            "rodada": sala["rodada_atual"],
            "total_rodadas": sala["configuracoes"]["rodadas"],
            "tempo": tempo_restante,
            "temas": sala["temas"]
        }
    )

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
