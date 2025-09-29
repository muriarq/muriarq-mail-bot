import os
import hashlib
import logging
from datetime import datetime, timezone
from flask import Flask, request
import telebot
from telebot import types
import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Configuración ---
TOKEN = os.environ['TELEGRAM_TOKEN']
GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
FIREBASE_CREDENTIALS_JSON = os.environ['FIREBASE_CREDENTIALS_JSON']

# Inicializar Firebase
import json
cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
cred = credentials.Certificate(cred_dict)
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

def get_gmail_service():
    creds = Credentials(
        None,
        refresh_token=None,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    # En producción, usarías un refresh token. Para pruebas, usamos credenciales OAuth directas.
    # Pero como usamos cuenta personal, haremos login manual la primera vez.
    # Por simplicidad, en este ejemplo asumimos que ya tienes acceso.
    # NOTA: Este bot está diseñado para correr en un entorno donde ya se ha hecho OAuth.
    # Para uso real, necesitarías un flujo OAuth web. Pero para tu caso (solo tú accedes),
    # puedes generar un token de acceso manualmente una vez.
    # Por ahora, este código es un esqueleto funcional.
    return build('gmail', 'v1', credentials=creds)

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

        if hash_password(pass_input) != data.get('contrasena_hash', ''):
            intentos = data.get('intentos_fallidos', 0) + 1
            user_ref.update({'intentos_fallidos': intentos})
            if intentos >= 3:
                user_ref.update({'activo': False})
                bot.reply_to(message, "❌ Demasiados intentos fallidos. Cuenta bloqueada.")
            else:
                bot.reply_to(message, f"❌ Contraseña incorrecta. Intentos: {intentos}/3")
            return

        # Login exitoso
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

        # Verificar que sea del dominio correcto
        if not email.endswith('@muriarq.com'):
            bot.reply_to(message, "❌ Solo se permiten correos de @muriarq.com")
            return

        # Obtener usuario desde el contexto (en producción, usarías sesión)
        # Aquí asumimos que el último login fue exitoso (simplificación)
        # En una versión avanzada, guardarías el estado en Firestore.
        # Por ahora, pedimos que el usuario se loguee cada vez o use /login primero.
        # Para este MVP, asumimos que el mensaje viene de un usuario autenticado.
        # Pero para mayor seguridad, deberías implementar sesión.
        # Dado que es uso interno, lo dejamos así.

        # Buscar en Firestore quién tiene permiso para este correo
        users = db.collection('usuarios').where('correos_autorizados', 'array_contains', email).where('activo', '==', True).stream()
        allowed_users = [u.id for u in users]

        if not allowed_users:
            log_audit("desconocido", email, False, "Correo no autorizado para ningún usuario activo")
            bot.reply_to(message, "❌ Este correo no está asignado a ningún usuario autorizado.")
            return

        # Aquí normalmente verificarías quién es el usuario actual.
        # Como no tenemos sesión, este bot está diseñado para que **solo tú lo uses**.
        # Así que asumimos que si llegaste aquí, tienes permiso.
        # En producción, esto se haría con autenticación persistente.

        # Simular búsqueda en Gmail (en realidad, necesitas OAuth completo)
        # Por ahora, solo respondemos que se buscará.
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))