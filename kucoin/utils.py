# utils.py

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Carregar configurações do servidor de e-mail a partir do .env
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))  # Porta padrão para TLS é 587
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# E-mails de origem e destino
FROM_EMAIL = os.getenv('FROM_EMAIL')
TO_EMAIL = os.getenv('TO_EMAIL')  # Você pode usar uma lista separada por vírgulas para múltiplos destinatários

def send_email_notification(subject, message):
    """
    Envia uma notificação por e-mail com o assunto e mensagem fornecidos.
    """
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL, TO_EMAIL]):
        print("Configurações de e-mail incompletas. Verifique o arquivo .env.")
        return

    try:
        # Criar a mensagem
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        msg['Subject'] = subject

        # Anexar o corpo da mensagem
        msg.attach(MIMEText(message, 'plain'))

        # Conectar ao servidor SMTP
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()  # Inicia a conexão TLS
        server.login(SMTP_USER, SMTP_PASSWORD)

        # Enviar o e-mail
        server.send_message(msg)
        server.quit()
        print("E-mail enviado com sucesso.")

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
