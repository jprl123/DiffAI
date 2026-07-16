"""Modelo de dados central do Compare-Docs.

Todos os módulos (extração, motor de comparação, saídas, API) trabalham
sobre estas estruturas. Compatível com Python 3.9.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BlockKind(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    IMAGE = "image"
    LIST_ITEM = "list_item"


class ChangeType(str, Enum):
    EQUAL = "equal"          # bloco idêntico (não gera Change, mas usado em render)
    INSERT = "insert"        # bloco novo no documento revisado
    DELETE = "delete"        # bloco removido do documento base
    MODIFY = "modify"        # bloco presente nos dois, com texto/formatação alterados
    MOVE = "move"            # mesmo conteúdo em outra posição
    MOVE_MODIFY = "move_modify"  # movido E alterado


class Category(str, Enum):
    """Classificação sinal vs. ruído — princípio central do produto."""
    CONTENT = "content"                  # mudança substantiva de conteúdo
    FORMATTING = "formatting"            # mesmo texto, formatação diferente
    NOISE_DATE = "noise_date"            # datas atualizadas
    NOISE_VERSION = "noise_version"      # número/rótulo de versão
    NOISE_PAGENUM = "noise_pagenum"      # numeração de página
    NOISE_WHITESPACE = "noise_whitespace"  # só espaçamento
    NOISE_PUNCT = "noise_punct"          # só pontuação/caixa
    TABLE = "table"                      # mudança estrutural em tabela
    IMAGE = "image"                      # imagem trocada/inserida/removida
    METADATA = "metadata"                # cabeçalho/rodapé/propriedades


NOISE_CATEGORIES = {
    Category.NOISE_DATE,
    Category.NOISE_VERSION,
    Category.NOISE_PAGENUM,
    Category.NOISE_WHITESPACE,
    Category.NOISE_PUNCT,
}


# ---------------------------------------------------------------------------
# Estruturas de documento (saída da extração)
# ---------------------------------------------------------------------------

@dataclass
class Run:
    """Trecho de texto com formatação uniforme."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None

    def style_key(self) -> str:
        return "%d%d%d%d" % (self.bold, self.italic, self.underline, self.strike)


@dataclass
class Cell:
    """Célula de tabela: texto rico."""
    runs: List[Run] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class Block:
    """Unidade de comparação: parágrafo, título, tabela ou imagem."""
    kind: BlockKind
    runs: List[Run] = field(default_factory=list)        # paragraph/heading/list_item
    rows: List[List[Cell]] = field(default_factory=list)  # table
    image_hash: Optional[str] = None                      # image
    level: int = 0                # nível do título (1..9); 0 se não for título
    page: Optional[int] = None    # página de origem (PDF); None em DOCX
    section_path: List[str] = field(default_factory=list)  # ["2. Resultados", "2.1 Receita"]
    index: int = -1               # posição no documento
    style_name: Optional[str] = None
    list_label: Optional[str] = None  # rótulo de numeração automática: "(a)", "6.1.", "iv."
    align: Optional[str] = None   # left | center | right | justify
    indent_left_pt: Optional[float] = None
    indent_right_pt: Optional[float] = None
    indent_first_pt: Optional[float] = None
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None

    @property
    def text(self) -> str:
        if self.kind == BlockKind.TABLE:
            return "\n".join(
                " | ".join(c.text for c in row) for row in self.rows
            )
        return "".join(r.text for r in self.runs)

    def normalized_text(self) -> str:
        """Texto normalizado para matching (espaços colapsados)."""
        return re.sub(r"\s+", " ", self.text).strip()

    def content_hash(self) -> str:
        base = self.normalized_text()
        if self.kind == BlockKind.IMAGE and self.image_hash:
            base = "img:" + self.image_hash
        elif self.list_label:
            # Renumeração é mudança real (regra do produto): o rótulo compõe a
            # identidade do bloco. Composto como "rótulo texto" para bater com
            # PDFs, onde o número impresso já faz parte do texto extraído.
            base = (self.list_label + " " + base).strip()
        return hashlib.sha1(base.encode("utf-8")).hexdigest()


