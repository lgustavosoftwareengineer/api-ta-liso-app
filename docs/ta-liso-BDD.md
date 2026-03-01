# Tá Liso — Cenários BDD

Cenários Gherkin em sincronia com as regras de negócio da API.

---

## Integração Telegram

### Registro e vinculação de conta

**Cenário: Usuário não vinculado recebe pedido de e-mail**

- Dado que o usuário envia qualquer mensagem ao bot do Telegram
- E não existe vínculo entre o `telegram_chat_id` e um usuário do Tá Liso
- Quando o webhook processa a mensagem
- Então o bot responde pedindo o e-mail cadastrado no app

**Cenário: Usuário envia e-mail e recebe pedido de código**

- Dado que o usuário não está vinculado
- Quando o usuário envia um e-mail válido cadastrado no Tá Liso
- Então o sistema chama `request_login_code` para esse e-mail
- E o bot responde pedindo o código de 6 dígitos enviado por e-mail

**Cenário: Usuário envia código e fica vinculado**

- Dado que existe um registro em `telegram_pending_auth` para o `telegram_chat_id` com um e-mail
- E o usuário já recebeu o código por e-mail
- Quando o usuário envia o código de 6 dígitos correto
- Então o sistema valida com `authenticate` e cria o vínculo em `telegram_users`
- E remove o registro de `telegram_pending_auth`
- E o bot confirma o registro e passa a aceitar mensagens normais

**Cenário: Usuário vinculado envia mensagem e recebe resposta do chat**

- Dado que existe um vínculo em `telegram_users` entre o `telegram_chat_id` e um `user_id`
- Quando o usuário envia uma mensagem de texto (ex.: "gastei 30 no almoço")
- Então o webhook agenda o processamento em background
- E o sistema chama `chat_service.process_message(db, user_id, message)`
- E o bot envia a resposta formatada ao usuário no Telegram
