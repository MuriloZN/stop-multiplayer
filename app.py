
import os
import secrets
import string
from datetime import datetime, timedelta

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "chave-temporaria-desenvolvimento"
)

socketio = SocketIO(app, cors_allowed_origins=[])

# Salas armazenadas temporariamente na memória do servidor
salas = {}

@app.route("/")
def index():
    return render_template("index.html")


def gerar_codigo():
    caracteres = string.ascii_uppercase + string.digits
    while True:
        codigo = "".join(secrets.choice(caracteres) for _ in range(6))
        if codigo not in salas:
            return codigo


@socketio.on("criar_sala")
def criar_sala(dados):
    nome = dados.get("nome", "").strip()

    if not nome:
        emit("erro", {"mensagem": "Informe seu nome."})
        return

    codigo = gerar_codigo()
    jogador_id = request.sid

    salas[codigo] = {
        "anfitriao": jogador_id,
        "jogadores": {
            jogador_id: {
                "nome": nome,
                "pontos": 0
            }
        },
        "estado": "aguardando",
        "configuracoes": {},
        "temas": [],
        "letras_disponiveis": list("ABCDEFGHIJKLMNOPRSTUVW"),
        "rodada_atual": 0,
        "respostas": {},
        "votos": {},
        "fim_rodada": None
    }

    join_room(codigo)

    emit("sala_criada", {
        "codigo": codigo,
        "jogadores": listar_jogadores(codigo),
        "anfitriao": True
    })


def listar_jogadores(codigo):
    sala = salas[codigo]
    return [
        {
            "nome": jogador["nome"],
            "pontos": jogador["pontos"]
        }
        for jogador in sala["jogadores"].values()
    ]


@socketio.on("entrar_sala")
def entrar_sala(dados):
    codigo = dados.get("codigo", "").strip().upper()
    nome = dados.get("nome", "").strip()

    sala = salas.get(codigo)

    if not sala:
        emit("erro", {"mensagem": "Sala não encontrada."})
        return

    if sala["estado"] != "aguardando":
        emit("erro", {"mensagem": "A partida já começou."})
        return

    if not nome:
        emit("erro", {"mensagem": "Informe seu nome."})
        return

    jogador_id = request.sid

    sala["jogadores"][jogador_id] = {
        "nome": nome,
        "pontos": 0
    }

    join_room(codigo)

    emit("entrou_sala", {
        "codigo": codigo,
        "anfitriao": False,
        "jogadores": listar_jogadores(codigo)
    })

    socketio.emit(
        "atualizar_jogadores",
        {"jogadores": listar_jogadores(codigo)},
        to=codigo
    )


@socketio.on("disconnect")
def desconectar():
    jogador_id = request.sid

    for codigo, sala in list(salas.items()):
        if jogador_id in sala["jogadores"]:
            del sala["jogadores"][jogador_id]
            leave_room(codigo)

            if not sala["jogadores"]:
                del salas[codigo]
            else:
                socketio.emit(
                    "atualizar_jogadores",
                    {"jogadores": listar_jogadores(codigo)},
                    to=codigo
                )
            break


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
