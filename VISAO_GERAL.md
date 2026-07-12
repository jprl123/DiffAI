# Visão Geral da Ideia

## O que é

Uma ferramenta para **comparar documentos** e gerar **PDFs com marcação de alterações** (redlines). Serve profissionais que precisam entender, de forma rápida e confiável, o que mudou entre uma versão de referência e uma versão revisada — contratos, pareceres, relatórios, políticas, propostas e documentos similares.

A ideia é simples: o usuário indica a versão original e a versão atualizada, e o sistema devolve um resultado padronizado, pronto para revisão, arquivamento ou compartilhamento.

---

## Problema que resolve

No dia a dia jurídico, corporativo e de consultoria, é comum receber muitos documentos revisados e precisar:

- ver exatamente o que mudou entre duas versões;
- gerar um PDF legível com inserções, deleções e movimentações visíveis;
- fazer isso em volume, com consistência de formato;
- ter um resumo objetivo das mudanças, não só o texto marcado.

A ferramenta existe para tirar esse trabalho repetitivo das mãos do usuário e entregar uma saída sempre no mesmo padrão.

---

## Público-alvo

- Advogados e equipes jurídicas
- Consultorias e escritórios que revisam documentos em volume
- Times internos que acompanham versões de contratos, políticas e relatórios
- Qualquer profissional que precise de comparação confiável de documentos com saída em redline

---

## Proposta de valor

| Benefício | Descrição |
|-----------|-----------|
| **Confiabilidade** | Comparação precisa entre versões, com detecção de inserções, deleções e movimentações |
| **Produtividade** | Um par de arquivos ou um lote inteiro, no mesmo fluxo |
| **Padronização** | Resultados com nomenclatura e apresentação consistentes |
| **Clareza** | Alterações exibidas de forma limpa e legível no documento final |
| **Resumo automático** | Cada comparação inclui estatísticas e indicação das páginas alteradas |
| **Flexibilidade** | Aceita diferentes formatos de entrada; exporta PDF completo ou só o que mudou |

---

## Essência do produto

O produto parte de três pilares:

**Entrada** — uma versão base (referência) e uma versão de comparação (revisada), seja como arquivos individuais ou como conjuntos organizados em pastas.

**Processamento** — o sistema identifica as diferenças, organiza as alterações de forma visual e consolida um resumo das mudanças. A forma exata de fazer isso fica em aberto: o que importa é a qualidade e a consistência do resultado, não o mecanismo interno.

**Saída** — PDFs redline padronizados, com opção de exportar também em formato editável e de filtrar apenas as páginas que contêm alterações.

O resultado não é só um diff técnico: é um documento profissional, pronto para ser lido por quem precisa tomar decisão sobre o que mudou.

---

## Duas leituras da mesma comparação

Há dois jeitos complementares de entregar valor — e a ferramenta pode abraçar os dois sem escolher um como “o certo”:

**Documento marcado** — o usuário recebe o texto como se estivesse lendo o documento revisado, com as alterações visíveis no fluxo da leitura. É o formato natural para revisão contratual, aprovação e circulação interna.

**Relatório analítico** — em vez de (ou além de) marcar o documento, o sistema organiza as mudanças em uma visão estruturada: o que mudou, onde mudou, que tipo de mudança foi, lado a lado quando fizer sentido. É o formato natural para auditoria, compliance, anexar em e-mail ou ticket, e para quem precisa filtrar ruído e focar no substantivo.

Não são concorrentes. Um advogado pode querer o PDF redline para assinar; um analista de compliance pode querer a planilha com só as mudanças de conteúdo. A mesma comparação pode alimentar as duas saídas.

---

## Insights da visão analítica

Estes são os princípios que orientam a parte de relatório estruturado — sem amarrar implementação nem formato final:

**Separar ruído de sinal.** Muitas alterações em documentos corporativos são rotineiras: versão do documento, data, numeração de páginas, ajustes de espaçamento. Tratá-las como categoria própria — distinta de mudança de conteúdo — deixa o relatório muito mais útil do que marcar tudo com o mesmo peso.

