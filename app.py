"""
Controle de Produção e Remessa — Facção / Confecção Têxtil
----------------------------------------------------------
Tela 1  Cadastro e painel dinâmico de OPs
Tela 2  Caderno digital de amarrações
Tela 3  Fechamento de remessa e emissão de PDF
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import db
from pdf_romaneio import gerar_pdf_romaneio, salvar_pdf

st.set_page_config(
    page_title="Controle de Produção Têxtil",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Source+Sans+3:wght@400;600;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Source Sans 3', sans-serif;
}
.block-container { padding-top: 1.2rem; max-width: 1400px; }

h1, h2, h3 { font-family: 'Cormorant Garamond', serif !important; letter-spacing: .02em; }

.hero {
    background: linear-gradient(120deg, #12263A 0%, #1B4F72 55%, #1A5276 100%);
    border-radius: 18px;
    padding: 22px 28px 20px;
    color: #F7F3EB;
    margin-bottom: 18px;
    border-bottom: 4px solid #C9A227;
}
.hero h1 { color: #F7F3EB !important; margin: 0; font-size: 2.1rem; }
.hero p { margin: 4px 0 0; opacity: .85; font-size: .95rem; }

.kpi {
    background: #fff;
    border: 1px solid #E5E1D8;
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 8px 20px rgba(18,38,58,.04);
}
.kpi .lbl { font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; color: #7B8A99; }
.kpi .val { font-size: 1.55rem; font-weight: 700; color: #12263A; line-height: 1.2; }

.op-card {
    background: #fff;
    border: 1px solid #E5E1D8;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 14px;
    box-shadow: 0 10px 24px rgba(18,38,58,.05);
}
.op-head {
    padding: 12px 16px 10px;
    color: #fff;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
}
.op-head .op { font-family: 'Cormorant Garamond', serif; font-size: 1.45rem; font-weight: 700; }
.op-head .meta { font-size: .85rem; opacity: .92; }
.op-body { padding: 8px 10px 12px; }

.size-chip {
    border: 1px solid #E5E1D8;
    border-radius: 12px;
    padding: 8px 10px;
    background: #FBFAF7;
    min-height: 108px;
}
.size-chip .tam { font-weight: 700; font-size: 1.05rem; color: #12263A; }
.size-chip .q { font-size: .78rem; color: #5D6D7E; line-height: 1.35; }
.saldo-ok { color: #1E8449; font-weight: 700; }
.saldo-zero { color: #B9770E; font-weight: 700; }
.saldo-neg { color: #922B21; font-weight: 700; }

div[data-testid="stSidebar"] { background: #12263A; }
div[data-testid="stSidebar"] * { color: #F7F3EB !important; }
div[data-testid="stSidebar"] .stRadio label { font-weight: 600; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def _brl(valor: float) -> str:
    txt = f"{float(valor):,.2f}"
    return "R$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _contraste(hex_color: str) -> str:
    h = (hex_color or "#1B4F72").lstrip("#")
    if len(h) != 6:
        return "#ffffff"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#12263A" if luma > 0.62 else "#ffffff"


def _rotulo_lote(lote: dict) -> str:
    return f"OP {lote['op']} · {lote['referencia']} · {lote['cor']}"


def _classe_saldo(n: int) -> str:
    if n > 0:
        return "saldo-ok"
    if n == 0:
        return "saldo-zero"
    return "saldo-neg"


# ---------------------------------------------------------------------------
# Tela 1 — Cadastro e painel de OPs
# ---------------------------------------------------------------------------
def tela_ops() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Cadastro e painel de OPs</h1>
            <p>Grade dinâmica por lote · totais amarrados (1ª / 2ª) · saldo restante para costurar</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    saldos = db.saldos_por_lote()
    lotes = db.listar_lotes()
    pecas_op = sum(int(s["qnt_original"]) for s in saldos)
    oficina = sum(int(s["estoque_oficina"]) for s in saldos)
    falta = sum(int(s["saldo_restante"]) for s in saldos)

    k1, k2, k3, k4 = st.columns(4)
    for col, lbl, val in (
        (k1, "OPs ativas", str(len(lotes))),
        (k2, "Peças da grade", f"{pecas_op:,}".replace(",", ".")),
        (k3, "Estoque na oficina", f"{oficina:,}".replace(",", ".")),
        (k4, "Falta costurar", f"{falta:,}".replace(",", ".")),
    ):
        col.markdown(
            f'<div class="kpi"><div class="lbl">{lbl}</div><div class="val">{val}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")
    with st.expander("Nova OP / lote", expanded=not lotes):
        with st.form("form_nova_op", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([1.1, 1.2, 1.6, 1.1])
            op = c1.text_input("OP *")
            referencia = c2.text_input("Referência *")
            descricao = c3.text_input("Descrição (artigo) *")
            preco = c4.number_input("Preço unitário (R$)", min_value=0.0, step=0.50, format="%.2f")

            d1, d2 = st.columns([1.4, 1])
            cor = d1.text_input("Cor *", placeholder="Ex.: Preto, Off-white, Azul marinho")
            cor_hex = d2.color_picker("Cor do cartão", "#1B4F72")

            st.markdown("**Grade original do lote** — informe a QNT de cada tamanho ativo nesta OP.")
            tamanhos = db.listar_tamanhos()
            grupos = {
                "padrao": "Padrão (PP–GG)",
                "plus_size": "Plus size (XGG–G3)",
                "numerico": "Numéricos",
            }
            grade_vals: dict[int, int] = {}
            for grupo, titulo in grupos.items():
                items = [t for t in tamanhos if t["grupo"] == grupo]
                if not items:
                    continue
                st.caption(titulo)
                cols = st.columns(len(items))
                for col, tam in zip(cols, items):
                    grade_vals[tam["id"]] = col.number_input(
                        tam["codigo"],
                        min_value=0,
                        step=1,
                        key=f"g_{tam['id']}",
                    )

            pecas_prev = sum(grade_vals.values())
            st.caption(f"Peças previstas: **{pecas_prev}** · Valor total do lote: **{_brl(pecas_prev * preco)}**")
            enviar = st.form_submit_button("Salvar OP", type="primary", use_container_width=True)

        if enviar:
            try:
                if not descricao.strip():
                    raise ValueError("Informe a descrição (artigo).")
                if not cor.strip():
                    raise ValueError("Informe a cor.")
                lote_id = db.criar_lote(
                    cor=cor,
                    cor_hex=cor_hex,
                    op=op,
                    referencia=referencia,
                    descricao=descricao,
                    preco_unitario=preco,
                    grade=list(grade_vals.items()),
                )
                st.success(f"OP gravada com ID {lote_id}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with st.expander("Cadastro de tamanhos (grade dinâmica)"):
        st.caption(
            "Pré-configurados: PP, P, M, G, GG e plus size XGG, G1, G2, G3. "
            "Tamanhos numéricos (36, 38, 40…) podem ser incluídos quando a modelagem exigir."
        )
        existentes = db.listar_tamanhos(apenas_ativos=False)
        st.dataframe(
            pd.DataFrame(existentes)[["codigo", "grupo", "ordem", "ativo"]]
            if existentes
            else pd.DataFrame(),
            use_container_width=True,
            hide_index=True,
        )
        n1, n2, n3 = st.columns([1.2, 1.4, 1])
        novo_cod = n1.text_input("Novo tamanho", placeholder="Ex.: 38 ou XG")
        novo_grp = n2.selectbox(
            "Grupo",
            options=["padrao", "plus_size", "numerico"],
            format_func=lambda g: {
                "padrao": "Padrão",
                "plus_size": "Plus size",
                "numerico": "Numérico",
            }[g],
        )
        if n3.button("Incluir tamanho", use_container_width=True):
            try:
                db.cadastrar_tamanho(novo_cod, novo_grp)
                st.success("Tamanho cadastrado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    st.subheader("Painel dinâmico")
    if not lotes:
        st.info("Nenhuma OP cadastrada. Use o formulário acima para começar.")
        return

    busca = st.text_input("Filtrar por OP, referência, cor ou artigo", placeholder="Buscar…")
    lotes_filtrados = lotes
    if busca.strip():
        q = busca.strip().lower()
        lotes_filtrados = [
            l
            for l in lotes
            if q in str(l["op"]).lower()
            or q in str(l["referencia"]).lower()
            or q in str(l["cor"]).lower()
            or q in str(l["descricao"]).lower()
        ]

    por_lote: dict[int, list[dict]] = {}
    for s in saldos:
        por_lote.setdefault(int(s["lote_id"]), []).append(s)

    for lote in lotes_filtrados:
        linhas = por_lote.get(int(lote["id"]), [])
        fg = _contraste(lote["cor_hex"])
        tot_orig = sum(int(x["qnt_original"]) for x in linhas)
        tot_am1 = sum(int(x["amarrado_1a"]) for x in linhas)
        tot_am2 = sum(int(x["amarrado_2a"]) for x in linhas)
        tot_saldo = sum(int(x["saldo_restante"]) for x in linhas)

        chips = []
        for s in linhas:
            cls = _classe_saldo(int(s["saldo_restante"]))
            chips.append(
                f"""
                <div class="size-chip">
                    <div class="tam">{s['tamanho']}</div>
                    <div class="q">Original: <b>{s['qnt_original']}</b></div>
                    <div class="q">Amarrado 1ª: <b>{s['amarrado_1a']}</b> · 2ª: <b>{s['amarrado_2a']}</b></div>
                    <div class="q">Total amarrado: <b>{s['amarrado_total']}</b></div>
                    <div class="{cls}">Saldo: {s['saldo_restante']}</div>
                </div>
                """
            )
        grid = "".join(
            f'<div style="flex:1 1 120px; max-width:180px;">{c}</div>' for c in chips
        )
        st.markdown(
            f"""
            <div class="op-card">
              <div class="op-head" style="background:{lote['cor_hex']}; color:{fg};">
                <div>
                  <div class="op">OP {lote['op']} — {lote['referencia']}</div>
                  <div class="meta">{lote['descricao']} · Cor: {lote['cor']}</div>
                </div>
                <div class="meta" style="text-align:right;">
                    Grade: {tot_orig} pç · Amarrado 1ª {tot_am1} / 2ª {tot_am2}<br/>
                    Falta costurar: <b>{tot_saldo}</b><br/>
                    Preço {_brl(lote['preco_unitario'])} · Lote {_brl(lote['valor_total'])}
                </div>
              </div>
              <div class="op-body">
                <div style="display:flex; flex-wrap:wrap; gap:8px;">{grid}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander(f"Excluir OP {lote['op']} (somente se ainda não houver remessa)"):
            if st.button("Confirmar exclusão", key=f"del_{lote['id']}"):
                try:
                    db.excluir_lote(int(lote["id"]))
                    st.success("OP excluída.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


# ---------------------------------------------------------------------------
# Tela 2 — Caderno digital de amarrações
# ---------------------------------------------------------------------------
def tela_amarracoes() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Caderno digital de amarrações</h1>
            <p>Lançamento diário por OP e tamanho · 1ª e 2ª qualidade acumulam no estoque da oficina</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    lotes = db.listar_lotes()
    if not lotes:
        st.warning("Cadastre uma OP na Tela 1 antes de lançar amarrações.")
        return

    c1, c2 = st.columns([1.4, 1])
    lote = c1.selectbox("OP / lote", lotes, format_func=_rotulo_lote)
    data_lanc = c2.date_input("Data da amarração", value=date.today())

    saldos = db.saldos_por_lote(int(lote["id"]))

    st.markdown("#### Situação atual da grade")
    cols = st.columns(max(len(saldos), 1))
    for col, s in zip(cols, saldos):
        col.metric(
            f"Tam. {s['tamanho']}",
            f"Saldo {s['saldo_restante']}",
            f"Amarrado {s['amarrado_total']} · Oficina {s['estoque_oficina']}",
        )

    with st.form("form_amarracao"):
        a1, a2, a3, a4 = st.columns([1.2, 1, 1, 2])
        tam_escolhido = a1.selectbox(
            "Tamanho",
            options=saldos,
            format_func=lambda s: f"{s['tamanho']}  (falta {s['saldo_restante']})",
        )
        q1 = a2.number_input("Qtd 1ª qualidade", min_value=0, step=1)
        q2 = a3.number_input("Qtd 2ª qualidade", min_value=0, step=1)
        obs = a4.text_input("Observação (opcional)")
        salvar = st.form_submit_button("Lançar amarração", type="primary", use_container_width=True)

    if salvar:
        try:
            db.lancar_amarracao(
                data_lanc=data_lanc,
                lote_id=int(lote["id"]),
                tamanho_id=int(tam_escolhido["tamanho_id"]),
                qtd_1a=int(q1),
                qtd_2a=int(q2),
                observacao=obs,
            )
            st.success("Amarração lançada. O estoque da oficina foi atualizado.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.markdown("#### Histórico recente")
    hist = db.listar_amarracoes(int(lote["id"]))
    if hist:
        df = pd.DataFrame(hist)
        df["total"] = df["qtd_1a"] + df["qtd_2a"]
        st.dataframe(
            df[["data", "tamanho", "qtd_1a", "qtd_2a", "total", "observacao"]].rename(
                columns={
                    "data": "Data",
                    "tamanho": "Tam.",
                    "qtd_1a": "1ª Qual.",
                    "qtd_2a": "2ª Qual.",
                    "total": "Total",
                    "observacao": "Obs.",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Nenhum lançamento nesta OP.")


# ---------------------------------------------------------------------------
# Tela 3 — Remessa e PDF
# ---------------------------------------------------------------------------
def tela_remessas() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Fechamento de remessa</h1>
            <p>Estoque de amarrados na oficina · envio parcial por tamanho · romaneio em PDF</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    estoque = [s for s in db.saldos_por_lote() if s["estoque_oficina"] > 0]
    if not estoque:
        st.info("Não há peças amarradas disponíveis para envio. Lance amarrações na Tela 2.")
    else:
        st.markdown("#### Estoque de amarrados na oficina (disponível para envio)")
        vis = pd.DataFrame(estoque)[
            [
                "op",
                "referencia",
                "cor",
                "tamanho",
                "estoque_1a",
                "estoque_2a",
                "estoque_oficina",
                "saldo_restante",
            ]
        ].rename(
            columns={
                "op": "OP",
                "referencia": "Ref.",
                "cor": "Cor",
                "tamanho": "Tam.",
                "estoque_1a": "Disp. 1ª",
                "estoque_2a": "Disp. 2ª",
                "estoque_oficina": "Total oficina",
                "saldo_restante": "Ainda falta costurar",
            }
        )
        st.dataframe(vis, use_container_width=True, hide_index=True)

        st.markdown("#### Montar remessa")
        r1, r2, r3 = st.columns([1, 1, 2])
        data_rem = r1.date_input("Data da remessa", value=date.today())
        numero = r2.text_input("Número do romaneio", value=db.proximo_romaneio())
        obs = r3.text_input("Observação do romaneio")

        st.caption("Informe as quantidades parciais a enviar. Deixe 0 nos itens que não saem nesta remessa.")
        envios: list[dict] = []
        header = st.columns([1.1, 1.3, 1.1, 0.7, 1, 1, 1.2])
        header[0].markdown("**OP**")
        header[1].markdown("**Ref. / Cor**")
        header[2].markdown("**Artigo**")
        header[3].markdown("**Tam.**")
        header[4].markdown("**Enviar 1ª**")
        header[5].markdown("**Enviar 2ª**")
        header[6].markdown("**Disponível**")

        for s in estoque:
            cols = st.columns([1.1, 1.3, 1.1, 0.7, 1, 1, 1.2])
            cols[0].write(s["op"])
            cols[1].write(f"{s['referencia']} · {s['cor']}")
            cols[2].write(s["descricao"])
            cols[3].write(s["tamanho"])
            q1 = cols[4].number_input(
                "1a",
                min_value=0,
                max_value=int(s["estoque_1a"]),
                value=0,
                step=1,
                key=f"e1_{s['lote_id']}_{s['tamanho_id']}",
                label_visibility="collapsed",
            )
            q2 = cols[5].number_input(
                "2a",
                min_value=0,
                max_value=int(s["estoque_2a"]),
                value=0,
                step=1,
                key=f"e2_{s['lote_id']}_{s['tamanho_id']}",
                label_visibility="collapsed",
            )
            cols[6].caption(f"1ª {s['estoque_1a']} · 2ª {s['estoque_2a']}")
            envios.append(
                {
                    "lote_id": int(s["lote_id"]),
                    "tamanho_id": int(s["tamanho_id"]),
                    "qtd_1a": int(q1),
                    "qtd_2a": int(q2),
                }
            )

        if st.button("Fechar remessa e gerar PDF", type="primary", use_container_width=True):
            try:
                remessa_id = db.fechar_remessa(
                    data_remessa=data_rem,
                    numero_romaneio=numero,
                    itens=envios,
                    observacao=obs,
                )
                remessa = db.obter_remessa(remessa_id)
                pdf_bytes = gerar_pdf_romaneio(remessa)
                path = salvar_pdf(remessa)
                st.session_state["ultimo_pdf"] = {
                    "nome": path.name,
                    "bytes": pdf_bytes,
                    "romaneio": remessa["cabecalho"]["numero_romaneio"],
                }
                st.success(f"Remessa {numero} fechada. PDF salvo em {path}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if st.session_state.get("ultimo_pdf"):
        pdf = st.session_state["ultimo_pdf"]
        st.download_button(
            f"Baixar PDF {pdf['romaneio']}",
            data=pdf["bytes"],
            file_name=pdf["nome"],
            mime="application/pdf",
            type="primary",
        )

    st.markdown("#### Remessas anteriores")
    hist = db.listar_remessas()
    if not hist:
        st.caption("Nenhuma remessa emitida.")
        return
    for r in hist:
        c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.4])
        c1.write(f"**{r['numero_romaneio']}**")
        c2.write(r["data"])
        c3.write(f"{r['pecas']} pç · {r['linhas']} linhas")
        if c4.button("Reemitir PDF", key=f"pdf_{r['id']}"):
            remessa = db.obter_remessa(int(r["id"]))
            pdf_bytes = gerar_pdf_romaneio(remessa)
            path = salvar_pdf(remessa)
            st.download_button(
                f"Download {r['numero_romaneio']}",
                data=pdf_bytes,
                file_name=path.name,
                mime="application/pdf",
                key=f"dl_{r['id']}",
            )


def main() -> None:
    with st.sidebar:
        st.markdown("### 🧵 Facção / Confecção")
        st.caption("Controle de produção e remessa")
        pagina = st.radio(
            "Telas",
            options=["ops", "amarracoes", "remessas"],
            format_func=lambda p: {
                "ops": "1 · Cadastro e painel de OPs",
                "amarracoes": "2 · Amarrações (caderno)",
                "remessas": "3 · Remessa e PDF",
            }[p],
        )
        st.markdown("---")
        st.caption(
            "Saldo restante = grade original − total amarrado.\n\n"
            "Estoque na oficina = amarrado − já enviado."
        )

    if pagina == "ops":
        tela_ops()
    elif pagina == "amarracoes":
        tela_amarracoes()
    else:
        tela_remessas()


if __name__ == "__main__":
    main()
