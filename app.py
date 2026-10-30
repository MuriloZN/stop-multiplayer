import os
import secrets
import string

from flask import Flask, render_template
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "chave-temporaria-desenvolvimento"
)

socketio = SocketIO(app)

# Salas temporárias
salas = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/sala/<codigo>")
def pagina_sala(codigo):
    if codigo not in salas:
        return "Sala não encontrada ou encerrada.", 404

    return render_template("sala.html", codigo=codigo)


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


# CRIAR SALA
@socketio.on("criar_sala")
def criar_sala(dados):
    nome = dados.get("nome", "").strip()

    if not nome:
        emit("erro", {"mensagem": "Informe seu nome."})
        return

    if len(nome) > 20:
        emit("erro", {"mensagem": "O nome deve ter até 20 caracteres."})
        return

    codigo = gerar_codigo()
    jogador_id = secrets.token_urlsafe(24)

    salas[codigo] = {
        "anfitriao": jogador_id,

        "jogadores": {
            jogador_id: {
                "nome": nome,
                "pontos": 0,
                "sid": None
            }
        },

        "estado": "aguardando",
        "configuracoes": {},
        "temas": [],
        "letras_disponiveis": list(string.ascii_uppercase),
        "rodada_atual": 0,
        "respostas": {},
        "votos": {},
        "fim_rodada": None
    }

    salas[codigo]["jogadores"][jogador_id]["sid"] = request_sid = __import__(
        "flask"
    ).request.sid

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

    if len(nome) > 20:
        emit("erro", {"mensagem": "O nome deve ter até 20 caracteres."})
        return

    jogador_id = secrets.token_urlsafe(24)

    sala["jogadores"][jogador_id] = {
        "nome": nome,
        "pontos": 0,
        "sid": __import__("flask").request.sid
    }

    join_room(codigo)

    emit("entrou_sala", {
        "codigo": codigo,
        "token": jogador_id,
        "anfitriao": False
    })

    atualizar_jogadores(codigo)


# RECONHECER JOGADOR APÓS MUDAR DE PÁGINA
@socketio.on("reconectar_sala")
def reconectar_sala(dados):
    codigo = dados.get("codigo", "").strip().upper()
    jogador_id = dados.get("token", "")

    sala = salas.get(codigo)

    if not sala or jogador_id not in sala["jogadores"]:
        emit("erro", {"mensagem": "Não foi possível recuperar sua vaga."})
        return

    jogador = sala["jogadores"][jogador_id]
    jogador["sid"] = __import__("flask").request.sid

    join_room(codigo)

    emit("sala_reconectada", {
        "codigo": codigo,
        "anfitriao": jogador_id == sala["anfitriao"],
        "jogadores": listar_jogadores(codigo)
    })

    atualizar_jogadores(codigo)


# DESCONECTAR SEM APAGAR A VAGA
@socketio.on("disconnect")
def desconectar():
    jogador_sid = __import__("flask").request.sid

    for codigo, sala in list(salas.items()):
        for jogador in sala["jogadores"].values():

            if jogador["sid"] == jogador_sid:
                jogador["sid"] = None
                atualizar_jogadores(codigo)
                return


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
