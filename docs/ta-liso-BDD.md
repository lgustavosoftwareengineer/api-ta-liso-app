# 📋 Estórias BDD — Tá Liso App

> Baseadas nas telas desenvolvidas no mockup (mobile + desktop):
> Login · Token · Início · Chat · Categorias · Resumo · Configurações

---

## Feature: Login sem senha via e-mail

### Scenario: Usuário solicita código de acesso com e-mail válido
```gherkin
Given que o usuário está na tela de login
When ele informa um e-mail válido no campo "Seu e-mail"
And clica em "Mandar o código 🚀"
Then o sistema deve gerar um token numérico de 6 dígitos
And salvar o token no Redis com TTL de 10 minutos
And enviar o token para o e-mail informado via SES
And redirecionar o usuário para a tela de validação do token
```

### Scenario: Usuário solicita código com e-mail inválido
```gherkin
Given que o usuário está na tela de login
When ele informa um e-mail com formato inválido (ex: "joaoemail.com")
And clica em "Mandar o código 🚀"
Then o sistema deve exibir mensagem de erro de formato de e-mail
And não deve enviar nenhum e-mail
And o usuário deve permanecer na tela de login
```

### Scenario: Usuário autentica com token válido
```gherkin
Given que o usuário está na tela de validação do token
And recebeu um token válido por e-mail
When ele informa o token de 6 dígitos corretamente
And clica em "Entrar"
Then o sistema deve validar o token no Redis
And gerar um JWT de sessão com validade de 7 dias
And redirecionar o usuário para a tela Início
```

### Scenario: Usuário informa token incorreto
```gherkin
Given que o usuário está na tela de validação do token
When ele informa um token incorreto
And clica em "Entrar"
Then o sistema deve exibir mensagem de token inválido
And o usuário deve permanecer na tela de validação
```

### Scenario: Usuário informa token expirado
```gherkin
Given que o usuário está na tela de validação do token
And o token gerado já expirou (mais de 10 minutos)
When ele informa o token expirado
And clica em "Entrar"
Then o sistema deve exibir mensagem de token expirado
And oferecer opção de solicitar um novo código
```

### Scenario: Usuário tenta acessar tela protegida sem autenticação
```gherkin
Given que o usuário não está autenticado
When ele tenta acessar qualquer tela protegida (Início, Chat, Categorias, Resumo, Configurações)
Then o sistema deve redirecionar para a tela de login
```

### Scenario: JWT do usuário expira durante uma sessão ativa
```gherkin
Given que o usuário está autenticado com um JWT válido
And o JWT tem validade de 7 dias
When o JWT expira e o usuário realiza qualquer requisição autenticada
Then a API deve retornar 401 Unauthorized
And o frontend deve remover o access_token do localStorage
And o frontend deve redirecionar o usuário para a tela de login
And o usuário deve realizar o fluxo de login novamente (solicitar novo código por e-mail)
```

---

## Feature: Tela Início — Visão geral do mês

### Scenario: Exibir resumo do mês atual ao entrar no app
```gherkin
Given que o usuário está autenticado
When ele acessa a tela Início
Then o sistema deve exibir o nome do usuário na saudação (ex: "E aí, João! 👋")
And exibir o mês e ano atuais
And exibir o card de saldo disponível com o total restante de todas as categorias
And exibir o total orçado (soma dos initial_amount de todas as categorias)
And exibir o total gasto no mês
And exibir o número de lançamentos do mês
```

### Scenario: Exibir alerta de categoria com saldo crítico
```gherkin
Given que o usuário está autenticado
And existe uma categoria com menos de 20% do saldo disponível
When ele acessa a tela Início
Then o sistema deve exibir um alerta destacado informando qual categoria está próxima do limite
And informar o valor restante disponível nessa categoria
```

### Scenario: Exibir cards de categorias com progresso
```gherkin
Given que o usuário possui categorias cadastradas com transações no mês
When ele acessa a tela Início
Then o sistema deve exibir cada categoria com seu ícone e nome
And exibir o saldo disponível, o valor orçado e o total gasto
And exibir uma barra de progresso proporcional ao percentual utilizado
And colorir a barra de verde quando abaixo de 70% utilizado
And colorir a barra de amarelo entre 70% e 89% utilizado
And colorir a barra de vermelho quando 90% ou mais utilizado
```

