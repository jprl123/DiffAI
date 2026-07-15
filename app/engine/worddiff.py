"""Diff palavra a palavra preservando formatação dos runs.

Após o SequenceMatcher, um passo de coalescência absorve pontes ``equal``
curtas entre edições (ex.: só as pontas mudam ao envolver uma frase em
``[...]``). Sem isso, palavras comuns no meio viram âncoras LCS e o redline
parece “palavras soltas” — o Word Compare trata o trecho como um replace
contíguo.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from app.models import Fragment, Run

_TOKEN_RE = re.compile(r"\S+|\s+")

# Máximo de palavras (não-espaço) numa ponte equal absorvida entre edições.
# REGRA DO PRODUTO (definida pelo usuário em 2026-07-12, prevalece sobre
# imitar o agrupamento do Word Compare): nunca apresentar palavra idêntica
# como excluída+reinserida; destacar SOMENTE o efetivamente alterado.
# Pontes de 1-2 palavras ainda são absorvidas (ex.: "de" entre duas edições),
# e o refinamento de caractere + guarda anti-fantasma cuidam do resto.
_BRIDGE_MAX_WORDS = 2

# REGRA DOS 30% (usuário, 2026-07-12): par de palavras com até 30% dos
# caracteres alterados (sobre a maior palavra) ganha marca fina de caractere;
# acima disso, a palavra antiga sai inteira e a nova entra inteira.
_WORD_CHANGE_MAX = 0.30
# Limpeza semântica: ilha "equal" INTERIOR menor que isso é absorvida pelas
# edições vizinhas — sem ela, "operação"→"compra" vira letras soltas (+c +m
# -e -ção…) em vez de uma troca limpa de palavra.
_CHAR_EQUAL_MIN = 3

# Tokens com dígito (valores, percentuais, datas, nºs de cláusula/lei) NUNCA
# recebem marca fina de caractere — a marcação dígito a dígito ("R$ 12.06.500"
# "20256") é ilegível. O token antigo sai inteiro e o novo entra inteiro
# (relatório de QA, testes 01–20). Só afeta números; texto segue a regra 30%.
_DIGIT_RE = re.compile(r"\d")


def _has_digit(text: str) -> bool:
    return bool(_DIGIT_RE.search(text))


Opcode = Tuple[str, int, int, int, int]


@dataclass
class _Token:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False

    def style_key(self) -> str:
        return "%d%d%d%d" % (self.bold, self.italic, self.underline, self.strike)


def _tokenize_runs(runs: List[Run]) -> List[_Token]:
    tokens: List[_Token] = []
    for run in runs or []:
        if not run.text:
            continue
        for part in _TOKEN_RE.findall(run.text):
            tokens.append(
                _Token(
                    text=part,
                    bold=bool(run.bold),
                    italic=bool(run.italic),
                    underline=bool(run.underline),
                    strike=bool(run.strike),
                )
            )
    return tokens


def _token_to_fragment(token: _Token, op: str) -> Fragment:
    return Fragment(
        text=token.text,
        op=op,
        bold=token.bold,
        italic=token.italic,
        underline=token.underline,
        strike=token.strike,
    )


def _merge_fragments(fragments: List[Fragment]) -> List[Fragment]:
    if not fragments:
        return []
    merged: List[Fragment] = [fragments[0]]
    for frag in fragments[1:]:
        prev = merged[-1]
        if (
            prev.op == frag.op
            and prev.bold == frag.bold
            and prev.italic == frag.italic
            and prev.underline == frag.underline
            and prev.strike == frag.strike
        ):
            prev.text += frag.text
        else:
            merged.append(frag)
    return merged


def _non_ws_count(tokens: Sequence[_Token], start: int, end: int) -> int:
    return sum(1 for i in range(start, end) if tokens[i].text.strip())


def _bridge_should_absorb(
    equal_op: Opcode, base_tokens: Sequence[_Token]
) -> bool:
    """True se a ponte equal entre duas edições deve virar parte do replace."""
    _tag, i1, i2, _j1, _j2 = equal_op
    words = _non_ws_count(base_tokens, i1, i2)
    if words == 0:
        return True  # só whitespace
    return words <= _BRIDGE_MAX_WORDS


def _coalesce_opcodes(
    opcodes: Sequence[Opcode], base_tokens: Sequence[_Token]
) -> List[Opcode]:
    """Absorve equals curtos entre edições num único ``replace`` contíguo."""
    ops: List[Opcode] = list(opcodes)
    while True:
        absorbed = False
        out: List[Opcode] = []
        i = 0
        while i < len(ops):
            if (
                i + 2 < len(ops)
                and ops[i][0] != "equal"
                and ops[i + 1][0] == "equal"
                and ops[i + 2][0] != "equal"
                and _bridge_should_absorb(ops[i + 1], base_tokens)
            ):
                left = ops[i]
                right = ops[i + 2]
                merged: Opcode = (
                    "replace",
                    left[1],
                    right[2],
                    left[3],
                    right[4],
                )
                i += 3
                # Encadeia pontes seguintes curtas na mesma região.
                while (
                    i + 1 < len(ops)
                    and ops[i][0] == "equal"
                    and ops[i + 1][0] != "equal"
                    and _bridge_should_absorb(ops[i], base_tokens)
                ):
                    right = ops[i + 1]
                    merged = (
                        "replace",
                        merged[1],
                        right[2],
                        merged[3],
                        right[4],
                    )
                    i += 2
                out.append(merged)
                absorbed = True
            else:
                out.append(ops[i])
                i += 1
        ops = out
        if not absorbed:
            break
    return ops


def formatting_style_diff_runs(
    base_runs: List[Run], compare_runs: List[Run]
) -> List[Fragment]:
    """Marca trechos com formatação alterada (op=format) quando o texto coincide."""
    base_tokens = _tokenize_runs(base_runs)
    compare_tokens = _tokenize_runs(compare_runs)
    if not base_tokens and not compare_tokens:
        return []
    if len(base_tokens) != len(compare_tokens):
        return worddiff_runs(base_runs, compare_runs)
    fragments: List[Fragment] = []
    for bt, ct in zip(base_tokens, compare_tokens):
        if bt.text != ct.text:
            return worddiff_runs(base_runs, compare_runs)
        op = "equal" if bt.style_key() == ct.style_key() else "format"
        fragments.append(_token_to_fragment(ct, op))
    return _merge_fragments(fragments)


def _region_chars(
    tokens: Sequence[_Token], start: int, end: int
) -> Tuple[str, List[_Token]]:
    """Concatena o texto dos tokens [start:end) e mapeia cada char ao token."""
    parts: List[str] = []
    char_tokens: List[_Token] = []
    for idx in range(start, end):
        token = tokens[idx]
        parts.append(token.text)
        char_tokens.extend([token] * len(token.text))
    return "".join(parts), char_tokens


def _char_fragments(
    text: str, char_tokens: List[_Token], lo: int, hi: int, op: str
) -> List[Fragment]:
    frags: List[Fragment] = []
    for pos in range(lo, hi):
        frags.append(_token_to_fragment(char_tokens[pos], op))
        frags[-1].text = text[pos]
    return frags


def _cleanup_char_opcodes(opcodes: List[Opcode]) -> List[Opcode]:
    """Absorve ilhas equal interiores curtas (< _CHAR_EQUAL_MIN) nas edições.

    A primeira e a última opcode equal são preservadas sempre — elas ancoram
    o refinamento ao texto estável em volta (é o que mantém "Luís" e "MA"
    intactos em "Luís-MA"→"Luís/MA").
    """
    if len(opcodes) < 3:
        return list(opcodes)
    out: List[Opcode] = []
    for idx, op in enumerate(opcodes):
        tag, a1, a2, b1, b2 = op
        interior = 0 < idx < len(opcodes) - 1
        is_tiny_equal = tag == "equal" and (a2 - a1) < _CHAR_EQUAL_MIN
        if interior and is_tiny_equal:
            out.append(("replace", a1, a2, b1, b2))
        else:
            out.append(op)
    # Funde não-equals adjacentes num replace contíguo.
    merged: List[Opcode] = []
    for op in out:
        if merged and merged[-1][0] != "equal" and op[0] != "equal":
            prev = merged[-1]
            merged[-1] = ("replace", prev[1], op[2], prev[3], op[4])
        else:
            merged.append(op)
    return merged


@dataclass
class _WordUnit:
    """Palavra + espaços que a seguem (unidade de pareamento)."""
    word: _Token
    spaces: List[_Token]


def _units(tokens: Sequence[_Token], start: int, end: int) -> List[_WordUnit]:
    units: List[_WordUnit] = []
    for idx in range(start, end):
        token = tokens[idx]
        if token.text.strip():
            units.append(_WordUnit(word=token, spaces=[]))
        elif units:
            units[-1].spaces.append(token)
        # espaço antes da primeira palavra da região: irrelevante p/ marcação
    return units


def _word_change_ratio(old_word: str, new_word: str) -> float:
    """Proporção de caracteres alterados em relação à MAIOR palavra."""
    lmax = max(len(old_word), len(new_word))
    if lmax == 0:
        return 0.0
    matcher = difflib.SequenceMatcher(None, old_word, new_word, autojunk=False)
    matched = sum(size for _a, _b, size in matcher.get_matching_blocks())
    return (lmax - matched) / lmax


def _pair_char_fragments(old: _WordUnit, new: _WordUnit) -> List[Fragment]:
    """Marca fina (nível de caractere) para um par de palavras ≤30% alterado."""
    old_text, old_map = _region_chars([old.word], 0, 1)
    new_text, new_map = _region_chars([new.word], 0, 1)
    matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
    opcodes = _cleanup_char_opcodes(matcher.get_opcodes())
    frags: List[Fragment] = []
    for tag, a1, a2, b1, b2 in opcodes:
        if tag == "equal":
            frags.extend(_char_fragments(new_text, new_map, b1, b2, "equal"))
        elif tag == "delete":
            frags.extend(_char_fragments(old_text, old_map, a1, a2, "delete"))
        elif tag == "insert":
            frags.extend(_char_fragments(new_text, new_map, b1, b2, "insert"))
        else:
            frags.extend(_char_fragments(old_text, old_map, a1, a2, "delete"))
            frags.extend(_char_fragments(new_text, new_map, b1, b2, "insert"))
    for space in new.spaces:
        frags.append(_token_to_fragment(space, "equal"))
    return frags


def _unit_fragments(unit: _WordUnit, op: str) -> List[Fragment]:
    frags = [_token_to_fragment(unit.word, op)]
    for space in unit.spaces:
        frags.append(_token_to_fragment(space, op))
    return frags


def _refine_replace(
    base_tokens: Sequence[_Token],
    compare_tokens: Sequence[_Token],
    i1: int, i2: int, j1: int, j2: int,
) -> Optional[List[Fragment]]:
    """CRITÉRIO UNIFORME do produto (usuário, 2026-07-12) para replaces.

    Dentro da região: palavras antigas e novas são pareadas por semelhança,
    usando a regra dos 30% como limiar — par com até 30% dos caracteres
    alterados (proporção sobre a MAIOR palavra) recebe marca FINA de
    caractere; palavra sem par é excluída/inserida POR INTEIRO. Pareamento
    guloso por melhor semelhança, sem cruzamento. Um único critério,
    previsível, aplicado do início ao fim do documento:
    - "Luís-MA"→"Luís/MA" (14%) marca só o hífen;
    - "cool"→"cooler" (33%) e sinônimos: palavra inteira sai e entra;
    - "as a result of"→"resulting from": nenhum par ≤30% → frase antiga
      excluída inteira, nova inserida inteira (nada de letras reaproveitadas).
    """
    old_units = _units(base_tokens, i1, i2)
    new_units = _units(compare_tokens, j1, j2)
    if not old_units or not new_units:
        return None
    if len(old_units) * len(new_units) > 2500:
        return None  # região gigante: replace bruto é mais seguro

    scored = []
    for oi, ou in enumerate(old_units):
        o_num = _has_digit(ou.word.text)
        for ni, nu in enumerate(new_units):
            n_num = _has_digit(nu.word.text)
            if o_num and n_num:
                # Dois números: pareiam por POSIÇÃO (troca inteira, sem char).
                scored.append((0.0, oi, ni))
            elif o_num or n_num:
                continue  # número vs palavra: não pareia → troca inteira
            else:
                ratio = _word_change_ratio(ou.word.text, nu.word.text)
                if ratio <= _WORD_CHANGE_MAX:
                    scored.append((ratio, oi, ni))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))

    pair_of_old: dict = {}
    pair_of_new: dict = {}
    for ratio, oi, ni in scored:
        if oi in pair_of_old or ni in pair_of_new:
            continue
        if any(
            (oi2 - oi) * (ni2 - ni) < 0 for oi2, ni2 in pair_of_old.items()
        ):
            continue  # sem cruzamento
        pair_of_old[oi] = ni
        pair_of_new[ni] = oi

    # Nenhum par: replace inteiro na ordem convencional (delete antigo → insert
    # novo). Devolver None deixa o fallback do worddiff_runs cuidar disso.
    if not pair_of_new:
        return None

    frags: List[Fragment] = []
    next_old = 0
    for ni, nu in enumerate(new_units):
        if ni in pair_of_new:
            oi = pair_of_new[ni]
            # exclusões de palavras antigas que vêm antes do par
            while next_old < oi:
                if next_old not in pair_of_old:
                    frags.extend(_unit_fragments(old_units[next_old], "delete"))
                next_old += 1
            next_old = max(next_old, oi + 1)
            # Par numérico: troca INTEIRA (delete antigo + insert novo), nunca
            # dígito a dígito. Texto: marca fina pela regra dos 30%.
            if _has_digit(old_units[oi].word.text) or _has_digit(nu.word.text):
                frags.extend(_unit_fragments(old_units[oi], "delete"))
                frags.extend(_unit_fragments(nu, "insert"))
            else:
                frags.extend(_pair_char_fragments(old_units[oi], nu))
        else:
            frags.extend(_unit_fragments(nu, "insert"))
    while next_old < len(old_units):
        if next_old not in pair_of_old:
            frags.extend(_unit_fragments(old_units[next_old], "delete"))
        next_old += 1
    return frags


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def worddiff_runs(base_runs: List[Run], compare_runs: List[Run]) -> List[Fragment]:
    """Compara dois conjuntos de runs e retorna fragmentos marcados."""
    base_tokens = _tokenize_runs(base_runs)
    compare_tokens = _tokenize_runs(compare_runs)
    if not base_tokens and not compare_tokens:
        return []
    if not base_tokens:
        return _merge_fragments(
            [_token_to_fragment(t, "insert") for t in compare_tokens]
        )
    if not compare_tokens:
        return _merge_fragments(
            [_token_to_fragment(t, "delete") for t in base_tokens]
        )

    matcher = difflib.SequenceMatcher(
        None,
        [t.text for t in base_tokens],
        [t.text for t in compare_tokens],
        autojunk=False,
    )
    opcodes = _coalesce_opcodes(matcher.get_opcodes(), base_tokens)
    fragments: List[Fragment] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for idx in range(j1, j2):
                fragments.append(_token_to_fragment(compare_tokens[idx], "equal"))
        elif tag == "insert":
            for idx in range(j1, j2):
                fragments.append(_token_to_fragment(compare_tokens[idx], "insert"))
        elif tag == "delete":
            for idx in range(i1, i2):
                fragments.append(_token_to_fragment(base_tokens[idx], "delete"))
        elif tag == "replace":
            old_joined, _ = _region_chars(base_tokens, i1, i2)
            new_joined, _ = _region_chars(compare_tokens, j1, j2)
            # Texto igual (só espaçamento/quebra de run mudou): nada de tachar
            # e reinserir conteúdo idêntico — vira equal.
            if _normalized(old_joined) == _normalized(new_joined):
                for idx in range(j1, j2):
                    fragments.append(_token_to_fragment(compare_tokens[idx], "equal"))
                continue
            refined = _refine_replace(base_tokens, compare_tokens, i1, i2, j1, j2)
            if refined is not None:
                fragments.extend(refined)
                continue
            for idx in range(i1, i2):
                fragments.append(_token_to_fragment(base_tokens[idx], "delete"))
            for idx in range(j1, j2):
                fragments.append(_token_to_fragment(compare_tokens[idx], "insert"))
    return _merge_fragments(fragments)


def runs_have_formatting_diff(base_runs: List[Run], compare_runs: List[Run]) -> bool:
    """True se o texto normalizado é igual mas a formatação difere."""
    base_text = "".join(r.text for r in base_runs or [])
    compare_text = "".join(r.text for r in compare_runs or [])
    if re.sub(r"\s+", " ", base_text).strip() != re.sub(r"\s+", " ", compare_text).strip():
        return False
    base_tokens = _tokenize_runs(base_runs)
    compare_tokens = _tokenize_runs(compare_runs)
    if len(base_tokens) != len(compare_tokens):
        return True
    for bt, ct in zip(base_tokens, compare_tokens):
        if bt.text != ct.text:
            return False
        if bt.style_key() != ct.style_key():
            return True
    return False
