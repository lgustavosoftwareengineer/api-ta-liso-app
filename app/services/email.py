import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

async def send_login_code(email: str, code: str) -> None:
    settings = get_settings()
    client = boto3.client(
        "ses",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

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
        client.send_email(
            Source=settings.ses_from_email,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body_text, "Charset": "UTF-8"},
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )
    except ClientError as e:
        raise RuntimeError(f"Falha ao enviar e-mail: {e.response['Error']['Message']}")
