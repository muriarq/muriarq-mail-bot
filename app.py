import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from flask import Flask, request
import telebot
from telebot import types
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuración ---
TOKEN = os.environ['TELEGRAM_TOKEN']
GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']

# 🔥 Credenciales de Firebase DIRECTAMENTE en el código (solo para pruebas)
FIREBASE_CREDENTIALS_DICT = {
  "type": "service_account",
  "project_id": "muriarq-mail-bot-cd937",
  "private_key_id": "4fa4f9f50920ff7d6c447b05e847b5651e6d0b29",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDS4AUdP84wCtvV\n5OMrcAwJzYRA2nuzVroISwZnq2D8FPGdMSYVLVd73AIkIsJMVh4vXCZPv6BR6+OQ\nvKEh1QsbR6rJbqK4YWg+FAVYQhucHuVkoZ7xFvbwc7itNcN0/uhMbDwVb4w9gEg+\nJ31Tntl8uZ7ok0yoJuWfOtMZiPAI3tbgFSEUbaQ6wPD3U0BQyMVW99PeUBaMRMVH\noQDuse0X0j/LzxTCX0yppUGw5G1eMrNPOUfupBEyJhh2hAjIIk28Eek5vVDLEh4K\n2FoTWh1g1PnGAOMLJ6igNz3hwsZ0w/QBmI/S7ZdiNnyNArGqmdnVtJIbn8s471T1\nZx5AaXv3AgMBAAECggEAUjYACG0tp1E0b2kyn2apatDytI35F+vBzyXgs13/C4fm\nwk+89xicOK+HLitW8IfKcNBOJ10f1ZBPQcgoUZZLJDGGhc1aJuPizgDkLIppVS4+\nZEMWQguf7hJPd0e0kdInIlQ4AGtikz+F6qVemNEfHR8IssdqZUv0zWUTk6rtWadB\nakl2rtPArk2QdjvcPh6CXX/TZEBfi4D/ZIRjo+Yr789NQVEJV7g7iVbKGVmtpEnD\nTuyz4sQJdNKZgT56LUxLGDIkqwmtSc5JOgQViYeYl+IUHGlfojYBVngffuAh2w+y\n7dpkj34gYvlwY2AdqbxrOKXu1htMsGU4QiGcjg7mcQKBgQDy6Mh5suKnyImtBatS\nokReJ2mAmXL8R7Aj2PJZKxDaSXhTHBPs6sBTv+JL0LZbc5tduUqPbjG7ew75Yexn\nPFdc8jgerEZGhDfKtTmkKmLkLiEXQDhdSIYxy3i0RU6fKBFrWK2mWnBfAUIM57Sh\nY2qAnvbJdobiCXDFKzUadM16lQKBgQDePUmO3sh9vPWcCb1iteJSWFBLkrz2PR7f\nI0HSOWauWZxiOtcA4OxkFjSCAgxfzxA25hvmnfwujNPEPp1T9O7ybUHtDFRPHcwB\n2i+O1msMZVCXSm66BsmWSah0a3Y10OZqThZFxacp0byiLSALFuPKlae50MgBQW4p\nwcze05IFWwKBgQChIk4qfMHh7yN1BTe63y1fD+HqjuA5/gwYG4fYIrtRMj+BUjTd\ninP+mmExTchKLgw4Rfvx3XVcGqu6Pn0lll+VppAXuMv9ZyPjcghEoGFtYDRPSiiZ\nqMxsJ79wRjF7Xob/oJnAqmm0fA8mpGWsUViK7ehjiB69vulxwdG+NRFBaQKBgAlC\nzozolbw/opCFC2JQqAS8b2Qm0j8EnwO3aWfEQpYjX9PsFceQl+k3z6pXQYLAkzFm\nd2Ut0jNyZOS5oz67ZzWs/eFN8Tl2yWiOWgr+vmk+05PqYyDXZZEgsqdfTwbBFMj7\nRgxURzoD5nNvo/UyV/26LMoefCcpPdj5nXrvoBcfAoGABRkErOKSReK7h2T3S26d\nmcdLnL7RoPKqOdPSEdTwxrRi8bDlfYzOucoByReMw1T71erIV/ANu9k+HblNjiim\n/APQRIkzO1XQSOTjW3HAqztVKrhanubgqWhfk757CmLL8u7oA6VqKDPPyaUKMLha\nYQQRfqfAKOaFdBXFMPORS/k=\n-----END PRIVATE KEY-----",
  "client_email": "firebase-adminsdk-fbsvc@muriarq-mail-bot-cd937.iam.gserviceaccount.com",
  "client_id": "102258804977016542352",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc@muriarq-mail-bot-cd937.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

# Inicializar Firebase desde diccionario
cred = credentials.Certificate(FIREBASE_CREDENTIALS_DICT)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Inicializar bot
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- Funciones auxiliares ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def log_audit(usuario, correo, permitido, mensaje):
    db.collection('auditoria').add({
        'usuario': usuario,
        'correo_solicitado': correo,
        'acceso_permitido': permitido,
        'mensaje': mensaje,
        'fecha': datetime.now(timezone.utc)
    })

# --- Comandos del bot ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🔐 Bienvenido al Bot de Correos Muriarq.\n\nPor favor, inicia sesión:\n`/login usuario contraseña`", parse_mode="Markdown")

@bot.message_handler(commands=['login'])
def login(message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ Uso: `/login usuario contraseña`", parse_mode="Markdown")
            return

        user_input = parts[1]
        pass_input = parts[2]

        user_ref = db.collection('usuarios').document(user_input)
        doc = user_ref.get()
        if not doc.exists:
            bot.reply_to(message, "❌ Usuario no encontrado.")
            return

        data = doc.to_dict()
        if not data.get('activo', False):
            bot.reply_to(message, "❌ Usuario desactivado.")
            return

        stored_hash = data.get('contrasena_hash', '')
        input_hash = hash_password(pass_input)

        if input_hash != stored_hash:
            intentos = data.get('intentos_fallidos', 0) + 1
            user_ref.update({'intentos_fallidos': intentos})
            if intentos >= 3:
                user_ref.update({'activo': False})
                bot.reply_to(message, "❌ Demasiados intentos fallidos. Cuenta bloqueada.")
            else:
                bot.reply_to(message, f"❌ Contraseña incorrecta. Intentos: {intentos}/3")
            return

        user_ref.update({
            'ultimo_acceso': datetime.now(timezone.utc),
            'intentos_fallidos': 0
        })
        bot.reply_to(message, "✅ ¡Inicio de sesión exitoso!\n\nUsa: `/correo nombre@muriarq.com` para consultar correos.")

    except Exception as e:
        logging.error(f"Error en login: {e}")
        bot.reply_to(message, "⚠️ Error interno. Contacta al administrador.")

@bot.message_handler(commands=['correo'])
def get_email(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Uso: `/correo nombre@muriarq.com`", parse_mode="Markdown")
            return
        email = parts[1].lower()

        if not email.endswith('@muriarq.com'):
            bot.reply_to(message, "❌ Solo se permiten correos de @muriarq.com")
            return

        users = db.collection('usuarios').where('correos_autorizados', 'array_contains', email).where('activo', '==', True).stream()
        allowed_users = [u.id for u in users]

        if not allowed_users:
            log_audit("desconocido", email, False, "Correo no autorizado para ningún usuario activo")
            bot.reply_to(message, "❌ Este correo no está asignado a ningún usuario autorizado.")
            return

        log_audit("daniel", email, True, "Consulta simulada (pendiente integración Gmail)")
        bot.reply_to(message, f"🔍 Buscando correos relacionados con `{email}` en tu bandeja...\n\n*(Nota: La integración completa con Gmail requiere un paso adicional de autorización OAuth. Te guiaré después.)*", parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Error en /correo: {e}")
        bot.reply_to(message, "⚠️ Error al procesar la solicitud.")

# --- Webhook para Render ---
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def index():
    return "Bot de Muriarq activo."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
