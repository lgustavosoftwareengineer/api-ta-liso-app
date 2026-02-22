# 🗃️ Tá Liso App — Diagrama de Entidades (ERD)

```mermaid
erDiagram

    users {
        UUID        id              PK
        VARCHAR255  email           UK "NOT NULL"
        VARCHAR100  name            "NOT NULL"
        TIMESTAMPTZ created_at      "DEFAULT NOW()"
    }

    login_tokens {
        UUID        id              PK
        UUID        user_id         FK
        VARCHAR6    token           "NOT NULL — 6 dígitos"
        TIMESTAMPTZ expires_at      "NOT NULL — TTL 10min"
        BOOLEAN     used            "DEFAULT false"
        TIMESTAMPTZ created_at      "DEFAULT NOW()"
    }

    user_settings {
        UUID        id                      PK
        UUID        user_id                 FK
        BOOLEAN     alert_low_balance       "DEFAULT true"
        BOOLEAN     monthly_reset           "DEFAULT true"
        BOOLEAN     block_negative_balance  "DEFAULT false"
        TIMESTAMPTZ updated_at              "DEFAULT NOW()"
    }

    categories {
        UUID        id               PK
        UUID        user_id          FK
        VARCHAR100  name             "NOT NULL"
        VARCHAR10   icon             "emoji"
        NUMERIC102  initial_amount   "NOT NULL — orçamento"
        NUMERIC102  current_balance  "NOT NULL — saldo atual"
        SMALLINT    reset_month      "lazy reset"
        SMALLINT    reset_year       "lazy reset"
        TIMESTAMPTZ created_at       "DEFAULT NOW()"
        TIMESTAMPTZ updated_at       "DEFAULT NOW()"
    }

    transactions {
        UUID        id           PK
        UUID        user_id      FK
        UUID        category_id  FK "SET NULL on delete"
        VARCHAR255  description  "NOT NULL"
        NUMERIC102  amount       "NOT NULL"
        TIMESTAMPTZ created_at   "DEFAULT NOW()"
    }

    category_monthly_snapshots {
        UUID        id             PK
        UUID        category_id    FK
        SMALLINT    month          "1–12"
        SMALLINT    year           "ex: 2025"
        NUMERIC102  initial_amount "orçamento do mês"
        NUMERIC102  total_spent    "total gasto"
        NUMERIC102  final_balance  "saldo ao fechar o mês"
        TIMESTAMPTZ created_at     "DEFAULT NOW()"
    }

    users            ||--o{ login_tokens                : "gera"
    users            ||--||  user_settings              : "possui"
    users            ||--o{ categories                  : "cria"
    users            ||--o{ transactions                : "registra"
    categories       ||--o{ transactions                : "classifica"
    categories       ||--o{ category_monthly_snapshots  : "gera snapshot"
```

---

## Relacionamentos

| De | Para | Cardinalidade | Comportamento |
|---|---|---|---|
| `users` | `login_tokens` | 1 : N | ON DELETE CASCADE |
| `users` | `user_settings` | 1 : 1 | ON DELETE CASCADE |
| `users` | `categories` | 1 : N | ON DELETE CASCADE |
| `users` | `transactions` | 1 : N | ON DELETE CASCADE |
| `categories` | `transactions` | 1 : N | ON DELETE SET NULL |
| `categories` | `category_monthly_snapshots` | 1 : N | ON DELETE CASCADE |

---

## Descrição das Entidades

### `users` — Entidade central
Armazena o cadastro do usuário. O `email` é o identificador único usado no login passwordless. O `name` é editável pela tela de Configurações.

### `login_tokens` — Autenticação
Cada solicitação de login gera um token numérico de 6 dígitos. O campo `used` é marcado como `true` após o primeiro uso válido, impedindo reutilização. O `expires_at` controla o TTL de 10 minutos.

### `user_settings` — Configurações
Criado automaticamente junto com o usuário. Armazena os 3 toggles da tela de Configurações: alerta de saldo crítico, reset mensal automático e bloqueio de saldo negativo.

### `categories` — Core
Cada categoria tem um orçamento (`initial_amount`) e um saldo atual (`current_balance`). Os campos `reset_month` e `reset_year` implementam o mecanismo de **lazy reset**: ao invés de um cron job, o sistema compara esses campos com o mês atual no momento do acesso e reseta o saldo se necessário.

### `transactions` — Core
Registra cada lançamento feito via chat. O `category_id` usa `SET NULL` na exclusão da categoria para preservar o histórico financeiro do usuário mesmo que a categoria seja removida.

### `category_monthly_snapshots` — Histórico
Gerado automaticamente no momento do lazy reset. Armazena o orçamento, total gasto e saldo final de cada categoria em cada mês encerrado. Alimenta a tela de Resumo para navegação por meses anteriores.
