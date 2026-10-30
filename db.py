"""Camada de persistência SQLite para OPs, grade, amarrações e remessas."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parent / "producao.db"

TAMANHOS_PADRAO = [
    ("PP", "padrao", 10),
    ("P", "padrao", 20),
    ("M", "padrao", 30),
    ("G", "padrao", 40),
    ("GG", "padrao", 50),
    ("XGG", "plus_size", 60),
    ("G1", "plus_size", 70),
    ("G2", "plus_size", 80),
    ("G3", "plus_size", 90),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tamanhos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                grupo TEXT NOT NULL CHECK (grupo IN ('padrao', 'plus_size', 'numerico')),
                ordem INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS lotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cor TEXT NOT NULL,
                cor_hex TEXT NOT NULL DEFAULT '#1B4F72',
                op TEXT NOT NULL,
                referencia TEXT NOT NULL,
                descricao TEXT NOT NULL,
                preco_unitario REAL NOT NULL DEFAULT 0,
                valor_total REAL NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS lote_grade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id INTEGER NOT NULL,
                tamanho_id INTEGER NOT NULL,
                qnt_original INTEGER NOT NULL CHECK (qnt_original >= 0),
                UNIQUE (lote_id, tamanho_id),
                FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
                FOREIGN KEY (tamanho_id) REFERENCES tamanhos(id)
            );

            CREATE TABLE IF NOT EXISTS amarracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                lote_id INTEGER NOT NULL,
                tamanho_id INTEGER NOT NULL,
                qtd_1a INTEGER NOT NULL DEFAULT 0 CHECK (qtd_1a >= 0),
                qtd_2a INTEGER NOT NULL DEFAULT 0 CHECK (qtd_2a >= 0),
                observacao TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
                FOREIGN KEY (tamanho_id) REFERENCES tamanhos(id)
            );

            CREATE TABLE IF NOT EXISTS remessas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                numero_romaneio TEXT NOT NULL UNIQUE,
                observacao TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS remessa_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                remessa_id INTEGER NOT NULL,
                lote_id INTEGER NOT NULL,
                tamanho_id INTEGER NOT NULL,
                qtd_1a INTEGER NOT NULL DEFAULT 0 CHECK (qtd_1a >= 0),
                qtd_2a INTEGER NOT NULL DEFAULT 0 CHECK (qtd_2a >= 0),
                FOREIGN KEY (remessa_id) REFERENCES remessas(id) ON DELETE CASCADE,
                FOREIGN KEY (lote_id) REFERENCES lotes(id),
                FOREIGN KEY (tamanho_id) REFERENCES tamanhos(id)
            );

            CREATE INDEX IF NOT EXISTS idx_amarracoes_lote ON amarracoes(lote_id, tamanho_id);
            CREATE INDEX IF NOT EXISTS idx_remessa_itens_lote ON remessa_itens(lote_id, tamanho_id);
            """
        )
        existentes = {
            row["codigo"]
            for row in conn.execute("SELECT codigo FROM tamanhos").fetchall()
        }
        for codigo, grupo, ordem in TAMANHOS_PADRAO:
            if codigo not in existentes:
                conn.execute(
                    "INSERT INTO tamanhos (codigo, grupo, ordem) VALUES (?, ?, ?)",
                    (codigo, grupo, ordem),
                )


def listar_tamanhos(apenas_ativos: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM tamanhos"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY ordem, codigo"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def cadastrar_tamanho(codigo: str, grupo: str, ordem: int | None = None) -> int:
    codigo = codigo.strip().upper()
    if not codigo:
        raise ValueError("Informe o código do tamanho.")
    if grupo not in ("padrao", "plus_size", "numerico"):
        raise ValueError("Grupo de tamanho inválido.")
    if ordem is None:
        if grupo == "numerico":
            try:
                ordem = 1000 + int(codigo)
            except ValueError:
                ordem = 2000
        else:
            ordem = 500
    with get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO tamanhos (codigo, grupo, ordem) VALUES (?, ?, ?)",
                (codigo, grupo, ordem),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"O tamanho {codigo} já está cadastrado.") from exc
        return int(cur.lastrowid)