**Classificar, não só contar.** Inserção, deleção e movimentação são o mínimo. O diferencial está em ir além: adição significativa, remoção significativa, alteração de formatação, reordenação, atualização de metadados, mudança de conteúdo substantivo. O usuário consegue filtrar “mostre só o que importa”.

**Contexto de seção.** Uma mudança isolada perde sentido. Saber que algo mudou em *“2. Resultados Financeiros > 2.1 Receita”* muda completamente a leitura. A hierarquia do documento deve acompanhar cada alteração no relatório.

**Alinhamento inteligente.** Parágrafos que se moveram de lugar, blocos reordenados, tabelas com linhas trocadas — o sistema precisa reconhecer que é o mesmo conteúdo em outra posição, não uma deleção seguida de inserção. Isso vale tanto para o documento marcado quanto para o relatório.

**Tabelas e imagens como cidadãos de primeira classe.** Mudança em célula, linha inserida ou removida, imagem trocada com o mesmo nome — tudo isso entra no mapa de alterações, não só texto corrido.

**Múltiplas abas ou visões no relatório.** Comparação completa para arquivo; só mudanças para revisão rápida; tabelas e imagens em seções próprias; estatísticas consolidadas no fim. O usuário escolhe o recorte.

**Saídas exportáveis para o ecossistema do usuário.** Planilha para quem vive no Excel, HTML interativo para arquivar e filtrar localmente, JSON para integração com outros sistemas. O relatório não precisa ficar preso à interface.

**Descrição em linguagem de negócio (futuro).** Uma mudança numérica ou técnica pode ganhar uma linha legível para executivos — “aumento de 10% na projeção de receita” em vez de só o par de valores. Opcional, premium, mas transforma relatório em síntese.

---

## Modos de uso

**Múltiplos arquivos** — o usuário aponta duas pastas (base e revisada). O sistema encontra os pares correspondentes e processa tudo de uma vez. Ideal para pacotes de contratos, anexos ou lotes de documentos.

**Arquivo único** — o usuário escolhe dois arquivos específicos, sem exigir que tenham o mesmo nome. Ideal para comparações pontuais e rápidas.

Em ambos os modos, é possível inverter base e comparação com um clique, caso a seleção tenha sido feita na ordem errada.

---

## O que o usuário recebe

- **PDF redline** com prefixo `[Redline]` — documento com todas as alterações marcadas
- **Variante enxuta** `[Redline-Changed Pages]` — somente as páginas que contêm mudanças, quando essa opção estiver ativa
- **DOCX opcional** — versão editável do resultado, quando necessário
- **Relatório estruturado opcional** — visão tabular ou exportável das mudanças, com filtros e estatísticas
- **Resumo da execução** — totais, tempo, sucessos e falhas
- **Página de síntese** — ao final de cada comparação, uma tabela com data, contagem de alterações e páginas afetadas

---

## Opções de exportação

| Opção | Ideia |
|-------|-------|
| **PDF completo** | Todo o documento com marcações e resumo |
| **Só páginas alteradas** | Apenas o que mudou, mais a página de resumo |
| **Com ou sem DOCX** | PDF apenas, ou PDF + versão editável |
| **Relatório analítico** | Mudanças organizadas por tipo, seção e status — para auditoria e arquivo |

---

## Interface

A experiência precisa ser **moderna** — limpa, responsiva, com feedback claro e pouca fricção entre “escolhi os arquivos” e “tenho o resultado”. Não estamos presos a um formato de entrega específico para a interface: o importante é que pareça ferramenta profissional atual, não utilitário legado.

Direção desejada:

- poucos cliques no fluxo principal;
- progresso visível em lotes grandes;
- troca rápida entre base e comparação;
- tema claro/escuro;
- campos com estado visual (preenchido, pendente, erro);
- visualização das mudanças com filtros e contexto de seção;
- abertura imediata dos arquivos gerados;
- guia de uso integrado, sem manual externo.