@dataclass
class Document:
    """Documento extraído e normalizado — DOCX e PDF viram a mesma coisa."""
    source_path: str
    fmt: str                      # "docx" | "pdf" | "xlsx"
    blocks: List[Block] = field(default_factory=list)
    page_count: int = 0
    title: str = ""
    default_font: Optional[str] = None
    default_font_size_pt: Optional[float] = None
    # Dimensões da 1ª página (pontos tipográficos). Usadas na pré-visualização
    # e no PDF padronizado para não "cortar" documentos paisagem.
    page_width_pt: Optional[float] = None
    page_height_pt: Optional[float] = None


def assign_section_paths(doc: Document) -> None:
    """Preenche block.section_path com a hierarquia de títulos vigente."""
    stack: List[str] = []      # títulos por nível
    levels: List[int] = []
    for block in doc.blocks:
        # Cabeçalho/rodapé (extraídos ao final do documento) não pertencem à
        # hierarquia de seções do corpo — recebem rótulo próprio.
        if block.style_name == "__header__":
            block.section_path = ["Cabeçalho"]
            continue
        if block.style_name == "__footer__":
            block.section_path = ["Rodapé"]
            continue
        if block.kind == BlockKind.HEADING and block.level > 0:
            while levels and levels[-1] >= block.level:
                levels.pop()
                stack.pop()
            stack.append(block.normalized_text())
            levels.append(block.level)
            block.section_path = list(stack[:-1])
        else:
            block.section_path = list(stack)


# ---------------------------------------------------------------------------
# Estruturas de resultado (saída do motor de comparação)
# ---------------------------------------------------------------------------

@dataclass
class Fragment:
    """Pedaço de texto dentro de um bloco renderizado, com marcação de diff."""
    text: str
    op: str = "equal"             # "equal" | "insert" | "delete" | "format"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None


@dataclass
class CellChange:
    row: int
    col: int
    change_type: ChangeType
    old_text: str = ""
    new_text: str = ""


@dataclass
class Change:
    """Uma alteração detectada — alimenta o relatório analítico."""
    id: int
    change_type: ChangeType
    category: Category
    section_path: List[str] = field(default_factory=list)
    page_base: Optional[int] = None
    page_compare: Optional[int] = None
    old_text: str = ""
    new_text: str = ""
    summary: str = ""             # descrição curta legível
    cell_changes: List[CellChange] = field(default_factory=list)
    moved_from_index: Optional[int] = None
    moved_to_index: Optional[int] = None


@dataclass
class RenderBlock:
    """Bloco do fluxo de saída do redline (ordem do documento revisado,
    com deleções intercaladas na posição alinhada)."""
    kind: BlockKind
    change_type: ChangeType
    category: Optional[Category] = None
    fragments: List[Fragment] = field(default_factory=list)
    rows: List[List[List[Fragment]]] = field(default_factory=list)  # tabela: rows x cols x frags
    row_ops: List[str] = field(default_factory=list)  # por linha: equal|insert|delete|modify
    level: int = 0
    page: Optional[int] = None            # página no doc revisado (ou base p/ deleções)
    section_path: List[str] = field(default_factory=list)
    change_id: Optional[int] = None       # liga ao Change correspondente
    list_label: Optional[str] = None      # rótulo de numeração automática do doc revisado
    style_name: Optional[str] = None
    align: Optional[str] = None
    indent_left_pt: Optional[float] = None
    indent_right_pt: Optional[float] = None
    indent_first_pt: Optional[float] = None
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None


@dataclass
class Stats:
    total_changes: int = 0
    insertions: int = 0
    deletions: int = 0
    modifications: int = 0
    moves: int = 0
    content_changes: int = 0
    formatting_changes: int = 0
    noise_changes: int = 0
    table_changes: int = 0
    image_changes: int = 0
    changed_pages: List[int] = field(default_factory=list)   # páginas afetadas (doc revisado)
    by_category: Dict[str, int] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    base_path: str
    compare_path: str
    base_title: str = ""
    compare_title: str = ""
    changes: List[Change] = field(default_factory=list)
    render_blocks: List[RenderBlock] = field(default_factory=list)
    stats: Stats = field(default_factory=Stats)
    compared_at: str = ""         # ISO timestamp — preenchido pelo orquestrador
    duration_seconds: float = 0.0
    preview_layout: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        def convert(obj: Any) -> Any:
            if isinstance(obj, Enum):
                return obj.value
            if dataclasses.is_dataclass(obj):
                return {k: convert(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert(v) for v in obj]
            return obj
        return convert(self)
