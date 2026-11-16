import os
import random
import uuid
from threading import Lock

from werkzeug.exceptions import HTTPException
from flask import Flask, jsonify, request, send_from_directory
from itsdangerous import BadSignature, URLSafeSerializer

app = Flask(__name__, static_folder="static")
firmador = URLSafeSerializer(os.environ.get("SIGNING_KEY") or os.urandom(32).hex())
jugadores = set()    # nombres registrados en /login (solo en memoria)
juegos = {}          # id -> diccionario del juego (solo en memoria)
cerrojo = Lock()


class ErrorApi(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = codigo


@app.errorhandler(ErrorApi)
def manejar_error(e):
    return jsonify(error=str(e)), e.codigo


@app.errorhandler(HTTPException)
def manejar_http(e):
    return jsonify(error=e.description), e.code


def cuerpo():
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def jugador_actual():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    try:
        nombre = firmador.loads(token)
    except BadSignature:
        raise ErrorApi("Debes iniciar sesión en /login", 401)
    if nombre not in jugadores:
        raise ErrorApi("Sesión no registrada, vuelve a iniciar sesión en /login", 401)
    return nombre


def leer_numero(datos):
    valor = datos.get("numero")
    if isinstance(valor, int) and not isinstance(valor, bool):
        valor = str(valor)
    if not isinstance(valor, str) or not (valor.isascii() and valor.isdigit()):
        raise ErrorApi("El número debe contener solo dígitos")
    if len(valor) != 4:
        raise ErrorApi("El número debe tener exactamente 4 dígitos")
    if len(set(valor)) != 4:
        raise ErrorApi("El número no puede tener dígitos repetidos")
    return valor


def obtener_juego(id_juego):
    juego = juegos.get(id_juego)
    if juego is None:
        raise ErrorApi("Juego no encontrado", 404)
    return juego


def resumen(j):
    return {"id": j["id"], "creador": j["creador"], "estado": j["estado"],
            "jugadores": j["jugadores"], "ganador": j["ganador"]}


@app.get("/")
def inicio():
    return send_from_directory("static", "index.html")


@app.post("/login")
def login():
    nombre = str(cuerpo().get("nombre", "")).strip()
    if not 1 <= len(nombre) <= 20:
        raise ErrorApi("El nombre debe tener entre 1 y 20 caracteres")
    jugadores.add(nombre)
    return jsonify(nombre=nombre, token=firmador.dumps(nombre))


@app.post("/juego")
def crear():
    yo = jugador_actual()
    numero = leer_numero(cuerpo())
    juego = {"id": uuid.uuid4().hex[:6], "creador": yo, "estado": "sin_completar",
             "jugadores": [yo], "numeros": {yo: numero}, "turno": None,
             "ganador": None, "jugadas": []}
    with cerrojo:
        juegos[juego["id"]] = juego
    return jsonify(resumen(juego)), 201


@app.get("/juego")
def listar():
    jugador_actual()
    with cerrojo:
        return jsonify([resumen(j) for j in juegos.values()])


@app.get("/juego/<id_juego>")
def ver(id_juego):
    jugador_actual()
    with cerrojo:
        j = obtener_juego(id_juego)
        return jsonify(resumen(j) | {"turno": j["turno"], "jugadas": j["jugadas"]})


@app.put("/juego/<id_juego>")
def unirse(id_juego):
    yo = jugador_actual()
    datos = cuerpo()
    if datos.get("nombre", yo) != yo:
        raise ErrorApi("El nombre no coincide con tu sesión", 403)
    numero = leer_numero(datos)
    with cerrojo:
        j = obtener_juego(id_juego)
        if j["estado"] != "sin_completar":
            raise ErrorApi("El juego ya no admite más jugadores", 409)
        if yo in j["jugadores"]:
            raise ErrorApi("No puedes unirte a tu propio juego", 409)
        j["jugadores"].append(yo)
        j["numeros"][yo] = numero
        j["estado"] = "en_juego"
        j["turno"] = random.choice(j["jugadores"])
        return jsonify(resumen(j) | {"turno": j["turno"]})


@app.post("/juego/<id_juego>/jugar")
def jugar(id_juego):
    yo = jugador_actual()
    intento = leer_numero(cuerpo())
    with cerrojo:
        j = obtener_juego(id_juego)
        if yo not in j["jugadores"]:
            raise ErrorApi("No participas en este juego", 403)
        if j["estado"] != "en_juego":
            raise ErrorApi("El juego no está en curso", 409)
        if j["turno"] != yo:
            raise ErrorApi("No es tu turno", 409)
        rival = next(p for p in j["jugadores"] if p != yo)
        secreto = j["numeros"][rival]
        fijas = sum(a == b for a, b in zip(intento, secreto))
        picas = len(set(intento) & set(secreto)) - fijas
        j["jugadas"].append({"jugador": yo, "numero": intento, "picas": picas, "fijas": fijas})
        if fijas == 4:
            j["estado"], j["ganador"], j["turno"] = "terminado", yo, None
        else:
            j["turno"] = rival
        return jsonify({"picas": picas, "fijas": fijas, "estado": j["estado"],
                        "ganador": j["ganador"], "turno": j["turno"]})
