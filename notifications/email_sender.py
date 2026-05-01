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