Se um arquivo falhar no meio de um lote, o restante continua — e as falhas ficam registradas para correção.

Há espaço para experimentar novas formas de apresentar comparação: visualização lado a lado, cards por tipo de mudança, timeline de alterações por seção. A interface é parte do produto, não só um invólucro.

---

## Formatos de entrada

O produto deve lidar com os formatos mais comuns do mundo documental profissional. Quando necessário, normaliza os arquivos internamente para que a comparação aconteça no mesmo fluxo, independentemente de como o documento chegou. PDF e documentos editáveis entram no mesmo pipeline — sem hierarquia implícita entre eles.

---

## Modelo de licenciamento

Pensado para distribuição comercial:

- ativação por chave de licença
- vinculação a dispositivo
- validação online
- planos com limites de dispositivo e prazo (trial, assinatura, perpétuo)

---

## Princípios de design

1. **Comparação de qualidade** — o diferencial está na precisão e na legibilidade do resultado, não em reinventar o fluxo do usuário.
2. **Redline limpo** — alterações visíveis no texto, sem poluição visual.
3. **Resumo sempre presente** — toda comparação termina com síntese das mudanças.
4. **Duas saídas, um processamento** — documento marcado e relatório analítico podem coexistir a partir da mesma comparação.
5. **Ruído separado de substância** — versão, data e formatação não devem competir com mudança de conteúdo na atenção do usuário.
6. **Lote como fluxo principal** — processar muitos documentos é o caso central; comparação pontual é o atalho.
7. **Saída previsível** — nomenclatura padronizada facilita organização e busca.
8. **Resiliência** — falha isolada não interrompe o lote inteiro.
9. **Feito para profissionais** — velocidade, confiabilidade e pouca fricção.
10. **Interface como produto** — experiência moderna e espaço para inovar na forma de mostrar diferenças.

---

## Casos de uso

**Revisão contratual** — um escritório recebe dezenas de contratos revisados. Coloca originais e revisados em pastas separadas e obtém um PDF redline para cada par, com resumo de alterações.

**Comparação pontual** — um advogado quer ver o que mudou entre duas versões específicas de um contrato. Seleciona os dois arquivos e recebe o resultado em segundos.

**Auditoria de mudanças** — um time de compliance precisa focar só no que mudou em um documento longo. Exporta apenas as páginas alteradas ou o relatório filtrado por tipo de mudança.

**Pacote misto** — alguns arquivos chegam em PDF, outros em formato editável. O sistema trata tudo no mesmo fluxo.

**Anexo formal** — um analista exporta relatório estruturado com mudanças classificadas e contexto de seção para anexar em ticket, e-mail ou dossiê de auditoria.

---

## O que o produto não é

- Não é um editor de documentos
- Não é colaboração em tempo real (tipo revisão simultânea)
- Não substitui a análise do profissional — entrega o mapa visual e analítico das mudanças; a interpretação continua humana
- Não é uma ferramenta genérica de diff de texto — é voltada ao mundo documental profissional
- Não é só gerador de redline — pode ser também ferramenta de análise e auditoria de alterações

---

## Em uma frase

> Transformar a comparação de documentos em um processo automatizado, padronizado e profissional — da seleção de versões ao PDF redline, ao relatório estruturado e ao resumo das alterações.

---

## Glossário

| Termo | Significado |
|-------|-------------|
| **Base** | Documento original ou de referência |
| **Compare** | Documento revisado ou atualizado |
| **Redline** | Documento com marcações visuais de inserção, deleção e movimentação |
| **Summary of Changes** | Resumo final com estatísticas e páginas alteradas |
| **Lote** | Conjunto de comparações executadas em sequência |
| **Changed pages** | Exportação restrita às páginas com alterações detectadas |
| **Relatório analítico** | Visão estruturada das mudanças — por tipo, seção e status — em formato exportável |
| **Ruído / mudança rotineira** | Alterações de versão, data, numeração ou formatação, distintas de mudança de conteúdo |
