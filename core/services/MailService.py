import os
from threading import Thread

from flask import current_app
from flask_mail import Message

from app import mail

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail


class MailService:
    def _send_via_sendgrid(self, to: str, subject: str, body: str):
        app = current_app._get_current_object()
        sg_api_key = os.environ.get("SENDGRID_API_KEY")
        from_email = os.environ.get("FROM_EMAIL")

        if not sg_api_key or not from_email:
            raise RuntimeError("SENDGRID_API_KEY o FROM_EMAIL no configuradas")

        if SGMail is None or SendGridAPIClient is None:
            raise RuntimeError("SendGrid SDK no disponible")

        message = SGMail(
            from_email=from_email,
            to_emails=to,
            subject=subject,
            html_content=body.replace("\n", "<br>")
        )

        try:
            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)
            app.logger.info(f"Correo enviado a {to} | Status: {response.status_code}")
        except Exception as e:
            app.logger.exception(f"Error enviando correo vía SendGrid: {e}")
            raise

    def send_email(self, to: str, subject: str, body: str):
        """
        Envía el correo en un Thread.
        Usa SendGrid si hay API key, o Flask-Mail si no.
        """
        app = current_app._get_current_object()

        def _send():
            with app.app_context():
                try:
                    if os.environ.get("SENDGRID_API_KEY"):
                        self._send_via_sendgrid(to, subject, body)
                    else:
                        msg = Message(subject, recipients=[to], body=body)
                        mail.send(msg)
                except Exception as e:
                    app.logger.exception(f"Fallo al enviar correo a {to}: {e}")

        Thread(target=_send, daemon=True).start()
