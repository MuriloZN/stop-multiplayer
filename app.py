
import os
import secrets
import string

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit


# CONFIGURAÇÃO

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "chave-temporaria-desenvolvimento"
)

socketio = SocketIO(app)

salas = {}


# PÁGINAS

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/sala/<codigo>")
def pagina_sala(codigo):
    if codigo not in salas:
        return "Sala não encontrada ou encerrada.", 404

    return render_template("sala.html", codigo=codigo)


# FUNÇÕES AUXILIARES

def gerar_codigo():
    caracteres = string.ascii_uppercase + string.digits

    while True:
        codigo = "".join(
            secrets.choice(caracteres) for _ in range(6)
        )

        if codigo not in salas:
            return codigo


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
    if codigo in salas:
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


def obter_jogador(dados):
    if not isinstance(dados, dict):
        return None, None, None

    codigo = dados.get("codigo", "").strip().upper()
    token = dados.get("token", "")

    sala = salas.get(codigo)

    if not sala or token not in sala["jogadores"]:
        return None, None, None

    return codigo, sala, token


def validar_nome(nome):
    return (
        isinstance(nome, str)
        and 0 < len(nome.strip()) <= 20
    )


# CRIAR SALA

@socketio.on("criar_sala")
def criar_sala(dados):
    if not isinstance(dados, dict):
        emit("erro", {"mensagem": "Dados inválidos."})
        return

    nome = dados.get("nome", "").strip()

    if not validar_nome(nome):
        emit("erro", {"mensagem": "O nome deve ter entre 1 e 20 caracteres."})
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
        "respostas": {},
        "votos": {},
        "fim_rodada": None
    }

    join_room(codigo)

    emit("sala_criada", {
        "codigo": codigo,
        "token": jogador_id,
        "jogadores": listar_jogadores(codigo),
        "anfitriao": True
    })


# ENTRAR EM UMA SALA

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
        emit("erro", {"mensagem": "O nome deve ter entre 1 e 20 caracteres."})
        return

    jogador_id = secrets.token_urlsafe(24)

    sala["jogadores"][jogador_id] = {
        "nome": nome,
        "pontos": 0,
        "sid": request.sid
    }

    join_room(codigo)

    emit("entrou_sala", {
        "codigo": codigo,
        "token": jogador_id,
        "anfitriao": False
    })

    atualizar_jogadores(codigo)
    enviar_estado_sala(codigo)


# RECONECTAR JOGADOR

@socketio.on("reconectar_sala")
def reconectar_sala(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Não foi possível recuperar sua vaga."})
        return

    sala["jogadores"][jogador_id]["sid"] = request.sid

    join_room(codigo)

    emit("sala_reconectada", {
        "codigo": codigo,
        "anfitriao": jogador_id == sala["anfitriao"],
        "jogadores": listar_jogadores(codigo)
    })

    enviar_estado_sala(codigo)
    atualizar_jogadores(codigo)


# ADICIONAR TEMA

@socketio.on("adicionar_tema")
def adicionar_tema(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Sua conexão com a sala não foi reconhecida."})
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
        emit("erro", {"mensagem": "O tema deve ter entre 1 e 30 caracteres."})
        return

    if len(sala["temas"]) >= 10:
        emit("erro", {"mensagem": "O limite de 10 temas foi atingido."})
        return

    if any(t.lower() == tema.lower() for t in sala["temas"]):
        emit("erro", {"mensagem": "Esse tema já foi adicionado."})
        return

    sala["temas"].append(tema)

    enviar_estado_sala(codigo)


# REMOVER TEMA

@socketio.on("remover_tema")
def remover_tema(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Sua conexão com a sala não foi reconhecida."})
        return

    if jogador_id != sala["anfitriao"]:
        emit("erro", {"mensagem": "Somente o anfitrião pode remover temas."})
        return

    indice = dados.get("indice")

    if not isinstance(indice, int) or isinstance(indice, bool):
        return

    if 0 <= indice < len(sala["temas"]):
        sala["temas"].pop(indice)
        enviar_estado_sala(codigo)


# ALTERAR CONFIGURAÇÕES

@socketio.on("alterar_configuracoes")
def alterar_configuracoes(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Sua conexão com a sala não foi reconhecida."})
        return

    if jogador_id != sala["anfitriao"]:
        emit("erro", {"mensagem": "Somente o anfitrião pode alterar as configurações."})
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


# INICIAR PARTIDA

@socketio.on("iniciar_partida")
def iniciar_partida(dados):
    codigo, sala, jogador_id = obter_jogador(dados)

    if not sala:
        emit("erro", {"mensagem": "Sua conexão com a sala não foi reconhecida."})
        return

    if jogador_id != sala["anfitriao"]:
        emit("erro", {"mensagem": "Somente o anfitrião pode iniciar a partida."})
        return

    if sala["estado"] != "aguardando":
        emit("erro", {"mensagem": "A partida já foi iniciada."})
        return

    if not sala["temas"]:
        emit("erro", {"mensagem": "Adicione pelo menos um tema antes de iniciar."})
        return

    sala["estado"] = "configurada"

    socketio.emit(
        "partida_pronta",
        {
            "temas": sala["temas"],
            "configuracoes": sala["configuracoes"]
        },
        to=codigo
    )


# DESCONECTAR JOGADOR

@socketio.on("disconnect")
def desconectar():
    jogador_sid = request.sid

    for codigo, sala in list(salas.items()):
        for jogador in sala["jogadores"].values():
            if jogador["sid"] == jogador_sid:
                jogador["sid"] = None
                atualizar_jogadores(codigo)
                return


# EXECUTAR SERVIDOR

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )

