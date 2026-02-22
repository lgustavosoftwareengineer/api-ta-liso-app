# ☁️ Tá Liso App — Infra & Deploy AWS

> **Infra:** EC2 t4g.micro + RDS db.t3.micro — AWS Free Tier  
> **Custo:** ~US$ 1/mês nos primeiros 12 meses · ~US$ 22/mês após o free tier  
> **Região:** sa-east-1 (São Paulo)

---

## 1. Visão Geral da Arquitetura

```
Internet
   │ HTTPS
   ▼
Route 53 ──► CloudFront + S3  (frontend Vue.js estático)
   │
   │ api.seudominio.com.br → Elastic IP
   ▼
EC2 t4g.micro  [Public Subnet]
  ├── Nginx :443  →  proxy  →  :8000
  ├── Gunicorn + Uvicorn (FastAPI)
  ├── Redis local (tokens de login)
  └── Certbot (TLS Let's Encrypt — gratuito)
   │
   │ porta 5432  (Security Group privado)
   ▼
RDS db.t3.micro  [Private Subnet]
  └── PostgreSQL 16
```

**CI/CD:** GitHub Actions → SSH → git pull + pip install + alembic upgrade + systemctl restart

---

## 2. Custos Mensais

| Serviço | Free Tier | Custo/mês |
|---|---|---|
| EC2 t4g.micro | 750h/mês por 12 meses | **US$ 0** |
| RDS db.t3.micro | 750h + 20 GB por 12 meses | **US$ 0** |
| S3 + CloudFront | 5 GB storage + 1 TB transferência | **US$ 0** |
| SES | 3.000 e-mails/mês sempre grátis | **US$ 0** |
| CloudWatch | Logs e métricas básicas grátis | **US$ 0** |
| Elastic IP | Grátis se associado ao EC2 rodando | **US$ 0** |
| Certbot / Let's Encrypt | Sempre grátis | **US$ 0** |
| Route 53 | 1 hosted zone (sem free tier) | **~US$ 1** |
| **Total (12 primeiros meses)** | | **~US$ 1/mês** |

> **Após 12 meses:** EC2 ~US$ 6 + RDS ~US$ 15 + Route 53 ~US$ 1 = **~US$ 22/mês**

---

## 3. Pré-requisitos

```bash
# Instalar AWS CLI v2
# https://aws.amazon.com/cli/

# Configurar credenciais
aws configure
# AWS Access Key ID:     <sua-key>
# AWS Secret Access Key: <seu-secret>
# Default region:        sa-east-1
# Default output:        json

# Confirmar
aws sts get-caller-identity
```

---

## 4. RDS PostgreSQL (db.t3.micro — Free Tier)

### 4.1 Criar subnet group

```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name taliso-subnet \
  --db-subnet-group-description "Tá Liso" \
  --subnet-ids subnet-xxxxxx subnet-yyyyyy
```

> Use as subnet IDs da VPC default da sua conta. Você as encontra em: AWS Console → VPC → Subnets.

### 4.2 Criar instância RDS

```bash
aws rds create-db-instance \
  --db-instance-identifier taliso-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username taliso_admin \
  --master-user-password <senha-forte> \
  --db-name taliso \
  --allocated-storage 20 \
  --db-subnet-group-name taliso-subnet \
  --no-publicly-accessible \
  --backup-retention-period 7
```

### 4.3 Pegar o endpoint (após ~5 minutos)

```bash
aws rds describe-db-instances \
  --db-instance-identifier taliso-db \
  --query "DBInstances[0].Endpoint.Address" \
  --output text
# → taliso-db.xxxxxxxxx.sa-east-1.rds.amazonaws.com
```

Guarde esse endpoint — ele vai no `DATABASE_URL` do `.env` de produção.

---

## 5. EC2 (t4g.micro ARM — Free Tier)

### 5.1 Par de chaves SSH

```bash
aws ec2 create-key-pair \
  --key-name taliso-key \
  --query "KeyMaterial" \
  --output text > taliso-key.pem
chmod 400 taliso-key.pem
```

### 5.2 Security Group

```bash
aws ec2 create-security-group \
  --group-name taliso-sg \
  --description "Tá Liso App"

# Portas necessárias
aws ec2 authorize-security-group-ingress --group-name taliso-sg --protocol tcp --port 22  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name taliso-sg --protocol tcp --port 80  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name taliso-sg --protocol tcp --port 443 --cidr 0.0.0.0/0
```

> Também crie um Security Group separado para o RDS que aceite apenas conexões na porta 5432 vindas do Security Group do EC2.

### 5.3 Lançar instância

```bash
# Busque o AMI ID atual do Ubuntu 24 LTS ARM64 em sa-east-1:
# AWS Console → EC2 → Launch Instance → Ubuntu 24 → selecione a AMI e copie o ID

aws ec2 run-instances \
  --image-id <ami-ubuntu-24-arm64-sa-east-1> \
  --instance-type t4g.micro \
  --key-name taliso-key \
  --security-groups taliso-sg \
  --count 1
```

> **Nota:** o t4g.micro usa arquitetura ARM (Graviton). Python 3.11 e todas as bibliotecas do projeto têm suporte completo a ARM.

### 5.4 Elastic IP (IP fixo)

```bash
# Alocar
aws ec2 allocate-address --domain vpc
# → retorna o AllocationId: eipalloc-xxxxxxxxx

# Associar à instância
aws ec2 associate-address \
  --instance-id <instance-id> \
  --allocation-id eipalloc-xxxxxxxxx
```

---

## 6. Configurar o Servidor EC2

```bash
# Conectar via SSH
ssh -i taliso-key.pem ubuntu@<elastic-ip>
```

### 6.1 Instalar dependências do sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip \
                   nginx redis-server git
```

### 6.2 Clonar e configurar a aplicação

```bash
git clone https://github.com/seu-usuario/ta-liso-backend.git /home/ubuntu/app
cd /home/ubuntu/app

# Virtualenv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Criar .env de produção
nano .env
```

`.env` de produção (valores reais):
```env
DATABASE_URL=postgresql+asyncpg://taliso_admin:<senha>@<endpoint-rds>:5432/taliso
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=<chave-aleatoria-longa>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
LOGIN_TOKEN_TTL_SECONDS=600
AWS_REGION=sa-east-1
SES_FROM_EMAIL=noreply@seudominio.com.br
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br
```

```bash
# Rodar migrations
alembic upgrade head

# Testar manualmente
gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
# Ctrl+C após confirmar que está funcionando
```

### 6.3 Serviço systemd

```bash
sudo nano /etc/systemd/system/taliso.service
```

```ini
[Unit]
Description=Tá Liso API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
Environment="PATH=/home/ubuntu/app/.venv/bin"
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/.venv/bin/gunicorn \
    app.main:app \
    -w 2 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile /var/log/taliso/access.log \
    --error-logfile /var/log/taliso/error.log
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/log/taliso && sudo chown ubuntu /var/log/taliso
sudo systemctl daemon-reload
sudo systemctl enable taliso
sudo systemctl start taliso
sudo systemctl status taliso
```

### 6.4 Nginx + TLS com Certbot

```bash
sudo nano /etc/nginx/sites-available/taliso
```

```nginx
server {
    listen 80;
    server_name api.seudominio.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.seudominio.com.br;

    ssl_certificate     /etc/letsencrypt/live/api.seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.seudominio.com.br/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/taliso /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Certificado TLS gratuito (Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.seudominio.com.br
# Certbot edita o nginx.conf automaticamente e configura renovação automática
```

---

## 7. SES — E-mail para Tokens de Login

```bash
# 1. Verificar domínio (gera registros DNS para adicionar no Route 53)
aws ses verify-domain-identity --domain seudominio.com.br

# 2. Verificar e-mail remetente
aws ses verify-email-identity --email-address noreply@seudominio.com.br

# 3. Sair do sandbox
# AWS Console → SES → Account dashboard → Request production access
# Necessário para enviar e-mails para qualquer endereço (não só verificados)
```

---

## 8. Frontend — S3 + CloudFront

```bash
# Criar bucket S3
aws s3 mb s3://taliso-frontend --region sa-east-1

# Build do Vue.js (no repositório do frontend)
npm run build

# Upload para o S3
aws s3 sync dist/ s3://taliso-frontend --delete
```

No AWS Console, criar distribuição CloudFront:
- **Origin:** `taliso-frontend.s3.amazonaws.com`
- **Viewer protocol policy:** Redirect HTTP to HTTPS
- **Default root object:** `index.html`
- **Custom error response:** 403/404 → `/index.html` com status 200 (necessário para Vue Router no modo history)

---

## 9. DNS — Route 53

```bash
# Criar hosted zone (se ainda não tiver)
aws route53 create-hosted-zone \
  --name seudominio.com.br \
  --caller-reference $(date +%s)
```

Registros necessários:
| Nome | Tipo | Valor |
|---|---|---|
| `api.seudominio.com.br` | A | Elastic IP do EC2 |
| `seudominio.com.br` | CNAME | domínio do CloudFront |
| `www.seudominio.com.br` | CNAME | domínio do CloudFront |

---

## 10. CI/CD com GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy EC2

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host:     ${{ secrets.EC2_HOST }}
          username: ubuntu
          key:      ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ubuntu/app
            git pull origin main
            source .venv/bin/activate
            pip install -r requirements.txt --quiet
            alembic upgrade head
            sudo systemctl restart taliso
            sudo systemctl status taliso --no-pager
```

**Secrets necessários** (GitHub → Settings → Secrets → Actions):

| Secret | Valor |
|---|---|
| `EC2_HOST` | Elastic IP da instância |
| `EC2_SSH_KEY` | Conteúdo do arquivo `taliso-key.pem` |

---

## 11. Checklist de Go-Live

### Infraestrutura
- [ ] RDS criado em subnet privada, endpoint anotado
- [ ] Security Group do RDS: apenas EC2 na porta 5432
- [ ] EC2 lançado com Elastic IP fixo associado
- [ ] Redis respondendo no EC2 (`redis-cli ping` → `PONG`)
- [ ] Nginx sem erros (`sudo nginx -t`)
- [ ] Certbot instalado, TLS ativo e renovação automática configurada
- [ ] Serviço systemd `taliso` habilitado e rodando

### Aplicação
- [ ] `.env` de produção no EC2 com todos os valores corretos
- [ ] `alembic upgrade head` executado com sucesso
- [ ] `GET /health` retornando `{"status": "ok"}`
- [ ] SES fora do sandbox (modo produção ativo)

### CI/CD e Frontend
- [ ] Secrets `EC2_HOST` e `EC2_SSH_KEY` no GitHub Actions
- [ ] Primeiro deploy automático testado com sucesso
- [ ] Build do Vue.js no S3, CloudFront apontando para o bucket
- [ ] `VITE_API_URL=https://api.seudominio.com.br` no build do frontend
- [ ] Route 53 com registros DNS configurados

---

*Documentação de Infra — Tá Liso App.*