### Scenario: Exibir lista dos últimos lançamentos
```gherkin
Given que o usuário possui transações registradas no mês
When ele acessa a tela Início
Then o sistema deve exibir os lançamentos mais recentes
And exibir para cada lançamento: ícone da categoria, descrição, categoria e valor
```

### Scenario: Navegar para o chat ao clicar em "Registrar gasto"
```gherkin
Given que o usuário está na tela Início
When ele clica no botão "Registrar gasto" ou no ícone de chat da barra de navegação
Then o sistema deve navegar para a tela Chat
```

---

## Feature: Chat financeiro — Registro de gastos

### Scenario: Registrar gasto com categoria existente e saldo suficiente
```gherkin
Given que o usuário está autenticado
And existe a categoria "Alimentação" com saldo disponível de R$ 800,00
When ele envia a mensagem "Mercado 200 alimentação"
Then o sistema deve extrair: descrição "Mercado", valor R$ 200,00, categoria "Alimentação"
And registrar a transação no banco de dados
And subtrair R$ 200,00 do saldo da categoria
And responder no chat confirmando: "Anotado! ✅ − R$ 200,00 em Alimentação"
And exibir o saldo restante atualizado da categoria
```

### Scenario: Registrar gasto com saldo insuficiente e configuração de bloqueio desativada
```gherkin
Given que o usuário está autenticado
And a categoria "Lazer & Forró" possui saldo disponível de R$ 50,00
And a configuração "Bloquear saldo negativo" está desativada
When ele envia "Show de forró 500 lazer"
Then o sistema deve exibir alerta de saldo insuficiente no chat
And informar o saldo disponível (R$ 50,00) e o valor tentado (R$ 500,00)
And exibir botões "Deixa pra lá" e "Confirmar 🤞"
```

### Scenario: Usuário confirma gasto com saldo insuficiente
```gherkin
Given que o sistema exibiu alerta de saldo insuficiente
And a configuração "Bloquear saldo negativo" está desativada
When o usuário clica em "Confirmar 🤞"
Then o sistema deve registrar a transação
And deixar o saldo da categoria negativo
And confirmar o lançamento no chat
```

### Scenario: Usuário cancela gasto com saldo insuficiente
```gherkin
Given que o sistema exibiu alerta de saldo insuficiente
When o usuário clica em "Deixa pra lá"
Then o sistema deve cancelar o lançamento
And não registrar nenhuma transação
And exibir mensagem de cancelamento no chat
```

### Scenario: Registrar gasto com saldo insuficiente e bloqueio ativado
```gherkin
Given que a configuração "Bloquear saldo negativo" está ativada
And a categoria "Saúde" possui saldo de R$ 30,00
When o usuário envia "Consulta 150 saúde"
Then o sistema deve exibir alerta de saldo insuficiente
And informar que a operação está bloqueada pela configuração
And não exibir opção de confirmar
```

### Scenario: Mensagem com categoria inexistente
```gherkin
Given que o usuário está na tela Chat
When ele envia uma mensagem com uma categoria que não existe (ex: "Gasolina 100 carro")
Then o sistema deve responder informando que a categoria "carro" não foi encontrada
And sugerir as categorias existentes do usuário
And oferecer opção de criar a categoria
```

### Scenario: Mensagem com formato não reconhecido
```gherkin
Given que o usuário está na tela Chat
When ele envia uma mensagem que não segue o padrão esperado (ex: "oi tudo bem")
Then o sistema deve responder orientando o formato correto
And exibir exemplos: "Mercado 200 alimentação", "Uber 45 transporte"
```

### Scenario: Exibir saldos das categorias no painel lateral (desktop)
```gherkin
Given que o usuário está na tela Chat (versão desktop)
Then o sistema deve exibir no painel lateral direito todas as categorias
And mostrar o saldo disponível atual de cada uma com barra de progresso
And atualizar os saldos em tempo real após cada lançamento registrado
```

---

## Feature: Gerenciamento de Categorias