def listar_lotes() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT l.*,
                   COALESCE(g.pecas, 0) AS pecas_originais
            FROM lotes l
            LEFT JOIN (
                SELECT lote_id, SUM(qnt_original) AS pecas
                FROM lote_grade
                GROUP BY lote_id
            ) g ON g.lote_id = l.id
            ORDER BY l.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def obter_lote(lote_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
        return dict(row) if row else None


def _recalcular_valor_total(conn: sqlite3.Connection, lote_id: int) -> float:
    row = conn.execute(
        """
        SELECT l.preco_unitario,
               COALESCE(SUM(g.qnt_original), 0) AS pecas
        FROM lotes l
        LEFT JOIN lote_grade g ON g.lote_id = l.id
        WHERE l.id = ?
        """,
        (lote_id,),
    ).fetchone()
    valor = float(row["preco_unitario"]) * int(row["pecas"])
    conn.execute("UPDATE lotes SET valor_total = ? WHERE id = ?", (valor, lote_id))
    return valor


def criar_lote(
    *,
    cor: str,
    cor_hex: str,
    op: str,
    referencia: str,
    descricao: str,
    preco_unitario: float,
    grade: list[tuple[int, int]],
) -> int:
    if not op.strip():
        raise ValueError("Informe o número da OP.")
    if not referencia.strip():
        raise ValueError("Informe a referência.")
    if not any(qnt > 0 for _, qnt in grade):
        raise ValueError("Informe a quantidade original de pelo menos um tamanho.")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO lotes (cor, cor_hex, op, referencia, descricao, preco_unitario)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cor.strip() or "Sem cor",
                cor_hex or "#1B4F72",
                op.strip(),
                referencia.strip(),
                descricao.strip(),
                float(preco_unitario or 0),
            ),
        )
        lote_id = int(cur.lastrowid)
        for tamanho_id, qnt in grade:
            if qnt > 0:
                conn.execute(
                    """
                    INSERT INTO lote_grade (lote_id, tamanho_id, qnt_original)
                    VALUES (?, ?, ?)
                    """,
                    (lote_id, tamanho_id, int(qnt)),
                )
        _recalcular_valor_total(conn, lote_id)
        return lote_id


def excluir_lote(lote_id: int) -> None:
    with get_conn() as conn:
        usado = conn.execute(
            "SELECT 1 FROM remessa_itens WHERE lote_id = ? LIMIT 1",
            (lote_id,),
        ).fetchone()
        if usado:
            raise ValueError("Não é possível excluir uma OP que já possui remessa.")
        conn.execute("DELETE FROM lotes WHERE id = ?", (lote_id,))


def saldos_por_lote(lote_id: int | None = None) -> list[dict[str, Any]]:
    filtro = ""
    params: tuple[Any, ...] = ()
    if lote_id is not None:
        filtro = "WHERE g.lote_id = ?"
        params = (lote_id,)
    sql = f"""
        SELECT
            l.id AS lote_id,
            l.op,
            l.cor,
            l.cor_hex,
            l.referencia,
            l.descricao,
            l.preco_unitario,
            l.valor_total,
            t.id AS tamanho_id,
            t.codigo AS tamanho,
            t.grupo,
            t.ordem,
            g.qnt_original,
            COALESCE(am.qtd_1a, 0) AS amarrado_1a,
            COALESCE(am.qtd_2a, 0) AS amarrado_2a,
            COALESCE(en.qtd_1a, 0) AS enviado_1a,
            COALESCE(en.qtd_2a, 0) AS enviado_2a
        FROM lote_grade g
        JOIN lotes l ON l.id = g.lote_id
        JOIN tamanhos t ON t.id = g.tamanho_id
        LEFT JOIN (
            SELECT lote_id, tamanho_id,
                   SUM(qtd_1a) AS qtd_1a,
                   SUM(qtd_2a) AS qtd_2a
            FROM amarracoes
            GROUP BY lote_id, tamanho_id
        ) am ON am.lote_id = g.lote_id AND am.tamanho_id = g.tamanho_id
        LEFT JOIN (
            SELECT lote_id, tamanho_id,
                   SUM(qtd_1a) AS qtd_1a,
                   SUM(qtd_2a) AS qtd_2a
            FROM remessa_itens
            GROUP BY lote_id, tamanho_id
        ) en ON en.lote_id = g.lote_id AND en.tamanho_id = g.tamanho_id
        {filtro}
        ORDER BY l.id DESC, t.ordem, t.codigo
    """
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r["amarrado_total"] = int(r["amarrado_1a"]) + int(r["amarrado_2a"])
        r["enviado_total"] = int(r["enviado_1a"]) + int(r["enviado_2a"])
        r["estoque_1a"] = int(r["amarrado_1a"]) - int(r["enviado_1a"])
        r["estoque_2a"] = int(r["amarrado_2a"]) - int(r["enviado_2a"])
        r["estoque_oficina"] = r["estoque_1a"] + r["estoque_2a"]
        r["saldo_restante"] = int(r["qnt_original"]) - r["amarrado_total"]
    return rows


