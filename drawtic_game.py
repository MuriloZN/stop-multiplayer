import random
import secrets
import string
import time
import unicodedata

from flask import render_template, request
from flask_socketio import emit, join_room

THEMES = {
    "Animais": ["cachorro", "gato", "elefante", "girafa", "leão", "tartaruga", "borboleta", "pinguim", "cavalo", "macaco", "coelho", "jacaré", "golfinho", "tubarão", "coruja", "abelha", "canguru", "zebra", "raposa", "urso"],
    "Comidas e frutas": ["pizza", "hambúrguer", "banana", "abacaxi", "morango", "melancia", "sorvete", "bolo", "pipoca", "sushi", "cenoura", "chocolate", "uva", "limão", "panqueca", "cachorro-quente", "maçã", "queijo", "ovo", "brigadeiro"],
    "Objetos": ["guarda-chuva", "relógio", "cadeira", "óculos", "violão", "lâmpada", "mochila", "tesoura", "chave", "telefone", "escova", "martelo", "livro", "câmera", "ventilador", "controle remoto", "bicicleta", "travesseiro", "caneca", "óculos de sol"],
    "Transportes": ["avião", "ônibus", "trem", "navio", "helicóptero", "motocicleta", "patinete", "submarino", " foguete", "trator", "ambulância", "metrô", "balão", "caminhão", "skate", "barco", "táxi", "carro de corrida", "teleférico", "carruagem"],
    "Natureza": ["árvore", "vulcão", "montanha", "arco-íris", "nuvem", "cachoeira", "flor", "sol", "lua", "estrela", "cacto", "cogumelo", "palmeira", "tornado", "floco de neve", "praia", "ilha", "planeta", "raio", "folha"],
    "Profissões": ["médico", "professor", "bombeiro", "astronauta", "cozinheiro", "dentista", "pintor", "policial", "mecânico", "jardineiro", "piloto", "fotógrafo", "carteiro", "padeiro", "cientista", "músico", "pescador", "veterinário", "construtor", "cabeleireiro"],
    "Lugares": ["escola", "hospital", "castelo", "estádio", "cinema", "aeroporto", "biblioteca", "restaurante", "museu", "parque", "fazenda", "igreja", "supermercado", "circo", "aquário", "praia", "deserto", "floresta", "shopping", "delegacia"],
    "Esportes": ["futebol", "basquete", "tênis", "natação", "surfe", "boxe", "skate", "golfe", "vôlei", "ciclismo", "esqui", "ginástica", "beisebol", "boliche", "judô", "corrida", "esgrima", "remo", "arco e flecha", "patinação"]
}
rooms = {}
DRAW_TIME = 75
POINTS = [100, 75, 50]


def clean_answer(value):
    value = unicodedata.normalize("NFD", str(value).strip().casefold())
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def public_players(room):
    return [{"nome": p["nome"], "pontos": p["pontos"]} for p in room["players"].values()]


def ranking(room):
    return sorted(public_players(room), key=lambda p: p["pontos"], reverse=True)


def broadcast_players(socketio, code):
    socketio.emit("drawtic_players", {"players": public_players(rooms[code])}, to=code)


def begin_turn(socketio, code):
    room = rooms.get(code)
    if not room:
        return
    while room["turn_index"] < len(room["order"]):
        drawer_id = room["order"][room["turn_index"]]
        drawer = room["players"].get(drawer_id)
        if drawer and drawer["sid"]:
            break
        room["turn_index"] += 1
    if room["turn_index"] >= len(room["order"]):
        room["round"] += 1
        if room["round"] > room["rounds"]:
            room["state"] = "finished"
            socketio.emit("drawtic_finished", {"ranking": ranking(room)}, to=code)
            return
        room["turn_index"] = 0
    drawer_id = room["order"][room["turn_index"]]
    room["drawer"] = drawer_id
    room["word"] = random.choice(room["words"])
    room["guessed"] = []
    room["turn_end"] = time.time() + DRAW_TIME
    room["state"] = "drawing"
    socketio.emit("drawtic_turn", {
        "round": room["round"], "rounds": room["rounds"],
        "drawer": room["players"][drawer_id]["nome"],
        "drawer_id": drawer_id, "duration": DRAW_TIME,
        "word": room["word"] if room["players"][drawer_id]["sid"] else None
    }, to=code)
    socketio.start_background_task(turn_clock, socketio, code, room["round"], room["turn_index"])


