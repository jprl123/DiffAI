# Gabarito — Testes 46 a 50 (pares v1/v2 para validação do Summary)

**Uso.** Cada par `v1`/`v2` foi gerado com alterações **controladas**. Rode cada par no Compare Docs e confira o *Summary of Changes* contra a tabela consolidada abaixo. As diffs foram verificadas com `pdftotext -layout`: v1 e v2 diferem **apenas** nas alterações listadas — nada acidental.

**Modelo de contagem (o mesmo do Summary do app).** Só existem três categorias: **Inserções**, **Exclusões** e **Movimentações**, e `Total = Inserções + Exclusões + Movimentações`. Regras:

- Cada trecho contíguo **inserido** (cláusula nova, linha de tabela nova) = **1 inserção**.
- Cada trecho contíguo **excluído** (cláusula removida, linha de tabela removida) = **1 exclusão**.
- Cada **modificação** (um valor/palavra trocado por outro) conta como **1 exclusão + 1 inserção** (não há campo "Modificações").
- Cada **bloco movido** (mesmo texto, posição diferente) = **1 movimentação** (contar 1 por bloco, não por parágrafo).

> Observação de projeto: as movimentações foram feitas com **texto idêntico** ao original, apenas reposicionado — o comparador deve marcá-las como movimento (verde), não como exclusão + inserção. Se aparecerem como del+ins, é bug de detecção de movimento, não erro do gabarito.

## Tabela consolidada

| Teste | Tipo | Inserções | Exclusões | Movimentações | **Total** |
|---|---|:--:|:--:|:--:|:--:|
| Teste 46 | Contrato de Prestação de Serviços de Consultoria Empresarial | 4 | 3 | 1 | **8** |
| Teste 47 | Contrato de Licenciamento de Uso de Software | 4 | 4 | 0 | **8** |
| Teste 48 | Contrato de Locação de Imóvel Comercial | 3 | 3 | 1 | **7** |
| Teste 49 | Contrato de Fornecimento de Materiais | 5 | 3 | 1 | **9** |
| Teste 50 | Acordo de Confidencialidade (NDA) | 2 | 2 | 1 | **5** |
| **Soma** | — | **18** | **15** | **4** | **37** |

---

## Teste 46 — Contrato de Prestação de Serviços de Consultoria Empresarial

- **Arquivo base:** `v1/Teste_46_Consultoria_v1.pdf`
- **Arquivo revisado:** `v2/Teste_46_Consultoria_v2.pdf`

**Alterações realizadas:**

| # | Tipo | Descrição | Conta como |
|---|---|---|---|
| 1 | modificação | valor mensal 5.1: R$ 45.000,00 → R$ 52.000,00 | 1 exclusão + 1 inserção |
| 2 | modificação | reajuste 6.1: 6% → 9% | 1 exclusão + 1 inserção |
| 3 | inserção | nova cláusula 10-A (Não Concorrência e Não Aliciamento) | 1 inserção |
| 4 | exclusão | cláusula 15 (Responsabilidade e Seguro) removida | 1 exclusão |
| 5 | movimentação | cláusula 19 (Comunicações) movida para logo após a 2 (Objeto) | 1 movimentação |
| 6 | inserção | nova linha na tabela de parcelas (parcela 5) | 1 inserção |

**Summary esperado:**

```
Arquivo base        Teste_46_Consultoria_v1.pdf
Arquivo revisado    Teste_46_Consultoria_v2.pdf
Total de alterações 8
Inserções           4
Exclusões           3
Movimentações       1
```

---

## Teste 47 — Contrato de Licenciamento de Uso de Software

- **Arquivo base:** `v1/Teste_47_Licenciamento_v1.pdf`
- **Arquivo revisado:** `v2/Teste_47_Licenciamento_v2.pdf`

**Alterações realizadas:**

| # | Tipo | Descrição | Conta como |
|---|---|---|---|
| 1 | modificação | objeto 2.1: 50 → 75 licenças nomeadas | 1 exclusão + 1 inserção |
| 2 | modificação | vigência 3.1: 24 → 36 meses | 1 exclusão + 1 inserção |
| 3 | modificação | tabela SLA: Disponibilidade 99,5% → 99,9% | 1 exclusão + 1 inserção |
| 4 | inserção | nova cláusula 12-A (Auditoria e Compliance) | 1 inserção |
| 5 | exclusão | cláusula 10 (Subcontratação) removida | 1 exclusão |

