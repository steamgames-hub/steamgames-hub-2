from flask_mail import Message
from flask import current_app

# Use the central mail extension from the application package
from app import mail


def send_email(to, subject, template):
    sender = current_app.config.get("MAIL_DEFAULT_SENDER", "no-reply@steamgameshub.io")
    message = Message(
        subject,
        recipients=[to],
        html=template,
        sender=sender,
    )
    mail.send(message)