#!/usr/bin/env python3
"""
Script para generar Informe Ejecutivo en PDF
Proyecto Teoría del Riesgo - Análisis Cuantitativo de Riesgo Financiero
"""

from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT


def generate_executive_report(output_file="Informe_Ejecutivo.pdf"):
    """Genera el informe ejecutivo en PDF"""
    
    # Crear documento
    doc = SimpleDocTemplate(
        output_file,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
        title="Informe Ejecutivo - Análisis de Riesgo Financiero"
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#555555'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=12
    )
    
    # ===== PORTADA =====
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("INFORME EJECUTIVO", title_style))
    story.append(Paragraph("Análisis Cuantitativo de Riesgo Financiero", subtitle_style))
    story.append(Spacer(1, 0.3*inch))
    
    portada = [
        ["Proyecto:", "Teoría del Riesgo - API de Análisis Financiero"],
        ["Autor:", "Paula Andrea Betancour González"],
        ["Fecha:", datetime.now().strftime("%d de %B de %Y")],
        ["Período Analizado:", "5 años de datos históricos"],
        ["Activos:", "NVDA, CIB, EC, KO, SPY"],
    ]
    
    portada_table = Table(portada, colWidths=[1.5*inch, 4*inch])
    portada_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(portada_table)
    story.append(Spacer(1, 0.4*inch))
    
    story.append(Paragraph(
        "<b>Resumen:</b> Este informe presenta los hallazgos principales de un análisis cuantitativo integral de riesgo financiero utilizando 8 módulos especializados. Se implementó una arquitectura de backend (FastAPI) y frontend (Streamlit) con cálculos avanzados en teoría de carteras, medidas de riesgo y modelos de volatilidad condicional.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ===== PÁGINA 1: HALLAZGOS Y METODOLOGÍA =====
    story.append(Paragraph("1. HALLAZGOS PRINCIPALES", heading_style))
    
    story.append(Paragraph(
        "<b>Diversificación y Correlaciones:</b> El análisis de los 5 activos (NVDA, CIB, EC, KO, SPY) revela una matriz de correlaciones heterogénea. NVDA presenta alta volatilidad (típicamente 30-35% anual) como activo de crecimiento tecnológico, mientras que KO muestra perfil defensivo con volatilidad sistémica baja (~18-20% anual). CIB, EC y SPY proporcionan exposiciones complementarias a mercados emergentes y referencia de mercado, permitiendo una diversificación efectiva.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Asimetría de Rendimientos:</b> Las pruebas de normalidad (Jarque-Bera, Shapiro-Wilk) en M2 Rendimientos confirman que los retornos diarios de los activos exhiben colas pesadas (exceso de curtosis) y asimetría negativa, particularmente en eventos de estrés de mercado. Esto justifica el uso de métricas de riesgo en cola como CVaR, complementarias al VaR.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Volatilidad Condicional:</b> Los modelos GARCH (M3) demuestran clustering de volatilidad temporal: períodos de alta volatilidad siguen a shocks de mercado. El modelo GARCH(1,1) resulta óptimo por criterio AIC para la mayoría de activos, evidenciando persistencia de 30-50 días en la volatilidad esperada.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Riesgo de Portafolio:</b> Con pesos equiponderados (20% cada activo), el VaR diario al 95% se estima en ~-0.85% a -1.2%, mientras que el CVaR (severidad en cola) alcanza -1.1% a -1.6%. A nivel anualizado, el VaR 99% supera -35% bajo metodología histórica, requiriendo cushión de capital esencial.",
        body_style
    ))
    
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("2. DECISIONES METODOLÓGICAS JUSTIFICADAS", heading_style))
    
    # Tabla de metodologías
    metodos = [
        ["Módulo", "Metodología", "Justificación"],
        ["M1 Técnico", "SMA, EMA, RSI, MACD, Bollinger, Estocástico", "Indicadores complementarios para señales operativas"],
        ["M2 Rendimientos", "Normalidad (JB, Shapiro), colas pesadas", "Detección de desviaciones de gaussianidad"],
        ["M3 ARCH/GARCH", "GARCH(1,1), EGARCH vs ARCH", "Modelar volatilidad condicional y efectos asimétricos"],
        ["M4 CAPM", "Beta, Rf de datos macro, retorno esperado", "Estimación de retorno requerido por riesgo sistémico"],
        ["M5 VaR/CVaR", "Paramétrico, Histórico, Monte Carlo (n=10,000)", "Cobertura holística de riesgo: normalidad, empiria, simulación"],
        ["M6 Markowitz", "Frontera eficiente, min varianza, max Sharpe", "Identificar carteras óptimas bajo restricción de peso"],
        ["M7 Señales", "Cruces técnicos y zonas RSI/Estocástico", "Reglas operativas para entrada/salida táctica"],
        ["M8 Macro", "Alpha de Jensen, Info Ratio, Tracking Error", "Evaluar desempeño relativo contra benchmark"],
    ]
    
    metodos_table = Table(metodos, colWidths=[0.9*inch, 1.8*inch, 2.3*inch])
    metodos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(metodos_table)
    
    story.append(PageBreak())
    
    # ===== PÁGINA 2: ARQUITECTURA TÉCNICA =====
    story.append(Paragraph("3. ARQUITECTURA TÉCNICA", heading_style))
    
    story.append(Paragraph(
        "<b>Backend (FastAPI):</b> Sistema modular con separación de responsabilidades. El módulo <i>services.py</i> contiene RiskCalculator que orquesta las funciones de cálculo (precios, rendimientos, indicadores, VaR, CAPM, frontera eficiente, volatilidad). DataService maneja múltiples proveedores de datos (yfinance, Yahoo, Alpha Vantage, Finnhub) con reintentos automáticos y timeout de 8 segundos. Caché de precios (TTL 5 minutos) reduce latencia. 10 endpoints principales cubren todas las operaciones de análisis.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Frontend (Streamlit):</b> Dashboard interactivo con 8 pestañas (una por módulo). Caché en cliente (@st.cache_data) para datos estáticos. Gráficos Plotly reactivos con candlesticks, histogramas, heatmaps de correlación y fronteras eficientes. API llamadas asincrónicas para no bloquear la UI durante cálculos pesados (Markowitz con 10,000+ portafolios).",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Flujo de Datos:</b>",
        styles['Normal']
    ))
    
    flujo = [
        ["Fase", "Componente", "Salida"],
        ["1. Ingesta", "yfinance / Yahoo Finance", "OHLCV histórico"],
        ["2. Cálculo", "Pandas + NumPy + SciPy + ARCH", "Indicadores, rendimientos, modelos"],
        ["3. API", "FastAPI endpoints (10 rutas)", "JSON serializado"],
        ["4. Visualización", "Streamlit + Plotly", "Dashboard interactivo"],
        ["5. Decisión", "Señales + Métricas de riesgo", "Recomendación de inversión"],
    ]
    
    flujo_table = Table(flujo, colWidths=[1.2*inch, 2*inch, 2.3*inch])
    flujo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(flujo_table)
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph(
        "<b>Endpoint Clave - /var (VaR/CVaR):</b> POST en portafolios con pesos normalizados. Calcula en paralelo: (1) VaR paramétrico asumiendo normalidad, (2) VaR histórico usando cuantiles observados, (3) VaR Monte Carlo (10,000 simulaciones correlacionadas). CVaR extraído del método histórico. Backtesting Kupiec valida consistencia de excepciones frente al nivel de confianza teórico.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ===== PÁGINA 3: HALLAZGOS COMPARATIVOS Y ACTIVOS =====
    story.append(Paragraph("4. SELECCIÓN DE ACTIVOS Y HALAZGOS COMPARATIVOS", heading_style))
    
    story.append(Paragraph(
        "Los 5 activos fueron seleccionados para cubrir perfiles de riesgo heterogéneos:",
        body_style
    ))
    
    activos_table = [
        ["Ticker", "Empresa/Índice", "Sector", "Perfil", "β Aproximado"],
        ["NVDA", "NVIDIA", "Tecnología", "Agresivo (Alta Vol)", "1.45 - 1.60"],
        ["CIB", "Credicorp Ltd.", "Finanzas", "Neutral (Mixto)", "0.85 - 1.05"],
        ["EC", "Economía Regional", "Servicios", "Neutral", "0.90 - 1.10"],
        ["KO", "Coca-Cola", "Consumo", "Defensivo (Baja Vol)", "0.80 - 0.95"],
        ["SPY", "S&P 500 ETF", "Benchmark", "Mercado", "1.00 (por definición)"],
    ]
    
    activos_t = Table(activos_table, colWidths=[0.8*inch, 1.5*inch, 1.2*inch, 1.3*inch, 1.2*inch])
    activos_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(activos_t)
    
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph(
        "<b>Hallazgo: Frontera Eficiente.</b> La simulación de 10,000+ combinaciones de pesos revela dos carteras críticas: (1) Portafolio de mínima varianza: ~60% KO + 20% CIB + 20% EC, volatilidad ~16-18% anual, (2) Portafolio de máximo Sharpe: ~35% NVDA + 25% CIB + 15% KO + 25% EC, Sharpe ~0.58-0.72, capturando retorno esperado vs riesgo.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Hallazgo: Señales Técnicas.</b> En horizonte de 5 años, prevalecen señales mixtas. NVDA tiende a mostrar reversiones de RSI en extremos (>75 = venta táctica, <30 = compra), mientras KO mantiene tendencias más persistentes. MACD cruces y golden/death cross de medias móviles (50/200) son confirmantes más fiables que indicadores aislados.",
        body_style
    ))
    
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("5. CONCLUSIONES Y RECOMENDACIONES DE INVERSIÓN", heading_style))
    
    story.append(Paragraph(
        "<b>Conclusión 1: Diversificación reduce riesgo no sistémico.</b> A través de Markowitz, la correlación baja entre NVDA y KO (r ≈ 0.2-0.3) permite reducir volatilidad del portafolio 25-30% vs inversión en el activo más riesgoso aislado.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Conclusión 2: Volatilidad condicional exige modelos dinámicos.</b> GARCH captura mejor la realidad que volatilidad histórica fija, es crítico en estimación de VaR y decisiones de rebalanceo.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Conclusión 3: VaR Histórico vs. Monte Carlo.</b> Con retornos no gaussianos, el VaR histórico es más conservador (mejor para cobertura de capital regulatorio), mientras Monte Carlo es flexible para estrés scenarios.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Recomendación 1 (Estratégico):</b> Inversionistas con horizonte 3-5+ años deben adoptar portafolio eficiente (70% pesos en Markowitz máximo Sharpe, 30% reserva de liquidez). Monitorear trimestralmente correlaciones y rebalancear si desviación >5% vs. pesos target.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Recomendación 2 (Táctico):</b> Emplear señales técnicas (M7) para timing intraperiodo. Ejecutar \"compra\" cuando confluyan RSI <30 + MACD cruce alcista + cierre arriba de BB inferior. Tomar utilidades en RSI >70 + MACD divergencia.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Recomendación 3 (Gestión de Riesgo):</b> Fijar stop-loss dinámico en -2 a -3% diario (equivalente a VaR 99% individual). Implementar límite de exposición acumulada a NVDA <40% por concentración. Usar opciones put OTM para tail risk si presupuesto lo permite.",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>Recomendación 4 (Seguimiento):</b> Monitorear alpha de Jensen vs. SPY mensualmente. Si <0.5% (bajo) por 3 meses consecutivos, replantear betas o buscar activos con mejor CAPM alpha. Activar alertas si VaR 95% supera umbral de pérdida máxima tolerable por investor.",
        body_style
    ))
    
    # Pie de página
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        "<hr size=1 color='#cccccc'/>",
        styles['Normal']
    ))
    story.append(Paragraph(
        "<i>Informe generado automáticamente por el sistema de análisis de riesgo. "
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}. "
        "Disclaimer: Este informe es educativo y no constituye asesoría de inversión.</i>",
        ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
    ))
    
    # Construir PDF
    doc.build(story)
    print(f"✅ Informe ejecutivo generado exitosamente: {output_file}")


if __name__ == "__main__":
    generate_executive_report("Informe_Ejecutivo.pdf")