**Summary esperado:**

```
Arquivo base        Teste_47_Licenciamento_v1.pdf
Arquivo revisado    Teste_47_Licenciamento_v2.pdf
Total de alterações 8
Inserções           4
Exclusões           4
Movimentações       0
```

---

## Teste 48 — Contrato de Locação de Imóvel Comercial

- **Arquivo base:** `v1/Teste_48_Locacao_v1.pdf`
- **Arquivo revisado:** `v2/Teste_48_Locacao_v2.pdf`

**Alterações realizadas:**

| # | Tipo | Descrição | Conta como |
|---|---|---|---|
| 1 | modificação | aluguel 5.1: R$ 12.000,00 → R$ 14.500,00 | 1 exclusão + 1 inserção |
| 2 | inserção | nova cláusula 2-A (Vistoria do Imóvel) | 1 inserção |
| 3 | inserção | nova cláusula 17-A (Multa Moratória) | 1 inserção |
| 4 | exclusão | cláusula 14 (Propriedade Intelectual) removida | 1 exclusão |
| 5 | movimentação | cláusula 21 (Foro) movida para logo após a 10 (Subcontratação) | 1 movimentação |
| 6 | exclusão | linha M4 removida da tabela de cronograma | 1 exclusão |

**Summary esperado:**

```
Arquivo base        Teste_48_Locacao_v1.pdf
Arquivo revisado    Teste_48_Locacao_v2.pdf
Total de alterações 7
Inserções           3
Exclusões           3
Movimentações       1
```

---

## Teste 49 — Contrato de Fornecimento de Materiais

- **Arquivo base:** `v1/Teste_49_Fornecimento_v1.pdf`
- **Arquivo revisado:** `v2/Teste_49_Fornecimento_v2.pdf`

**Alterações realizadas:**

| # | Tipo | Descrição | Conta como |
|---|---|---|---|
| 1 | modificação | objeto 2.1: entrega 15 → 10 dias úteis | 1 exclusão + 1 inserção |
| 2 | modificação | valor 5.1: R$ 38.000,00 → R$ 41.500,00 | 1 exclusão + 1 inserção |
| 3 | modificação | 5.3: multa por atraso 2% → 3% | 1 exclusão + 1 inserção |
| 4 | movimentação | cláusula 18 (Força Maior) movida para logo após a 10 (Subcontratação) | 1 movimentação |
| 5 | inserção | nova linha na tabela de parcelas (parcela 5) | 1 inserção |
| 6 | inserção | nova cláusula 10-A (Devolução e Troca) | 1 inserção |

**Summary esperado:**

```
Arquivo base        Teste_49_Fornecimento_v1.pdf
Arquivo revisado    Teste_49_Fornecimento_v2.pdf
Total de alterações 9
Inserções           5
Exclusões           3
Movimentações       1
```

---

## Teste 50 — Acordo de Confidencialidade (NDA)

- **Arquivo base:** `v1/Teste_50_NDA_v1.pdf`
- **Arquivo revisado:** `v2/Teste_50_NDA_v2.pdf`

**Alterações realizadas:**

| # | Tipo | Descrição | Conta como |
|---|---|---|---|
| 1 | modificação | 11.2: sigilo subsistirá por 5 → 7 anos | 1 exclusão + 1 inserção |
| 2 | exclusão | cláusula 13 (Anticorrupção) removida | 1 exclusão |
| 3 | inserção | nova cláusula 11-A (Exceções à Confidencialidade) | 1 inserção |
| 4 | movimentação | cláusula 3 (Prazo de Vigência) movida para logo após a 12 (Proteção de Dados) | 1 movimentação |

**Summary esperado:**

```
Arquivo base        Teste_50_NDA_v1.pdf
Arquivo revisado    Teste_50_NDA_v2.pdf
Total de alterações 5
Inserções           2
Exclusões           2
Movimentações       1
```
