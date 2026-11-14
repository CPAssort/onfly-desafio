# Declaração de uso de IA

## Ferramenta e modelo

- **Ferramenta:** Claude, assistente da Anthropic, usado no app desktop do Claude para Windows.
  Ele foi conectado ao meu computador (acesso à pasta Downloads, leitura da tela do terminal e o
  navegador do próprio app) e tinha um ambiente Linux isolado na nuvem para executar código.
- **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`).
- **Sessão:** uma única conversa em 14/11/2026, das 12h26 às 14h45 (horário de Brasília). O log
  consolidado está em `sessao.md`.

## O que a IA fez

- **Verificação de segurança do zip recebido**, feita antes de qualquer execução:
  - procurou caracteres Unicode invisíveis ou bidirecionais;
  - procurou chamadas perigosas no código e revisou as dependências;
  - procurou injeção de fórmula nos CSVs e instruções escondidas no README.
- **Conferência do ambiente que eu montei.** Leu o histórico do meu terminal WSL e clonou o
  repositório do GitHub para comparar com o zip original.
- **Revisão de código** contra o README, classificando os problemas em crítico, médio e baixo e
  incluindo concorrência e tratamento de erros.
- **Escrita da suíte `tests/test_review_bugs.py`**, com 25 testes: um por defeito, a regressão da
  amostra do README e proteções contra correções ingênuas. A IA rodou a suíte contra o código
  original para provar cada defeito antes de propor a correção.
- **Implementação das 8 correções**, entregues como patches separados (um por commit), com a
  explicação de onde e por que cada mudança foi feita.
- **Validação**, testando cada etapa isoladamente (antes e depois da correção) e no estado final:
  - Python 3.11, `ruff`;
  - amostra do README;
  - recálculo independente do dataset real;
  - códigos de saída.
- **Redação** deste arquivo, do `README-ENTREGA.md` e do log `sessao.md`.

## O que eu fiz

- Baixei o desafio e pedi a verificação de segurança antes de abrir o projeto.
- Montei o ambiente no WSL (Ubuntu 24.04):
  - extraí os arquivos e criei o `.venv`;
  - instalei as dependências;
  - removi os `*:Zone.Identifier` gerados pelo Windows.
- Criei o repositório público no GitHub e configurei a autenticação com `gh auth login`, depois
  que o push com senha foi recusado.
- Direcionei o trabalho:
  - pedi uma revisão rigorosa com testes que provassem cada bug antes da correção;
  - pedi que a implementação fosse feita **por etapas**, para eu verificar cada uma.
- Apliquei cada correção no meu terminal (`git apply`), revisei o `git diff` e rodei os testes da
  etapa e a suíte completa.
- Fiz cada commit e o push.
- Conferi os resultados no meu ambiente (Python 3.12.3): `30 passed`, e as saídas da amostra e do
  dataset iguais às esperadas.
- Revisei os documentos de entrega antes de versioná-los.

## Observações

- A IA não executou comandos no meu terminal: o acesso a ele era só de leitura e clique. Todos os
  `git apply`, `pytest`, commits e o push foram feitos por mim.
- Os testes fornecidos, os dados e o README original não foram alterados.