### Scenario: Criar nova categoria
```gherkin
Given que o usuário está autenticado
And acessa a tela Categorias
When ele informa um nome (ex: "Transporte")
And define um valor de orçamento mensal (ex: R$ 500,00)
And seleciona um ícone
And clica em "Salvar Categoria 💾"
Then o sistema deve salvar a categoria vinculada ao usuário
And definir o current_balance igual ao initial_amount
And exibir a nova categoria na listagem
```

### Scenario: Criar categoria com nome duplicado
```gherkin
Given que o usuário já possui uma categoria chamada "Alimentação"
When ele tenta criar outra categoria com o mesmo nome
Then o sistema deve exibir mensagem de erro informando que o nome já existe
And não salvar a categoria duplicada
```

### Scenario: Editar orçamento de uma categoria existente
```gherkin
Given que existe a categoria "Alimentação" com orçamento de R$ 1.000,00
When o usuário altera o valor do orçamento para R$ 1.500,00
And salva as alterações
Then o sistema deve atualizar o initial_amount para R$ 1.500,00
And recalcular o current_balance proporcionalmente
```

### Scenario: Editar nome e ícone de uma categoria
```gherkin
Given que existe a categoria "Comida" com ícone 🛒
When o usuário altera o nome para "Feira e Mercado"
And seleciona o ícone 🥗
And salva as alterações
Then o sistema deve atualizar o nome e o ícone da categoria
And refletir as mudanças em todos os lançamentos vinculados
```

### Scenario: Excluir categoria sem lançamentos
```gherkin
Given que existe a categoria "Teste" sem nenhum lançamento registrado
When o usuário clica no ícone de excluir da categoria
And confirma a exclusão
Then o sistema deve remover a categoria
And ela não deve mais aparecer na listagem
```

### Scenario: Excluir categoria com lançamentos exclui as transações em cascata
```gherkin
Given que existe a categoria "Alimentação" com lançamentos registrados
When o usuário confirma a exclusão da categoria
Then o sistema deve remover a categoria
And todas as transações vinculadas a essa categoria devem ser removidas junto
And a listagem de transações não deve mais exibir nenhum lançamento daquela categoria
```

### Scenario: Exibir progresso de cada categoria na listagem
```gherkin
Given que o usuário acessa a tela Categorias
Then para cada categoria o sistema deve exibir:
  | campo             | descrição                              |
  | Ícone + Nome      | identificação visual da categoria      |
  | Orçamento total   | valor do initial_amount                |
  | Total gasto       | soma das transações do mês             |
  | Saldo disponível  | current_balance atual                  |
  | Barra de progresso| percentual gasto em relação ao orçamento |
```

---

## Feature: Resumo mensal

### Scenario: Exibir resumo do mês atual
```gherkin
Given que o usuário está autenticado
And possui categorias com lançamentos no mês atual
When ele acessa a tela Resumo
Then o sistema deve exibir o mês e ano atuais no seletor
And exibir cards com: saldo restante total, total gasto e número de lançamentos
And exibir o breakdown por categoria com barras de progresso
And exibir a lista completa de todos os lançamentos do mês em ordem cronológica decrescente
And exibir o total gasto no rodapé da lista
```

### Scenario: Navegar para o mês anterior
```gherkin
Given que o usuário está na tela Resumo visualizando o mês atual
When ele clica no botão "‹" (mês anterior)
Then o sistema deve carregar os dados do mês anterior
And atualizar o label do seletor (ex: "Janeiro 2025")
And exibir os cards de métricas com os valores daquele mês
And exibir os lançamentos daquele mês
```

### Scenario: Navegar para o mês seguinte
```gherkin
Given que o usuário está na tela Resumo visualizando um mês passado
When ele clica no botão "›" (próximo mês)
Then o sistema deve carregar os dados do mês seguinte
And atualizar o label do seletor
```

### Scenario: Visualizar mês sem lançamentos
```gherkin
Given que o usuário navega para um mês sem nenhum lançamento registrado
When ele visualiza a tela Resumo para aquele mês
Then o sistema deve exibir os cards zerados
And exibir mensagem informando que não há lançamentos naquele mês
```

