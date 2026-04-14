# Guion de Sustentacion (15-20 min)

## 1. Apertura (1 min)
- Problema: medir riesgo y apoyar decisiones de inversion.
- Solucion: plataforma con backend FastAPI + dashboard Streamlit.

## 2. Arquitectura (3 min)
- Mostrar separacion backend/frontend.
- Explicar por que la logica esta en API y no en frontend.
- Mostrar /docs (Swagger) y un ejemplo de request/response validado con Pydantic.

## 3. Demo funcional (8-10 min)
1. Modulo tecnico: SMA/EMA/RSI/MACD/Bollinger/Estocastico.
2. Modulo rendimientos: estadisticos, normalidad, interpretacion.
3. Modulo volatilidad: comparacion ARCH/GARCH por AIC/BIC.
4. CAPM: beta y rendimiento esperado con Rf dinamica.
5. VaR/CVaR: comparar metodos y explicar diferencia.
6. Markowitz: frontera eficiente, min varianza, max Sharpe.
7. Senales: reglas y semaforo de alertas.
8. Macro/benchmark: alpha, TE, IR, Sharpe, drawdown.

## 4. Preguntas tecnicas esperadas (4-5 min)
- Como validan que los pesos sumen 1.0?
- Que depende de Depends y por que?
- Que pasa cuando falla la API externa?
- Por que usar GARCH frente a varianza constante?
- Diferencia entre VaR y CVaR?
- Como interpretan alpha de Jensen?

## 5. Respuestas cortas recomendadas
- Validacion: @field_validator en modelo de request.
- Dependencias: desacoplar servicios, testing y mantenimiento.
- Errores externos: HTTPException con 503 y mensajes claros.
- GARCH: captura heterocedasticidad y clustering de volatilidad.
- VaR vs CVaR: VaR umbral; CVaR severidad promedio en cola.
- Alpha: exceso de retorno ajustado por riesgo sistematico.

## 6. Cierre (1 min)
- Resumen de valor: integra teoria + implementacion + interpretacion.
- Siguiente paso: backtesting Kupiec, pruebas automatizadas y despliegue nube.
