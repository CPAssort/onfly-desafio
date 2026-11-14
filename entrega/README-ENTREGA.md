# Entrega — Consolidador de reservas de hotel (Onfly)

## Resumo

O CLI gerava o relatório sem erro de execução, mas com números errados: no arquivo real ele
reportava **200** reservas, **−1393** noites e **R$ 193.218,53**. Os valores corretos são
**300** reservas, **1347** noites e **R$ 396.170,00**.

Encontrei e corrigi **5 defeitos de regra de negócio**. Esses defeitos faziam falhar os 5 testes
fornecidos. Também reforcei o **tratamento de erros de entrada** e a **gravação do relatório**.
Cada correção está em um commit próprio, e os testes fornecidos não foram alterados.

| | Antes | Depois |
|-|-|-|
| `pytest -q` | 5 failed | **30 passed** (5 fornecidos + 25 adicionais) |
| Amostra (`exemplo-validacao.csv`) | 12 reservas, −33 noites, R$ 5.962,41 | 12 reservas, 28 noites, R$ 7.566,00 (igual ao README) |
| Dataset (`reservas_hoteis.csv`) | 200 reservas, −1393 noites, R$ 193.218,53 | 300 reservas, 1347 noites, R$ 396.170,00 |

## Defeitos corrigidos

### Defeitos de regra de negócio (causa das falhas nos testes fornecidos)

| # | Arquivo | Defeito | Causa raiz | Commit |
|-|-|-|-|-|
| 1 | `repositories/csv_reservation_repository.py` | Só as primeiras 200 reservas eram lidas | Um `if len(rows) == 200: break` encerrava a leitura e descartava o restante do arquivo sem aviso. | `1d9fc60` |
| 2 | `services/currency_converter.py` | Valores em USD/EUR convertidos errado e com imprecisão | A conversão **dividia** pela taxa em vez de multiplicar e passava por `float`, contrariando a regra de usar só `Decimal`. | `7840ba0` |
| 3 | `services/status_policy.py` | `NO_SHOW` entrava em noites, valores, `by_month` e `top_hotels` | A regra excluía apenas `CANCELLED` (`status != "CANCELLED"`) em vez de aceitar apenas `CONFIRMED`. | `f1533c8` |
| 4 | `services/stay_calculator.py` | Noites negativas ou zeradas quando a estadia muda de mês ou de ano | A conta subtraía o **dia do mês** (`checkout.day - checkin.day`) em vez da diferença entre as datas. | `12bd091` |
| 5 | `services/report_builder.py` | `top_hotels` listava os hotéis de **menor** faturamento | A ordenação usava a chave `(total, hotel_id)` em ordem crescente, sem inverter o total. | `db9418e` |

**Detalhes das correções:**

- **#1:** o arquivo passou a ser lido inteiro.
- **#2:** passou a ser `amount * rate`, só com `Decimal`. O arredondamento continua acontecendo
  apenas na serialização.
- **#3:** a regra virou uma lista positiva: `status == "CONFIRMED"`. As contagens por status não
  mudam, porque acontecem antes do filtro.
- **#4:** passou a ser `(checkout - checkin).days * rooms`, exatamente a fórmula do README.
- **#5:** a chave passou a ser `(-total, hotel_id)`. Não usei `reverse=True` porque ele também
  inverteria o desempate, que precisa ser por `hotel_id` ascendente.

### Robustez e tratamento de erros (além dos testes fornecidos)

O README define o código de saída `2` para entrada inválida e `1` para erro inesperado. Várias
entradas ruins escapavam como traceback com código `1`, ou passavam em silêncio e corrompiam os
totais.

| # | Arquivo | Defeito | Causa raiz | Commit |
|-|-|-|-|-|
| 6 | `csv_reservation_repository.py` | Arquivo fora de UTF-8 saía com código 1; CSV com BOM (Excel) era recusado | `UnicodeDecodeError` não é `OSError` e escapava do `except`; o `encoding="utf-8"` mantinha o BOM no nome da primeira coluna. | `1d9fc60` |
| 7 | `currency_converter.py` | Moeda sem taxa derrubava o CLI com `KeyError` (código 1) | O código acessava `rates[currency]` sem tratar a ausência da moeda. | `7840ba0` |
| 8 | `repositories/csv_rate_repository.py` | Taxa `NaN` saía com código 1, `Infinity` era aceita e moeda duplicada era sobrescrita | A comparação `rate <= 0` lança erro com `NaN` e aceita `Infinity`, e não havia checagem de duplicatas. | `fcc8576` |
| 9 | `services/row_parser.py` | `amount` `NaN`, `rooms` < 1 e check-out ≤ check-in passavam; `usd` e `confirmed` em minúsculas não eram reconhecidos | O parser só convertia os tipos, sem validar valores, e não normalizava maiúsculas como a tabela de câmbio já fazia. | `847f562` |
| 10 | `cli.py` | Uma interrupção, ou duas execuções no mesmo `--output`, podia deixar o JSON truncado | O `write_text` gravava direto no arquivo de destino. | `80aef03` |

**Como cada um foi resolvido:**

- **#6:** a leitura passou a usar `utf-8-sig`, e o `UnicodeDecodeError` vira `InputFileError`.
- **#7:** a moeda sem taxa vira `InputFileError` (código 2), com a moeda na mensagem.
- **#8:** a taxa precisa ser finita (`is_finite()`) e positiva, e moedas duplicadas são
  rejeitadas.
- **#9:** os valores são validados e os erros saem com código 2, citando o número da linha.
  Confirmei antes que nenhuma das 312 linhas de `data/` viola essas regras.
