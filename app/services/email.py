import resend

from app.config import get_settings


async def send_login_code(email: str, code: str) -> None:
    settings = get_settings()
    resend.api_key = settings.resend_api_key

    subject = "Seu código de acesso — Tá Liso"
    body_text = f"Seu código de login é: {code}\n\nEle expira em 10 minutos."
    body_html = f"""
    <html>
      <body>
        <h2>Tá Liso — Código de acesso</h2>
        <p>Use o código abaixo para entrar na sua conta:</p>
        <h1 style="letter-spacing: 8px;">{code}</h1>
        <p>O código expira em <strong>10 minutos</strong>.</p>
        <p>Se você não solicitou este código, ignore este e-mail.</p>
      </body>
    </html>
    """

    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [email],
            "subject": subject,
            "html": body_html,
            "text": body_text,
        })
    except Exception as e:
        raise RuntimeError(f"Falha ao enviar e-mail: {e}")
