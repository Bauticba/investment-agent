import smtplib
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(override=True)


def send_investment_email(result: dict):
    """
    Recibe el resultado completo del CIO y envía un email
    con la tesis de inversión formateada.
    """

    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")

    if not email_user or not email_pass:
        print("⚠️  Email no configurado en .env — saltando envío.")
        return False

    thesis = result.get("ceo_thesis", {})
    ticker = result.get("ticker", "N/A")
    reports = result.get("reports", {})

    scores = {k: v.get("score", "N/A") for k, v in reports.items()}

    verdict_emoji = {
        "buy":   "🟢 COMPRAR",
        "sell":  "🔴 VENDER",
        "hold":  "🟡 MANTENER",
        "avoid": "⛔ EVITAR"
    }

    verdict_display = verdict_emoji.get(
        thesis.get("final_verdict", ""),
        thesis.get("final_verdict", "").upper()
    )

    pros_html  = "".join(f"<li>✓ {p}</li>" for p in thesis.get("pros", []))
    cons_html  = "".join(f"<li>✗ {c}</li>" for c in thesis.get("cons", []))
    steps_html = "".join(
        f"<li style='margin-bottom:8px'><b>{s}</b></li>"
        for s in thesis.get("action_steps", [])
    )

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 680px; margin: auto; color: #222;">

    <div style="background:#1a1a2e; color:white; padding:24px; border-radius:8px 8px 0 0;">
        <h1 style="margin:0; font-size:22px;">📊 Tesis de Inversión — {ticker}</h1>
        <p style="margin:8px 0 0; opacity:0.7; font-size:13px;">
            Sistema de Agentes IA · Análisis automático
        </p>
    </div>

    <div style="background:#f8f9fa; padding:20px; border-left:4px solid #0066cc;">
        <h2 style="margin:0 0 8px; font-size:28px;">{verdict_display}</h2>
        <p style="margin:0; color:#555;">
            Score CEO: <b>{thesis.get("ceo_score")}/10</b> ·
            Convicción: <b>{thesis.get("conviction", "").upper()}</b> ·
            Horizonte: <b>{thesis.get("time_horizon")}</b>
        </p>
    </div>

    <div style="padding:20px; background:white; border:1px solid #e0e0e0;">
        <h3 style="color:#1a1a2e;">📋 Tesis Principal</h3>
        <p style="line-height:1.7; color:#333;">{thesis.get("thesis")}</p>
    </div>

    <div style="padding:20px; background:white; border:1px solid #e0e0e0; margin-top:2px;">
        <table style="width:100%; border-collapse:collapse;">
            <tr>
                <td style="padding:8px; background:#e8f5e9; border-radius:4px; font-size:14px;">
                    <b>🎯 Stop Loss:</b> ${thesis.get("stop_loss")}
                </td>
                <td style="width:10px;"></td>
                <td style="padding:8px; background:#e3f2fd; border-radius:4px; font-size:14px;">
                    <b>🎯 Take Profit:</b> ${thesis.get("take_profit")}
                </td>
            </tr>
        </table>
    </div>

    <div style="padding:20px; background:white; border:1px solid #e0e0e0; margin-top:2px;">
        <table style="width:100%;">
            <tr>
                <td style="vertical-align:top; width:50%;">
                    <h3 style="color:#2e7d32;">✅ Argumentos a favor</h3>
                    <ul style="color:#333; line-height:1.8;">{pros_html}</ul>
                </td>
                <td style="vertical-align:top; width:50%;">
                    <h3 style="color:#c62828;">❌ Argumentos en contra</h3>
                    <ul style="color:#333; line-height:1.8;">{cons_html}</ul>
                </td>
            </tr>
        </table>
    </div>

    <div style="padding:20px; background:white; border:1px solid #e0e0e0; margin-top:2px;">
        <h3 style="color:#1a1a2e;">📌 Pasos a seguir</h3>
        <ol style="color:#333; line-height:1.8;">{steps_html}</ol>
    </div>

    <div style="padding:20px; background:white; border:1px solid #e0e0e0; margin-top:2px;">
        <h3 style="color:#1a1a2e;">🔬 Scores por agente</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr style="background:#f5f5f5;">
                <td style="padding:8px; border:1px solid #ddd;"><b>Fundamental</b></td>
                <td style="padding:8px; border:1px solid #ddd;">{scores.get("fundamental")}/10</td>
                <td style="padding:8px; border:1px solid #ddd;">{reports.get("fundamental", {}).get("verdict", "").upper()}</td>
            </tr>
            <tr>
                <td style="padding:8px; border:1px solid #ddd;"><b>Técnico</b></td>
                <td style="padding:8px; border:1px solid #ddd;">{scores.get("technical")}/10</td>
                <td style="padding:8px; border:1px solid #ddd;">{reports.get("technical", {}).get("verdict", "").upper()}</td>
            </tr>
            <tr style="background:#f5f5f5;">
                <td style="padding:8px; border:1px solid #ddd;"><b>Indicadores</b></td>
                <td style="padding:8px; border:1px solid #ddd;">{scores.get("indicators")}/10</td>
                <td style="padding:8px; border:1px solid #ddd;">{reports.get("indicators", {}).get("verdict", "").upper()}</td>
            </tr>
            <tr>
                <td style="padding:8px; border:1px solid #ddd;"><b>Sentimiento</b></td>
                <td style="padding:8px; border:1px solid #ddd;">{scores.get("sentiment")}/10</td>
                <td style="padding:8px; border:1px solid #ddd;">{reports.get("sentiment", {}).get("verdict", "").upper()}</td>
            </tr>
        </table>
    </div>

    <div style="padding:20px; background:#fff3e0; border:1px solid #ffb74d; margin-top:2px; border-radius:0 0 8px 8px;">
        <h3 style="color:#e65100; margin:0 0 8px;">⚠️ Advertencia de riesgo</h3>
        <p style="margin:0; color:#555; line-height:1.6;">{thesis.get("risk_warning")}</p>
    </div>

    <p style="text-align:center; color:#999; font-size:12px; margin-top:20px;">
        Este análisis es generado automáticamente por IA y no constituye asesoramiento financiero.
        Siempre consultá con un profesional antes de invertir.
    </p>

    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[CEO] {verdict_display} — {ticker} | Score: {thesis.get('ceo_score')}/10"
    msg["From"]    = email_user
    msg["To"]      = email_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
        print(f"✅ Email enviado a {email_user}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False


def send_portfolio_email(portfolio: dict, capital: float):
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")

    if not email_user or not email_pass:
        print("⚠️  Email no configurado en .env — saltando envío.")
        return False

    positions    = portfolio.get("positions", [])
    total_inv    = portfolio.get("total_invested", 0)
    cash         = portfolio.get("cash_reserve", 0)
    cash_pct     = portfolio.get("cash_reserve_pct", 0)
    thesis       = portfolio.get("portfolio_thesis", "")
    main_risk    = portfolio.get("main_risk", "")
    exp_return   = portfolio.get("expected_return", "")
    sector_bdown = portfolio.get("sector_breakdown", {})

    rows_html = ""
    for p in positions:
        conviction_color = {"high": "#2e7d32", "medium": "#f57c00", "low": "#c62828"}.get(
            p.get("conviction", ""), "#555"
        )
        rows_html += f"""
        <tr>
          <td style="padding:10px;border:1px solid #ddd;font-weight:bold">{p['ticker']}</td>
          <td style="padding:10px;border:1px solid #ddd">{p.get('shares')} acciones</td>
          <td style="padding:10px;border:1px solid #ddd">${p.get('price', 0):.2f}</td>
          <td style="padding:10px;border:1px solid #ddd"><b>${p.get('amount_usd', 0):,.2f}</b></td>
          <td style="padding:10px;border:1px solid #ddd">{p.get('allocation_pct')}%</td>
          <td style="padding:10px;border:1px solid #ddd;color:{conviction_color};font-weight:bold">{p.get('conviction','').upper()}</td>
          <td style="padding:10px;border:1px solid #ddd">SL ${p.get('stop_loss')} / TP ${p.get('take_profit')}</td>
        </tr>
        <tr style="background:#f9f9f9">
          <td colspan="7" style="padding:8px 10px;border:1px solid #ddd;color:#555;font-size:13px;font-style:italic">
            {p.get('rationale', '')}
          </td>
        </tr>
        """

    sector_html = "".join(
        f"<span style='display:inline-block;margin:4px;padding:4px 10px;background:#e3f2fd;border-radius:12px;font-size:13px'>"
        f"<b>{s}</b>: {pct}%</span>"
        for s, pct in sector_bdown.items()
    )

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:720px;margin:auto;color:#222">

    <div style="background:#0d2137;color:white;padding:24px;border-radius:8px 8px 0 0">
      <h1 style="margin:0;font-size:22px">💼 Portafolio de Inversión</h1>
      <p style="margin:8px 0 0;opacity:0.7;font-size:13px">
        Capital: <b>${capital:,.0f} USD</b> ·
        Invertido: <b>${total_inv:,.2f}</b> ·
        Cash reserva: <b>${cash:,.2f} ({cash_pct}%)</b>
      </p>
    </div>

    <div style="padding:20px;background:#f0f4f8;border-left:4px solid #0066cc">
      <h3 style="margin:0 0 8px">📋 Tesis del Portafolio</h3>
      <p style="margin:0;line-height:1.7;color:#333">{thesis}</p>
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 12px">📊 Posiciones</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr style="background:#1a1a2e;color:white">
          <th style="padding:10px;text-align:left">Ticker</th>
          <th style="padding:10px;text-align:left">Cantidad</th>
          <th style="padding:10px;text-align:left">Precio</th>
          <th style="padding:10px;text-align:left">Monto</th>
          <th style="padding:10px;text-align:left">%</th>
          <th style="padding:10px;text-align:left">Convicción</th>
          <th style="padding:10px;text-align:left">Niveles</th>
        </tr>
        {rows_html}
      </table>
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 10px">🗂 Diversificación sectorial</h3>
      {sector_html}
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <table style="width:100%">
        <tr>
          <td style="vertical-align:top;width:50%;padding-right:10px">
            <h3 style="color:#2e7d32;margin:0 0 8px">📈 Retorno esperado</h3>
            <p style="color:#333;margin:0">{exp_return}</p>
          </td>
          <td style="vertical-align:top;width:50%">
            <h3 style="color:#c62828;margin:0 0 8px">⚠️ Riesgo principal</h3>
            <p style="color:#333;margin:0">{main_risk}</p>
          </td>
        </tr>
      </table>
    </div>

    <p style="text-align:center;color:#999;font-size:12px;margin-top:20px">
      Este análisis es generado automáticamente por IA y no constituye asesoramiento financiero.
      Siempre consultá con un profesional antes de invertir.
    </p>

    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Portfolio] ${capital:,.0f} USD — {len(positions)} posiciones"
    msg["From"]    = email_user
    msg["To"]      = email_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
        print(f"✅ Email de portafolio enviado a {email_user}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False


def send_ars_recommendation_email(rec: dict, capital: float, riesgo: str, macro: dict, cedear_picks: list = None, merval_picks: list = None):
    """Email con la recomendación de inversión en ARS generada por invest_ars.py."""
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")
    if not email_user or not email_pass:
        print("⚠️  Email no configurado en .env — saltando envío.")
        return False

    allocation   = rec.get("allocation", [])
    infl_m       = macro.get("inflation_monthly")
    infl_date    = macro.get("inflation_date")
    usd          = macro.get("usd_oficial")

    # Etiqueta del dato de inflación (mes oficial INDEC)
    _meses_email = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    if infl_date:
        try:
            _p = infl_date.split("-")
            infl_label_email = f"IPC {_meses_email[int(_p[1])-1]} {_p[0]} (INDEC)"
        except Exception:
            infl_label_email = "Inflación mensual (INDEC)"
    else:
        infl_label_email = "Inflación mensual (INDEC)"
    riesgo_label = {"bajo": "🟢 BAJO", "moderado": "🟡 MODERADO", "alto": "🔴 ALTO"}.get(riesgo, riesgo.upper())

    type_color = {
        "bono_cer":          "#1565c0",
        "lecer":             "#1565c0",
        "lecap":             "#0d47a1",
        "caucion":           "#37474f",
        "plazo_fijo_uva":    "#6a1b9a",
        "plazo_fijo":        "#4a148c",
        "dolar_mep":         "#1b5e20",
        "bono_hard_dollar":  "#004d40",
        "on_usd":            "#01579b",
        "fci_mm":            "#e65100",
        "fci_renta_fija":    "#bf360c",
        "fci_dolar_linked":  "#1b5e20",
        "fci_acciones":      "#b71c1c",
        "cedear":            "#880e4f",
        "cedears":           "#880e4f",
        "accion_merval":     "#4a148c",
    }
    type_emoji = {
        "bono_cer":          "📈",
        "lecer":             "📈",
        "lecap":             "📋",
        "caucion":           "🔐",
        "plazo_fijo_uva":    "🔒",
        "plazo_fijo":        "🔒",
        "dolar_mep":         "💵",
        "bono_hard_dollar":  "💲",
        "on_usd":            "🏢",
        "fci_mm":            "💧",
        "fci_renta_fija":    "💧",
        "fci_dolar_linked":  "💵",
        "fci_acciones":      "📊",
        "cedear":            "🌎",
        "cedears":           "🌎",
        "accion_merval":     "🇦🇷",
    }

    rows_html = ""
    for p in allocation:
        t     = p.get("type", "")
        color = type_color.get(t, "#555")
        emoji = type_emoji.get(t, "")
        rows_html += f"""
        <tr>
          <td style="padding:10px;border:1px solid #ddd;font-weight:bold">
            <span style="color:{color}">{emoji} {p.get('name','')}</span>
          </td>
          <td style="padding:10px;border:1px solid #ddd;text-align:center">
            <b>{p.get('allocation_pct',0):.0f}%</b>
          </td>
          <td style="padding:10px;border:1px solid #ddd;text-align:right">
            <b>${p.get('amount_ars',0):,.0f}</b>
          </td>
        </tr>
        <tr style="background:#f9f9f9">
          <td colspan="3" style="padding:8px 10px;border:1px solid #ddd;color:#555;font-size:13px">
            <b>Cómo comprar:</b> {p.get('how_to_buy','')}<br>
            <i>{p.get('rationale','')}</i>
          </td>
        </tr>
        """

    # Separar CEDEARs picks: los que están en la cartera vs los que son alternativas
    cedear_html = ""
    if cedear_picks:
        alloc_text = " ".join(
            (pos.get("name", "") + " " + pos.get("instrument_id", "")).upper()
            for pos in allocation if pos.get("type") in ("cedear", "cedears")
        )
        en_cartera   = [p for p in cedear_picks if p["ticker"].upper() in alloc_text]
        alternativas = [p for p in cedear_picks if p["ticker"].upper() not in alloc_text]

        def _cedear_item_html(p, badge="", in_cartera=True):
            par_str = f"${p['parity_price_ars']:,.0f} ARS" if p.get("parity_price_ars") else "N/A"
            if in_cartera:
                _default_how = f"IOL > Operar > CEDEARs > buscar {p['ticker']} > Comprar"
                iol_line = f"📍 {p.get('how_to_buy', _default_how)}"
            else:
                iol_line = f"📌 Monitorear en IOL: Mercados > CEDEARs > {p['ticker']}. No ejecutar orden en esta cartera."
            return f"""
            <div style="border:1px solid #e0e0e0;border-radius:6px;padding:14px;margin-bottom:10px">
              <b>{p['ticker']} — {p['name']}{badge}</b>
              <span style="float:right;background:#1a1a2e;color:white;padding:2px 8px;border-radius:10px;font-size:13px">
                Score {p.get('score','?')}/10
              </span><br>
              <span style="color:#555;font-size:13px">
                Subyacente: ${p.get('us_price_usd','?')} USD &nbsp;·&nbsp;
                Paridad ARS: {par_str} (ratio 1:{p.get('ratio','?')})
              </span><br>
              <span style="font-size:13px;color:#333;margin-top:4px;display:block">
                {p.get('thesis','')}
              </span>
              <span style="font-size:12px;color:#888;margin-top:4px;display:block">
                {iol_line}
              </span>
            </div>
            """

        sections = ""
        if en_cartera:
            items_html = "".join(_cedear_item_html(p, " ✅", in_cartera=True) for p in en_cartera)
            sections += f"""
            <h4 style="color:#2e7d32;margin:0 0 10px">CEDEARs incluidos en la cartera</h4>
            {items_html}
            """
        if alternativas:
            items_html = "".join(_cedear_item_html(p, in_cartera=False) for p in alternativas)
            sections += f"""
            <h4 style="color:#555;margin:{'16px' if en_cartera else '0'} 0 6px">CEDEARs analizados — no incluidos en esta cartera</h4>
            <p style="margin:0 0 10px;font-size:12px;color:#888">Buen score pero descartados por el advisor en este contexto.</p>
            {items_html}
            """

        cedear_html = f"""
        <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
          <h3 style="color:#880e4f;margin:0 0 14px">🌎 CEDEARs analizados</h3>
          {sections}
        </div>
        """

    # MERVAL picks — separar en cartera vs analizadas
    merval_html = ""
    if merval_picks:
        alloc_merval_text = " ".join(
            (pos.get("instrument_id", "") + " " + pos.get("name", "")).upper()
            for pos in allocation if pos.get("type") == "accion_merval"
        )
        en_cartera_m   = [p for p in merval_picks if p["ticker"].upper() in alloc_merval_text]
        alternativas_m = [p for p in merval_picks if p["ticker"].upper() not in alloc_merval_text]

        def _merval_item_html(p):
            price_str = f"${p['market_price_ars']:,.0f} ARS" if p.get("market_price_ars") else "N/A"
            ccl_str   = f" | CCL impl.: ${p['ccl_implicit']:,.0f}" if p.get("ccl_implicit") else ""
            action    = p.get("action", "hold")
            default_how = (
                f"IOL > Operar > Acciones > buscar {p['ticker']} > Comprar" if action == "buy"
                else f"Monitorear en IOL: Mercados > MERVAL > {p['ticker']}. No ejecutar orden aún."
            )
            return f"""
            <div style="border:1px solid #e0e0e0;border-radius:6px;padding:14px;margin-bottom:10px">
              <b>🇦🇷 {p['ticker']} — {p.get('name', p['ticker'])}</b>
              <span style="float:right;background:#4a148c;color:white;padding:2px 8px;border-radius:10px;font-size:13px">
                Score {p.get('score','?')}/10
              </span><br>
              <span style="color:#555;font-size:13px">
                Precio: {price_str}{ccl_str} &nbsp;·&nbsp;
                Acción: <b>{action.upper()}</b>
              </span><br>
              <span style="font-size:13px;color:#333;margin-top:4px;display:block">
                {p.get('rationale','')}
              </span>
              <span style="font-size:12px;color:#888;margin-top:4px;display:block">
                📍 {p.get('how_to_buy') or default_how}
              </span>
            </div>
            """

        sections_m = ""
        if en_cartera_m:
            items_m = "".join(_merval_item_html(p) for p in en_cartera_m)
            sections_m += f"""
            <h4 style="color:#2e7d32;margin:0 0 10px">Incluidas en la cartera ✅</h4>
            {items_m}
            """
        if alternativas_m:
            items_m = "".join(_merval_item_html(p) for p in alternativas_m)
            sections_m += f"""
            <h4 style="color:#555;margin:{'16px' if en_cartera_m else '0'} 0 6px">Analizadas — no incluidas en cartera</h4>
            <p style="margin:0 0 10px;font-size:12px;color:#888">Score ≥ 6 pero no seleccionadas en este contexto. Seguirlas como alternativas.</p>
            {items_m}
            """

        merval_html = f"""
        <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
          <h3 style="color:#4a148c;margin:0 0 14px">🇦🇷 Acciones MERVAL analizadas</h3>
          {sections_m}
        </div>
        """

    # Pre-computar tabla de riesgo por instrumento
    risk_rows = [p for p in allocation if p.get("main_risk") or p.get("role")]
    if risk_rows:
        _risk_rows_html = "".join(
            f"""<tr style="{'background:#f9f9f9' if i%2 else ''}">
              <td style="padding:8px 10px;border:1px solid #eee;font-weight:bold;font-size:13px">{p.get('name','?')}</td>
              <td style="padding:8px 10px;border:1px solid #eee;font-size:13px;color:#c62828">{p.get('main_risk','—')}</td>
              <td style="padding:8px 10px;border:1px solid #eee;font-size:13px;text-align:center">{p.get('liquidity','—')}</td>
              <td style="padding:8px 10px;border:1px solid #eee;font-size:13px;color:#1565c0">{p.get('role','—')}</td>
            </tr>"""
            for i, p in enumerate(risk_rows)
        )
        _risk_table_html = f"""
        <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
          <h3 style="color:#1a1a2e;margin:0 0 10px">📋 Riesgo por instrumento</h3>
          <table style="width:100%;border-collapse:collapse">
            <tr style="background:#1a1a2e;color:white;font-size:12px">
              <th style="padding:8px 10px;text-align:left">Instrumento</th>
              <th style="padding:8px 10px;text-align:left">Riesgo principal</th>
              <th style="padding:8px 10px;text-align:center">Liquidez</th>
              <th style="padding:8px 10px;text-align:left">Rol</th>
            </tr>
            {_risk_rows_html}
          </table>
          <p style="margin:10px 0 0;font-size:11px;color:#999">
            ⚠️ Los resultados no incluyen comisiones, spread de compra/venta ni diferencia entre precio teórico y ejecutado.
          </p>
        </div>
        """
    else:
        _risk_table_html = ""

    # Pre-computar triggers de rebalanceo
    triggers = rec.get("rebalance_triggers", [])
    if triggers:
        _trigger_items = "".join(f"<li style='margin-bottom:6px'>{t}</li>" for t in triggers)
        _triggers_html = f"""
        <div style="padding:20px;background:#f3f8ff;border:1px solid #90caf9;margin-top:2px">
          <h3 style="color:#1565c0;margin:0 0 10px">🔁 Cuándo rebalancear</h3>
          <ul style="margin:0;padding-left:20px;color:#333;font-size:13px;line-height:1.7">{_trigger_items}</ul>
        </div>
        """
    else:
        _triggers_html = ""

    # Pre-computar sección USD breakdown para evitar lógica compleja dentro del f-string
    usd_bd = rec.get("usd_exposure_breakdown", {})
    if usd_bd:
        _breakdown_row = f"""
        <tr><td colspan="2" style="padding-top:12px">
          <table style="width:100%;font-size:13px;color:#555">
            <tr>
              <td>💵 Dólar líquido (MEP)</td>
              <td style="text-align:right;font-weight:bold">{usd_bd.get('dolar_liquido_pct',0):.0f}%</td>
              <td style="width:14px"></td>
              <td>🏢 Renta corp. USD</td>
              <td style="text-align:right;font-weight:bold">{usd_bd.get('renta_corporativa_usd_pct',0):.0f}%</td>
              <td style="width:14px"></td>
              <td>🌎 Equity dolarizado</td>
              <td style="text-align:right;font-weight:bold">{usd_bd.get('equity_dolarizado_pct',0):.0f}%</td>
            </tr>
          </table>
        </td></tr>"""
    else:
        _breakdown_row = ""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;color:#222">

    <div style="background:#0d2137;color:white;padding:24px;border-radius:8px 8px 0 0">
      <h1 style="margin:0;font-size:22px">💰 Recomendación en Pesos Argentinos</h1>
      <p style="margin:8px 0 0;opacity:0.7;font-size:13px">
        Capital: <b>${capital:,.0f} ARS</b> &nbsp;·&nbsp;
        Riesgo: <b>{riesgo_label}</b> &nbsp;·&nbsp;
        Sistema de Agentes IA
      </p>
    </div>

    <div style="padding:16px 20px;background:#f0f4f8;border-left:4px solid #0066cc">
      <b>Contexto macro:</b> &nbsp;
      {infl_label_email}: <b>{f'{infl_m:.1f}%' if infl_m else 'N/A'}</b> &nbsp;·&nbsp;
      Dólar oficial: <b>${f'{usd:,.0f}' if usd else 'N/A'} ARS/USD</b>
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 12px">📊 Distribución recomendada</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr style="background:#1a1a2e;color:white">
          <th style="padding:10px;text-align:left">Instrumento</th>
          <th style="padding:10px;text-align:center">%</th>
          <th style="padding:10px;text-align:right">Monto ARS</th>
        </tr>
        {rows_html}
        <tr style="background:#e8f0fe;font-weight:bold">
          <td style="padding:10px;border:1px solid #ddd">TOTAL</td>
          <td style="padding:10px;border:1px solid #ddd;text-align:center">100%</td>
          <td style="padding:10px;border:1px solid #ddd;text-align:right">${capital:,.0f}</td>
        </tr>
      </table>
    </div>

    <div style="padding:20px;background:#f8f9fa;border:1px solid #e0e0e0;margin-top:2px">
      <table style="width:100%">
        <tr>
          <td style="vertical-align:top;width:50%;padding-right:10px">
            <b>🛡 Cobertura inflacionaria</b><br>
            <span style="font-size:22px;font-weight:bold;color:#1565c0">{rec.get('inflation_coverage_pct','?')}%</span>
            <span style="color:#555;font-size:13px"> del portafolio</span>
          </td>
          <td style="vertical-align:top;width:50%">
            <b>💵 Exposición dolarizada total</b><br>
            <span style="font-size:22px;font-weight:bold;color:#1b5e20">{rec.get('usd_exposure_pct','?')}%</span>
            <span style="color:#555;font-size:13px"> del portafolio</span>
          </td>
        </tr>
        {_breakdown_row}
      </table>
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 8px">📋 Estrategia</h3>
      <p style="margin:0;line-height:1.7;color:#333">{rec.get('strategy_summary','')}</p>
      <p style="margin:12px 0 0;font-size:13px;color:#555">
        <b>Horizonte:</b> {rec.get('time_horizon','?')} &nbsp;·&nbsp;
        <b>Próxima revisión:</b> {rec.get('review_in','?')}
      </p>
    </div>

    {_risk_table_html}

    {_triggers_html}

    {cedear_html}

    {merval_html}

    <div style="padding:20px;background:#fff3e0;border:1px solid #ffb74d;margin-top:2px;border-radius:0 0 8px 8px">
      <h3 style="color:#e65100;margin:0 0 8px">⚠️ Riesgo principal</h3>
      <p style="margin:0;color:#555;line-height:1.6">{rec.get('main_risk','')}</p>
    </div>

    <p style="text-align:center;color:#999;font-size:12px;margin-top:20px">
      Este análisis es generado automáticamente por IA y no constituye asesoramiento financiero.
      Siempre consultá con un profesional antes de invertir.
    </p>

    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ARS] Recomendación {riesgo.upper()} — ${capital:,.0f} ARS"
    msg["From"]    = email_user
    msg["To"]      = email_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
        print(f"✅ Email enviado a {email_user}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False


def send_portfolio_analysis_email(position_reports: list, thesis: dict, cash: dict, broker: str):
    """Email con el análisis del portafolio propio (analyze_portfolio.py)."""
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")
    if not email_user or not email_pass:
        print("⚠️  Email no configurado en .env — saltando envío.")
        return False

    action_label = {
        "hold":                "⏸ MANTENER",
        "sell":                "🔴 VENDER",
        "add":                 "🟢 COMPRAR MÁS",
        "reduce":              "🟡 REDUCIR",
        "stop_loss_triggered": "🚨 STOP LOSS",
        "sin_precio":          "❓ SIN PRECIO",
    }
    action_color = {
        "hold":  "#f57c00", "sell": "#c62828", "add": "#2e7d32",
        "reduce": "#f57c00", "stop_loss_triggered": "#b71c1c", "sin_precio": "#888",
    }
    type_icon = {
        "bono_argentino": "🇦🇷",
        "cedear":         "🌎",
    }

    rows_html = ""
    for r in sorted(position_reports, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("urgency", "low"), 2)):
        action  = r.get("action", "?")
        color   = action_color.get(action, "#555")
        label   = action_label.get(action, action.upper())
        pnl_pct = r.get("pnl_pct")
        pnl_str = f"{pnl_pct:+.1f}%" if pnl_pct is not None else "N/A"
        pnl_color = "#2e7d32" if (pnl_pct or 0) >= 0 else "#c62828"
        ticker  = r.get("ticker", "?")
        icon    = type_icon.get(r.get("asset_type", ""), "📊")
        alert   = r.get("key_alert", "")

        # Línea de detalle según tipo de activo
        if r.get("asset_type") == "bono_argentino":
            detail = f"Vencimiento: {r.get('maturity','?')} · {r.get('days_to_maturity','?')} días"
        elif r.get("asset_type") == "cedear":
            premium = r.get("premium_discount_pct")
            detail = f"Paridad: {f'{premium:+.1f}% vs teórico' if premium is not None else 'N/A'} · CCL implícito: ${r.get('ccl_implicit','?'):,.0f}" if isinstance(r.get('ccl_implicit'), (int, float)) else f"Score subyacente: {r.get('ceo_score','?')}/10"
        else:
            detail = f"Stop Loss: ${r.get('stop_loss','?')} · Take Profit: ${r.get('take_profit','?')}"

        rows_html += f"""
        <tr>
          <td style="padding:10px;border:1px solid #ddd;font-weight:bold">{icon} {ticker}</td>
          <td style="padding:10px;border:1px solid #ddd;color:{color};font-weight:bold">{label}</td>
          <td style="padding:10px;border:1px solid #ddd;color:{pnl_color};font-weight:bold;text-align:right">{pnl_str}</td>
          <td style="padding:10px;border:1px solid #ddd;text-align:center">{r.get('urgency','?').upper()}</td>
        </tr>
        <tr style="background:#f9f9f9">
          <td colspan="4" style="padding:8px 10px;border:1px solid #ddd;color:#555;font-size:13px">
            {detail}
            {'<br><b>⚠️ ' + alert + '</b>' if alert else ''}
          </td>
        </tr>
        """

    health_color = {"excellent": "#2e7d32", "good": "#388e3c", "warning": "#f57c00", "critical": "#c62828"}
    health_emoji = {"excellent": "✅", "good": "🟢", "warning": "🟡", "critical": "🔴"}
    health = thesis.get("portfolio_health", "warning")

    priority_html = ""
    urg_color = {"high": "#c62828", "medium": "#f57c00", "low": "#2e7d32"}
    for a in thesis.get("priority_actions", []):
        ticker_str = f"[{a['ticker']}] " if a.get("ticker") else ""
        c = urg_color.get(a.get("urgency", ""), "#555")
        priority_html += f"<li style='margin-bottom:8px;color:{c}'><b>{ticker_str}</b>{a.get('action','')}</li>"

    total_cost_ars  = sum(r.get("cost_basis_ars", 0) for r in position_reports)
    total_value_ars = sum(r.get("current_value_ars", 0) for r in position_reports)
    total_cost_usd  = sum(r.get("cost_basis_usd", 0) for r in position_reports)
    total_value_usd = sum(r.get("current_value_usd", 0) for r in position_reports)

    totals_html = ""
    if total_cost_usd:
        pnl_usd = total_value_usd - total_cost_usd
        pct_usd = pnl_usd / total_cost_usd * 100 if total_cost_usd else 0
        c = "#2e7d32" if pnl_usd >= 0 else "#c62828"
        totals_html += f"<p style='margin:4px 0'>Acciones USD: invertido <b>${total_cost_usd:,.2f}</b> → valor <b>${total_value_usd:,.2f}</b> &nbsp;<span style='color:{c}'><b>{pct_usd:+.1f}%</b></span></p>"
    if total_cost_ars:
        pnl_ars = total_value_ars - total_cost_ars
        pct_ars = pnl_ars / total_cost_ars * 100 if total_cost_ars else 0
        c = "#2e7d32" if pnl_ars >= 0 else "#c62828"
        totals_html += f"<p style='margin:4px 0'>Bonos/CEDEARs ARS: invertido <b>${total_cost_ars:,.0f}</b> → valor <b>${total_value_ars:,.0f}</b> &nbsp;<span style='color:{c}'><b>{pct_ars:+.1f}%</b></span></p>"
    if cash:
        totals_html += f"<p style='margin:4px 0;color:#555'>Cash: USD ${cash.get('USD',0):,.0f} &nbsp;·&nbsp; ARS ${cash.get('ARS',0):,.0f}</p>"

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;color:#222">

    <div style="background:#0d2137;color:white;padding:24px;border-radius:8px 8px 0 0">
      <h1 style="margin:0;font-size:22px">📂 Análisis de tu Portafolio — {broker}</h1>
      <p style="margin:8px 0 0;opacity:0.7;font-size:13px">
        {len(position_reports)} posición(es) &nbsp;·&nbsp; Sistema de Agentes IA
      </p>
    </div>

    <div style="padding:16px 20px;background:#f0f4f8;border-left:4px solid {health_color.get(health,'#888')}">
      <b>Estado general: {health_emoji.get(health,'❓')} {health.upper()}</b>
      &nbsp;·&nbsp; Diversificación: <b>{thesis.get('diversification_score','?')}/10</b><br>
      {totals_html}
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 12px">📊 Posiciones</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr style="background:#1a1a2e;color:white">
          <th style="padding:10px;text-align:left">Activo</th>
          <th style="padding:10px;text-align:left">Acción</th>
          <th style="padding:10px;text-align:right">P&amp;L</th>
          <th style="padding:10px;text-align:center">Urgencia</th>
        </tr>
        {rows_html}
      </table>
    </div>

    <div style="padding:20px;background:#f8f9fa;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 8px">📋 Resumen ejecutivo</h3>
      <p style="margin:0;line-height:1.7;color:#333">{thesis.get('portfolio_summary','')}</p>
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1a1a2e;margin:0 0 8px">🎯 Acciones prioritarias</h3>
      <ol style="color:#333;line-height:1.8;margin:0;padding-left:20px">{priority_html}</ol>
    </div>

    <div style="padding:20px;background:white;border:1px solid #e0e0e0;margin-top:2px">
      <h3 style="color:#1b5e20;margin:0 0 6px">💵 Cash</h3>
      <p style="margin:0;color:#333">{thesis.get('cash_recommendation','')}</p>
    </div>

    <div style="padding:20px;background:#fff3e0;border:1px solid #ffb74d;margin-top:2px;border-radius:0 0 8px 8px">
      <h3 style="color:#e65100;margin:0 0 8px">⚠️ Riesgo principal</h3>
      <p style="margin:0;color:#555;line-height:1.6">{thesis.get('main_risk','')}</p>
      <p style="margin:10px 0 0;font-size:13px;color:#777">
        <b>Próxima revisión:</b> {thesis.get('next_review','')}
      </p>
    </div>

    <p style="text-align:center;color:#999;font-size:12px;margin-top:20px">
      Este análisis es generado automáticamente por IA y no constituye asesoramiento financiero.
      Siempre consultá con un profesional antes de invertir.
    </p>

    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Mi Portafolio] {health_emoji.get(health,'?')} {health.upper()} — {len(position_reports)} posición(es)"
    msg["From"]    = email_user
    msg["To"]      = email_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
        print(f"✅ Email enviado a {email_user}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False

def send_price_alert_email(alerts: list) -> bool:
    """Email de alerta cuando un ticker toca stop loss, take profit, o se acerca al stop."""
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASSWORD")
    if not email_user or not email_pass:
        print("⚠️  Email no configurado — saltando envío.")
        return False

    ALERT_META = {
        "stop_hit":   {"label": "🚨 STOP LOSS TOCADO",      "color": "#b71c1c", "bg": "#ffebee"},
        "near_stop":  {"label": "⚠️ CERCA DEL STOP LOSS",   "color": "#e65100", "bg": "#fff3e0"},
        "target_hit": {"label": "✅ TAKE PROFIT ALCANZADO", "color": "#1b5e20", "bg": "#e8f5e9"},
    }

    priority = {"stop_hit": 0, "near_stop": 1, "target_hit": 2}
    alerts   = sorted(alerts, key=lambda a: priority.get(a["alert_type"], 9))

    subject_parts = [f"{a['ticker']} {ALERT_META.get(a['alert_type'],{}).get('label','?')}" for a in alerts]
    subject = f"[Alerta] {' | '.join(subject_parts[:3])}"

    rows_html = ""
    for a in alerts:
        meta        = ALERT_META.get(a["alert_type"], {"label": a["alert_type"], "color": "#555", "bg": "#fff"})
        pnl         = a.get("pnl_pct", 0)
        pnl_col     = "#2e7d32" if pnl >= 0 else "#c62828"
        dist_stop   = (a["current"] - a["stop"])   / a["stop"]   * 100
        dist_target = (a["target"] - a["current"]) / a["current"] * 100
        rows_html += f"""
        <div style="margin-bottom:16px;border-radius:8px;overflow:hidden;border:1px solid #ddd">
          <div style="background:{meta['color']};color:white;padding:12px 16px">
            <b style="font-size:18px">{a['ticker']}</b>&nbsp;&nbsp;
            <span style="font-size:14px">{meta['label']}</span>
          </div>
          <div style="background:{meta['bg']};padding:14px 16px">
            <table style="width:100%;font-size:14px">
              <tr><td style="padding:4px 0;color:#555">Precio actual</td>
                  <td style="text-align:right;font-weight:bold;font-size:16px">${a['current']:,.2f}</td></tr>
              <tr><td style="padding:4px 0;color:#555">Entrada (análisis)</td>
                  <td style="text-align:right">${a['entry']:,.2f}</td></tr>
              <tr><td style="padding:4px 0;color:#555">P&amp;L desde análisis</td>
                  <td style="text-align:right;color:{pnl_col};font-weight:bold">{pnl:+.1f}%</td></tr>
              <tr><td colspan="2"><hr style="border:none;border-top:1px solid #ddd;margin:6px 0"></td></tr>
              <tr><td style="padding:4px 0;color:#c62828">🛑 Stop Loss</td>
                  <td style="text-align:right;color:#c62828">${a['stop']:,.2f}
                    <span style="font-size:12px;color:#888">({dist_stop:+.1f}% desde actual)</span></td></tr>
              <tr><td style="padding:4px 0;color:#2e7d32">🎯 Take Profit</td>
                  <td style="text-align:right;color:#2e7d32">${a['target']:,.2f}
                    <span style="font-size:12px;color:#888">({dist_target:+.1f}% hasta aquí)</span></td></tr>
              <tr><td style="padding:4px 0;color:#555">Score CEO</td>
                  <td style="text-align:right">{a.get('score','?')}/10 — veredicto: <b>{(a.get('verdict') or '?').upper()}</b>
                    (análisis del {a.get('analysis_date','?')})</td></tr>
            </table>
          </div>
        </div>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#222">
    <div style="background:#1a1a2e;color:white;padding:20px 24px;border-radius:8px 8px 0 0">
      <h1 style="margin:0;font-size:20px">📡 Alertas de Precio</h1>
      <p style="margin:6px 0 0;opacity:0.7;font-size:13px">{len(alerts)} alerta(s) · Investment Agent</p>
    </div>
    <div style="padding:20px;background:white;border:1px solid #e0e0e0">{rows_html}</div>
    <div style="padding:14px 20px;background:#f5f5f5;border:1px solid #e0e0e0;border-radius:0 0 8px 8px">
      <p style="margin:0;font-size:12px;color:#888">
        Alertas automáticas del Investment Agent. No constituyen asesoramiento financiero.
      </p>
    </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_user
    msg["To"]      = email_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_user, msg.as_string())
        print(f"✅ Email de alertas enviado a {email_user}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email de alertas: {e}")
        return False