def lancar_amarracao(
    *,
    data_lanc: date,
    lote_id: int,
    tamanho_id: int,
    qtd_1a: int,
    qtd_2a: int,
    observacao: str = "",
) -> int:
    qtd_1a = int(qtd_1a or 0)
    qtd_2a = int(qtd_2a or 0)
    if qtd_1a < 0 or qtd_2a < 0:
        raise ValueError("Quantidades não podem ser negativas.")
    if qtd_1a == 0 and qtd_2a == 0:
        raise ValueError("Informe pelo menos uma peça amarrada.")
    saldos = [
        s
        for s in saldos_por_lote(lote_id)
        if s["tamanho_id"] == tamanho_id
    ]
    if not saldos:
        raise ValueError("Este tamanho não faz parte da grade da OP.")
    saldo = saldos[0]
    a_lancar = qtd_1a + qtd_2a
    if a_lancar > saldo["saldo_restante"]:
        raise ValueError(
            f"Saldo insuficiente para costurar. Faltam {saldo['saldo_restante']} pç(s) neste tamanho."
        )
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO amarracoes (data, lote_id, tamanho_id, qtd_1a, qtd_2a, observacao)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data_lanc.isoformat(),
                lote_id,
                tamanho_id,
                qtd_1a,
                qtd_2a,
                observacao.strip() or None,
            ),
        )
        return int(cur.lastrowid)


def listar_amarracoes(lote_id: int | None = None, limite: int = 80) -> list[dict[str, Any]]:
    sql = """
        SELECT a.id, a.data, a.qtd_1a, a.qtd_2a, a.observacao,
               l.op, l.cor, l.referencia, t.codigo AS tamanho
        FROM amarracoes a
        JOIN lotes l ON l.id = a.lote_id
        JOIN tamanhos t ON t.id = a.tamanho_id
    """
    params: list[Any] = []
    if lote_id is not None:
        sql += " WHERE a.lote_id = ?"
        params.append(lote_id)
    sql += " ORDER BY a.data DESC, a.id DESC LIMIT ?"
    params.append(limite)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def proximo_romaneio() -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT numero_romaneio FROM remessas ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return "ROM-0001"
    digits = "".join(ch for ch in row["numero_romaneio"] if ch.isdigit())
    n = int(digits) + 1 if digits else 1
    return f"ROM-{n:04d}"


def fechar_remessa(
    *,
    data_remessa: date,
    numero_romaneio: str,
    itens: list[dict[str, int]],
    observacao: str = "",
) -> int:
    numero_romaneio = numero_romaneio.strip().upper()
    if not numero_romaneio:
        raise ValueError("Informe o número do romaneio.")
    linhas = [
        i
        for i in itens
        if int(i.get("qtd_1a") or 0) > 0 or int(i.get("qtd_2a") or 0) > 0
    ]
    if not linhas:
        raise ValueError("Selecione ao menos uma quantidade para envio.")

    saldos = {(s["lote_id"], s["tamanho_id"]): s for s in saldos_por_lote()}
    for item in linhas:
        chave = (int(item["lote_id"]), int(item["tamanho_id"]))
        saldo = saldos.get(chave)
        if not saldo:
            raise ValueError("Item de remessa não encontrado na grade.")
        q1 = int(item.get("qtd_1a") or 0)
        q2 = int(item.get("qtd_2a") or 0)
        if q1 > saldo["estoque_1a"] or q2 > saldo["estoque_2a"]:
            raise ValueError(
                f"Estoque insuficiente na oficina para OP {saldo['op']} tam. {saldo['tamanho']}."
            )

    with get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO remessas (data, numero_romaneio, observacao)
                VALUES (?, ?, ?)
                """,
                (data_remessa.isoformat(), numero_romaneio, observacao.strip() or None),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"O romaneio {numero_romaneio} já existe.") from exc
        remessa_id = int(cur.lastrowid)
        for item in linhas:
            conn.execute(
                """
                INSERT INTO remessa_itens (remessa_id, lote_id, tamanho_id, qtd_1a, qtd_2a)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    remessa_id,
                    int(item["lote_id"]),
                    int(item["tamanho_id"]),
                    int(item.get("qtd_1a") or 0),
                    int(item.get("qtd_2a") or 0),
                ),
            )
        return remessa_id


def obter_remessa(remessa_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        cab = conn.execute("SELECT * FROM remessas WHERE id = ?", (remessa_id,)).fetchone()
        if not cab:
            return None
        itens = conn.execute(
            """
            SELECT ri.qtd_1a, ri.qtd_2a,
                   l.op, l.cor, l.referencia, l.descricao, l.preco_unitario,
                   t.codigo AS tamanho
            FROM remessa_itens ri
            JOIN lotes l ON l.id = ri.lote_id
            JOIN tamanhos t ON t.id = ri.tamanho_id
            WHERE ri.remessa_id = ?
            ORDER BY l.op, t.ordem, t.codigo
            """,
            (remessa_id,),
        ).fetchall()
    return {"cabecalho": dict(cab), "itens": [dict(i) for i in itens]}


def listar_remessas() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.data, r.numero_romaneio, r.observacao,
                   COUNT(ri.id) AS linhas,
                   COALESCE(SUM(ri.qtd_1a + ri.qtd_2a), 0) AS pecas
            FROM remessas r
            LEFT JOIN remessa_itens ri ON ri.remessa_id = r.id
            GROUP BY r.id
            ORDER BY r.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
