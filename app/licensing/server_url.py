"""URL do servidor de licenças embutida no app/executável.

Ordem de resolução (ver client.py): variável de ambiente
COMPAREDOCS_LICENSE_SERVER > esta constante.

PRODUÇÃO: antes de empacotar o executável para distribuição, troque o valor
abaixo pela URL pública do servidor de licenças (HTTPS), ex.:
"https://api.comparedocs.app". O deploy do servidor e a URL definitiva são
tratados no fluxo da Vercel/Cursor — ver docs/VERCEL_CURSOR.md.
"""
from __future__ import annotations

DEFAULT_SERVER_URL = "https://diffai-production.up.railway.app"