def finish_turn(socketio, code, reason="finished"):
    room = rooms.get(code)
    if not room or room["state"] != "drawing":
        return
    room["state"] = "revealing"
    socketio.emit("drawtic_reveal", {
        "word": room["word"], "reason": reason,
        "drawer": room["players"][room["drawer"]]["nome"],
        "ranking": ranking(room)
    }, to=code)
    socketio.start_background_task(next_turn, socketio, code, room["round"], room["turn_index"])


def next_turn(socketio, code, round_number, turn_index):
    socketio.sleep(4)
    room = rooms.get(code)
    if not room or room["state"] != "revealing" or room["round"] != round_number or room["turn_index"] != turn_index:
        return
    room["turn_index"] += 1
    begin_turn(socketio, code)


def turn_clock(socketio, code, round_number, turn_index):
    while True:
        socketio.sleep(1)
        room = rooms.get(code)
        if not room or room["state"] != "drawing" or room["round"] != round_number or room["turn_index"] != turn_index:
            return
        remaining = max(0, int(room["turn_end"] - time.time()))
        socketio.emit("drawtic_timer", {"remaining": remaining}, to=code)
        if remaining <= 0:
            finish_turn(socketio, code, "time")
            return


def register_drawtic(app, socketio):
    @app.get("/drawtic")
    def drawtic_page():
        return render_template("drawtic.html")

    @app.get("/drawtic/sala/<code>")
    def drawtic_room_page(code):
        if code not in rooms:
            return "Sala Drawtic não encontrada.", 404
        return render_template("drawtic.html", room_code=code)

    @socketio.on("drawtic_create")
    def drawtic_create(data):
        name = str((data or {}).get("name", "")).strip()[:20]
        if not name:
            emit("drawtic_error", {"message": "Digite seu nome."})
            return
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        player_id = secrets.token_urlsafe(18)
        rooms[code] = {
            "host": player_id, "players": {player_id: {"nome": name, "pontos": 0, "sid": request.sid}},
            "state": "lobby", "rounds": 5, "theme": "Animais", "round": 0,
            "turn_index": 0, "order": [], "words": [], "drawer": None,
            "word": None, "guessed": [], "turn_end": None
        }
        join_room("drawtic_" + code)
        emit("drawtic_created", {"code": code, "token": player_id, "name": name, "host": True})

    @socketio.on("drawtic_join")
    def drawtic_join(data):
        data = data or {}
        code = str(data.get("code", "")).strip().upper()
        name = str(data.get("name", "")).strip()[:20]
        room = rooms.get(code)
        if not room or room["state"] != "lobby" or not name:
            emit("drawtic_error", {"message": "Sala indisponível ou nome inválido."})
            return
        player_id = secrets.token_urlsafe(18)
        room["players"][player_id] = {"nome": name, "pontos": 0, "sid": request.sid}
        join_room("drawtic_" + code)
        emit("drawtic_joined", {"code": code, "token": player_id, "name": name, "host": False})
        broadcast_players(socketio, "drawtic_" + code)

    @socketio.on("drawtic_reconnect")
    def drawtic_reconnect(data):
        data = data or {}
        code, token = data.get("code"), data.get("token")
        room = rooms.get(code)
        if not room or token not in room["players"]:
            emit("drawtic_error", {"message": "Não foi possível recuperar sua vaga."})
            return
        room["players"][token]["sid"] = request.sid
        join_room("drawtic_" + code)
        emit("drawtic_lobby", {"players": public_players(room), "host": token == room["host"],
             "rounds": room["rounds"], "theme": room["theme"], "state": room["state"]})
        if room["state"] == "drawing":
            emit("drawtic_turn", {"round": room["round"], "rounds": room["rounds"],
                "drawer": room["players"][room["drawer"]]["nome"], "drawer_id": room["drawer"],
                "duration": max(0, int(room["turn_end"] - time.time())),
                "word": room["word"] if token == room["drawer"] else None})
        elif room["state"] == "revealing":
            emit("drawtic_reveal", {"word": room["word"], "drawer": room["players"][room["drawer"]]["nome"],
                "ranking": ranking(room)})

    @socketio.on("drawtic_config")
    def drawtic_config(data):
        data = data or {}
        room = rooms.get(data.get("code"))
        token = data.get("token")
        if not room or token != room["host"] or room["state"] != "lobby":
            return
        if data.get("rounds") in [3, 5, 10]:
            room["rounds"] = data["rounds"]
        if data.get("theme") in THEMES:
            room["theme"] = data["theme"]
        socketio.emit("drawtic_lobby", {"players": public_players(room), "host": True,
            "rounds": room["rounds"], "theme": room["theme"], "state": room["state"]}, to="drawtic_" + data["code"])

    @socketio.on("drawtic_start")
    def drawtic_start(data):
        data = data or {}
        room = rooms.get(data.get("code"))
        if not room or data.get("token") != room["host"] or room["state"] != "lobby":
            return
        if len(room["players"]) < 2:
            emit("drawtic_error", {"message": "São necessários pelo menos dois jogadores."})
            return
        room["words"] = list(THEMES[room["theme"]])
        random.shuffle(room["words"])
        room["order"] = list(room["players"].keys())
        room["round"] = 1
        room["turn_index"] = 0
        for player in room["players"].values():
            player["pontos"] = 0
        begin_turn(socketio, data["code"])

    @socketio.on("drawtic_stroke")
    def drawtic_stroke(data):
        data = data or {}
        room = rooms.get(data.get("code"))
        if not room or room["state"] != "drawing" or data.get("token") != room["drawer"]:
            return
        stroke = data.get("stroke")
        if not isinstance(stroke, dict) or len(str(stroke)) > 12000:
            return
        socketio.emit("drawtic_stroke", {"stroke": stroke}, to="drawtic_" + data["code"], include_self=False)

    @socketio.on("drawtic_clear")
    def drawtic_clear(data):
        data = data or {}
        room = rooms.get(data.get("code"))
        if room and room["state"] == "drawing" and data.get("token") == room["drawer"]:
            socketio.emit("drawtic_clear", {}, to="drawtic_" + data["code"])

    @socketio.on("drawtic_chat")
    def drawtic_chat(data):
        data = data or {}
        code, token = data.get("code"), data.get("token")
        room = rooms.get(code)
        if not room or room["state"] != "drawing" or token not in room["players"]:
            return
        if token == room["drawer"] or token in room["guessed"]:
            return
        message = str(data.get("message", "")).strip()[:100]
        if not message:
            return
        if clean_answer(message) == clean_answer(room["word"]):
            position = len(room["guessed"])
            points = POINTS[position] if position < len(POINTS) else 30
            room["players"][token]["pontos"] += points
            room["players"][room["drawer"]]["pontos"] += 20
            room["guessed"].append(token)
            socketio.emit("drawtic_chat_message", {"name": room["players"][token]["nome"],
                "message": "Acertou!", "correct": True, "points": points}, to="drawtic_" + code)
            socketio.emit("drawtic_score", {"ranking": ranking(room),
                "guessed": len(room["guessed"])}, to="drawtic_" + code)
            eligible = [pid for pid, p in room["players"].items() if pid != room["drawer"] and p["sid"]]
            if eligible and all(pid in room["guessed"] for pid in eligible):
                finish_turn(socketio, code, "all_guessed")
        else:
            socketio.emit("drawtic_chat_message", {"name": room["players"][token]["nome"],
                "message": message, "correct": False}, to="drawtic_" + code)

    @socketio.on("drawtic_end_turn")
    def drawtic_end_turn(data):
        data = data or {}
        room = rooms.get(data.get("code"))
        if room and room["state"] == "drawing" and data.get("token") == room["drawer"]:
            finish_turn(socketio, data["code"], "drawer_finished")
