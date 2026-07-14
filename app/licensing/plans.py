"""Catálogo de planos exibido na aba Planos.

Preços e textos são PLACEHOLDERS de lançamento — ajuste aqui (uma fonte só;
a UI busca via GET /api/plans). ``checkout_url`` deve apontar para a página
de compra (Stripe Payment Link, Mercado Pago etc.) quando existir; enquanto
for None a UI mostra o contato de vendas.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

SALES_EMAIL = os.environ.get("COMPAREDOCS_SALES_EMAIL", "vendas@diffai.app")

PLANS: List[Dict[str, Any]] = [
    {
        "id": "trial",
        "name": "Avaliação",
        "price": "Grátis",
        "period": "14 dias",
        "highlight": False,
        "cta": "Começa automaticamente",
        "checkout_url": None,
        "features": [
            "Todas as funções do Pro",
            "Até 25 comparações",
            "Lote com até 5 pares",
            "Sem cartão de crédito",
        ],
    },
    {
        "id": "pro",
        "name": "Pro",
        "price": "R$ 59",
        "period": "/mês por usuário",
        "highlight": True,
        "cta": "Assinar o Pro",
        "checkout_url": os.environ.get("COMPAREDOCS_CHECKOUT_PRO"),
        "features": [
            "Comparações ilimitadas",
            "PDF redline fiel + DOCX editável",
            "Relatórios HTML, Excel e JSON",
            "Lote ilimitado",
            "2 dispositivos por licença",
        ],
    },
    {
        "id": "team",
        "name": "Equipe",
        "price": "R$ 49",
        "period": "/mês por usuário · mín. 5",
        "highlight": False,
        "cta": "Falar com vendas",
        "checkout_url": os.environ.get("COMPAREDOCS_CHECKOUT_TEAM"),
        "features": [
            "Tudo do Pro",
            "5 dispositivos por licença",
            "Chaves gerenciadas para o time",
            "Suporte prioritário",
        ],
    },
]
