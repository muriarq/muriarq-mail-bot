import os
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

# Inicializar Firebase desde archivo
cred = credentials.Certificate('firebase-credentials.json')
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

        if not email.endswith('@muriarq.com'):
            bot.reply_to(message, "❌ Solo se permiten correos de @muriarq.com")
            return

        # Buscar en Firestore quién tiene permiso para este correo
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