### Scenario: Exportar histórico como CSV
```gherkin
Given que o usuário está na tela Resumo
When ele clica em "Exportar CSV"
Then o sistema deve gerar um arquivo CSV com todos os lançamentos do mês visualizado
And iniciar o download do arquivo no dispositivo
And o arquivo deve conter: data, descrição, categoria e valor de cada lançamento
```

---

## Feature: Gerenciamento de Transações

### Scenario: Criar transação reduz o saldo da categoria
```gherkin
Given que o usuário possui a categoria "Alimentação" com saldo de R$ 1.000,00
When ele registra uma transação de R$ 200,00 nessa categoria
Then o sistema deve salvar a transação com sucesso
And o current_balance da categoria deve ser reduzido para R$ 800,00
```

### Scenario: Excluir transação restaura o saldo da categoria
```gherkin
Given que o usuário possui a categoria "Alimentação" com saldo de R$ 800,00
And possui uma transação de R$ 200,00 vinculada a essa categoria
When ele exclui a transação
Then o sistema deve remover a transação
And o current_balance da categoria deve ser restaurado para R$ 1.000,00
```

### Scenario: Atualizar valor de transação ajusta o saldo da categoria
```gherkin
Given que o usuário possui a categoria "Alimentação" com saldo de R$ 800,00
And possui uma transação de R$ 200,00 vinculada a essa categoria
When ele altera o valor da transação para R$ 300,00
Then o sistema deve atualizar a transação
And o current_balance da categoria deve ser ajustado para R$ 700,00
```

### Scenario: Bloquear transação com saldo insuficiente (bloqueio ativado)
```gherkin
Given que o usuário possui a configuração "Bloquear saldo negativo" ativada
And a categoria "Saúde" possui saldo de R$ 30,00
When ele tenta registrar uma transação de R$ 150,00 na categoria "Saúde"
Then o sistema deve retornar erro 422
And informar que o saldo é insuficiente (disponível R$ 30,00, solicitado R$ 150,00)
And não registrar a transação
And não alterar o saldo da categoria
```

### Scenario: Permitir transação com saldo insuficiente (bloqueio desativado)
```gherkin
Given que o usuário possui a configuração "Bloquear saldo negativo" desativada
And a categoria "Lazer" possui saldo de R$ 50,00
When ele registra uma transação de R$ 200,00 na categoria "Lazer"
Then o sistema deve salvar a transação com sucesso
And o current_balance da categoria deve ser reduzido para R$ -150,00
```

---

## Feature: Chat — Registro de gastos via linguagem natural

### Scenario: Registrar gasto via mensagem de texto
```gherkin
Given que o usuário está autenticado
And possui ao menos uma categoria cadastrada
When ele envia a mensagem "gastei 80 reais no mercado" para o chat
Then o sistema deve extrair categoria, descrição e valor da mensagem
And criar a transação vinculada à categoria correta
And reduzir o saldo da categoria pelo valor informado
And retornar a transação criada junto com uma confirmação em linguagem natural
```

### Scenario: Mensagem sem informações suficientes
```gherkin
Given que o usuário está autenticado
And possui ao menos uma categoria cadastrada
When ele envia uma mensagem incompleta como "gastei no mercado" (sem valor)
Then o sistema não deve criar nenhuma transação
And deve retornar uma resposta em português pedindo as informações que faltam
```

### Scenario: Categoria mencionada não existe (match estrito pelo servidor)
```gherkin
Given que o usuário possui apenas a categoria "Débito"
When ele envia a mensagem "Crédito 100 Corte de cabelo"
Then o sistema não deve criar nenhuma transação
And deve retornar mensagem informando que a categoria "Crédito" não foi encontrada
And deve listar as categorias disponíveis do usuário
```

### Scenario: Chat sem categorias cadastradas
```gherkin
Given que o usuário está autenticado
And não possui nenhuma categoria cadastrada
When ele envia qualquer mensagem para o chat
Then o sistema não deve criar transação
And deve orientar o usuário a criar uma categoria primeiro
```

---

## Feature: Reset mensal automático de saldos