- **#10:** o relatório é gravado em um arquivo temporário na mesma pasta e trocado de uma vez com
  `os.replace`, que é uma operação atômica.

## Como investiguei

1. **Verificação do material recebido.** Antes de executar qualquer coisa, inspecionei o zip.
   - Todos os arquivos são texto (Python, CSV, Markdown); não há binários nem scripts de shell.
   - Não há caracteres Unicode invisíveis ou bidirecionais.
   - Não há chamadas perigosas no código (`eval`, `exec`, rede); o único `subprocess` é o do
     `tests/helpers.py`, que roda o próprio CLI.
   - As dependências de desenvolvimento são conhecidas e com versão fixa.
2. **Ambiente.**
   - Extraí o projeto no WSL (Ubuntu 24.04) e criei o `.venv` com o `requirements-dev.txt`.
   - Removi os arquivos `*:Zone.Identifier` criados pelo Windows na extração.
   - Versionei o projeto original como primeiro commit (`cf7928b`).
3. **Reprodução.** Rodei o `pytest -q` (5 falhas, como o README prevê) e o CLI na amostra. O
   resultado com −33 noites e total divergente apontou de cara para os cálculos de noites e de
   câmbio.
4. **Revisão contra o README.** Li cada módulo comparando com as regras: status, noites, câmbio,
   exatidão, ordenação e códigos de saída. Também procurei casos de borda: encoding, BOM,
   `NaN`/`Infinity`, datas invertidas, moeda ausente e gravação concorrente.
5. **Teste antes da correção.**
   - Para cada problema, escrevi primeiro um teste unitário em `tests/test_review_bugs.py` que
     falhava no código original, comprovando o defeito: 22 falhas e 3 testes de proteção passando
     (commit `77a551a`).
   - Os testes chamam os módulos direto, sem `subprocess`, para isolar a causa.
   - Alguns testes protegem contra correções ingênuas: o `test_g2` pega o `reverse=True` no
     ranking, o `test_c2_..._without_float` pega quem trocar `/` por `*` mas mantiver o `float`, e
     o `test_g1` pega quem arredondar antes da serialização.
6. **Correção incremental.** Apliquei uma correção por vez. Em cada etapa, rodei os testes daquela
   etapa (falhando antes, passando depois) e a suíte completa (para garantir que nada regrediu), e
   fiz um commit separado.
7. **Conferência independente.** Recalculei o resumo do dataset real com um script separado, sem
   usar o pacote, e ele bateu campo a campo com o relatório gerado.

## Como validar

Requisitos: Python 3.11+.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Testes: 5 fornecidos + 25 adicionais
pytest -q

# Amostra do README
PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json

# Dataset completo
PYTHONPATH=src python -m onfly_report \
  --input data/reservas_hoteis.csv \
  --rates data/taxas_cambio.csv \
  --output output/report.json
```

Saídas esperadas no stdout:

```
Reservas: 12 | Confirmadas: 9 | Noites: 28 | Total BRL: 7566.00
Reservas: 300 | Confirmadas: 235 | Noites: 1347 | Total BRL: 396170.00
```

O `output/exemplo.json` reproduz exatamente as três tabelas da seção "Amostra de validação" do
README: resumo, `by_month` e `top_hotels`.

Resumo esperado em `output/report.json`:

| Campo | Valor |
|-|-|
| `total_reservations` | 300 |
| `confirmed_reservations` | 235 |
| `cancelled_reservations` | 31 |
| `no_show_reservations` | 34 |
| `total_room_nights` | 1347 |
| `total_amount_brl` | 396170.00 |
| `average_nightly_rate_brl` | 294.11 |

Códigos de saída: arquivo inexistente ou `--top 0` retornam `2`.

## Resultado do `pytest`

```
$ pytest -q
..............................                                           [100%]
30 passed in 0.37s
```

Validado com Python 3.12.3 (WSL, Ubuntu 24.04) e Python 3.11.18. `ruff check .` sem apontamentos.

| Arquivo | Testes | Origem |
|-|-|-|
| `test_currency.py`, `test_nights.py`, `test_regression_report.py`, `test_status_rules.py`, `test_top_hotels.py` | 5 | fornecidos, **inalterados** |
| `test_review_bugs.py` | 25 | adicionados: um teste por defeito, regressão da amostra do README e proteções |

## Decisões e premissas

- **Normalização de `status` e `currency`.** O README não pede, mas a tabela de câmbio já
  normalizava as moedas para maiúsculas e o parser de reservas não. Alinhei os dois para que `usd`
  ou `confirmed` não virem moeda sem taxa ou status ignorado. Os dados fornecidos já vêm em
  maiúsculas, então os totais não mudam.
- **Validações novas.** O README afirma que os dados são consistentes. As validações (check-out
  posterior ao check-in, `rooms` ≥ 1, valores finitos) não alteram nenhum resultado do dataset;
  elas apenas fazem uma entrada corrompida falhar com código `2` e o número da linha, em vez de
  gerar totais silenciosamente errados.
- **Valores negativos de `amount`.** Não são rejeitados: não há regra no README, e um valor
  negativo pode representar um estorno legítimo.
- **Contrato preservado.** Comando, argumentos, schema e semântica do relatório não mudaram, assim
  como `data/reservas_hoteis.csv`, `data/taxas_cambio.csv` e os testes fornecidos.

## Uso de IA

Usei IA neste desafio. A exportação da sessão está em `entrega/uso-de-ia/sessao.md`, e a
declaração (ferramenta, modelo e divisão do trabalho) está em `entrega/uso-de-ia/declaracao.md`.