### Scenario: Reset automático no primeiro acesso do mês
```gherkin
Given que o usuário possui categorias com saldos do mês anterior
And a configuração "Reset mensal automático" está ativada
And é o primeiro acesso do usuário no novo mês
When ele acessa qualquer tela do app
Then o sistema deve identificar que o mês mudou (lazy reset)
And salvar um snapshot do mês anterior em category_monthly_snapshots
And resetar o current_balance de todas as categorias para o respectivo initial_amount
```

### Scenario: Sem reset quando a configuração está desativada
```gherkin
Given que a configuração "Reset mensal automático" está desativada
When o usuário acessa o app em um novo mês
Then o sistema não deve resetar os saldos das categorias
And os saldos devem continuar acumulando do mês anterior
```

---

## Feature: Configurações do usuário

### Scenario: Editar nome do perfil
```gherkin
Given que o usuário está na tela Configurações
When ele altera o nome no campo "Seu nome"
And clica em "Salvar alterações 💾"
Then o sistema deve atualizar o nome do usuário no banco de dados
And refletir o novo nome na saudação da tela Início
And atualizar o avatar com as iniciais do novo nome
```

### Scenario: Tentativa de alterar e-mail
```gherkin
Given que o usuário está na tela Configurações
Then o campo de e-mail deve estar desabilitado para edição
And exibir a mensagem "O e-mail não pode ser alterado"
```

### Scenario: Consultar configurações do usuário
```gherkin
Given que o usuário está autenticado
When ele acessa GET /api/settings/
Then o sistema deve retornar as configurações atuais do usuário
And incluir os campos: alert_low_balance, monthly_reset, block_negative_balance
```

### Scenario: Ativar/desativar notificação de saldo crítico
```gherkin
Given que o usuário está autenticado
When ele envia PATCH /api/settings/ com {"alert_low_balance": false}
Then o sistema deve salvar a nova preferência
And retornar as configurações atualizadas
```

### Scenario: Ativar/desativar reset mensal automático
```gherkin
Given que o usuário está autenticado
When ele envia PATCH /api/settings/ com {"monthly_reset": false}
Then o sistema deve salvar a nova preferência
And retornar as configurações atualizadas
```

### Scenario: Ativar/desativar bloqueio de saldo negativo
```gherkin
Given que o usuário está autenticado
When ele envia PATCH /api/settings/ com {"block_negative_balance": true}
Then o sistema deve salvar a nova preferência
And aplicá-la imediatamente ao tentar registrar gastos acima do saldo
```

### Scenario: Fazer logout
```gherkin
Given que o usuário está autenticado
And acessa a tela Configurações
When ele clica em "Sair da conta 👋"
Then o sistema deve invalidar o JWT da sessão atual
And limpar os dados de autenticação do frontend (Pinia)
And redirecionar o usuário para a tela de login
```

### Scenario: Limpar todos os dados
```gherkin
Given que o usuário está na tela Configurações
When ele clica em "Limpar todos os dados"
And confirma a ação na caixa de diálogo
Then o sistema deve excluir todas as categorias e lançamentos do usuário
And manter apenas o cadastro do usuário (e-mail e nome)
And redirecionar para a tela Início com estado zerado
```

---

## Feature: Navegação entre telas

### Scenario: Navegar pela bottom navigation bar (mobile)
```gherkin
Given que o usuário está autenticado em qualquer tela
When ele toca em um dos ícones da barra de navegação inferior
  | ícone   | tela destino  |
  | 🏠      | Início        |
  | 📂      | Categorias    |
  | 💬 (FAB)| Chat          |
  | 📊      | Resumo        |
  | ⚙️      | Configurações |
Then o sistema deve navegar para a tela correspondente
And destacar o ícone da tela ativa na barra de navegação
```

### Scenario: Navegar pelo sidebar (desktop)
```gherkin
Given que o usuário está autenticado na versão desktop
When ele clica em um item da sidebar de navegação lateral
Then o sistema deve exibir a tela correspondente na área de conteúdo principal
And destacar o item ativo na sidebar
```

### Scenario: Acesso direto ao chat pelo botão flutuante (FAB)
```gherkin
Given que o usuário está em qualquer tela
When ele toca no botão central da bottom nav (botão flutuante de chat)
Then o sistema deve navegar diretamente para a tela Chat
E focar automaticamente no campo de entrada de mensagem
```
