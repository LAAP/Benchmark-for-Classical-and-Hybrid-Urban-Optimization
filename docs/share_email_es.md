## Plantilla de email (ES) para compartir el repo + demo

Asunto: Benchmark urbano (CP-SAT vs híbrido QUBO) + demo toy

Hola,

Te comparto este repositorio: **[PEGAR LINK GITHUB]**

Incluye un framework de benchmarking para comparar un baseline clásico (OR-Tools CP-SAT) con un workflow híbrido tipo QUBO en instancias urbanas discretizadas. Gran parte del trabajo hasta ahora se ha centrado en que el benchmark sea **científicamente interpretable** (etiquetas de fairness, metadatos de comparabilidad/densidad, banderas de certificación y diagnósticos estructurales).

Demo (toy-only): **[PEGAR LINK DEMO]**  
Docs clave: **[PEGAR LINK DOCS]** (recomiendo `docs/methodology.md`, `docs/current_findings.md` y `docs/demo_guide.md`)

Notas importantes:
- Esto es un **framework de benchmark/demo**, no un producto.
- **No** afirma *quantum advantage*.
- La mayoría de comparaciones son **aproximadas**, no paridad exacta.
- El régimen `toy` es utilizable con cautelas; `small` sigue siendo un régimen duro/diagnóstico bajo la formulación discreta actual.

Si puedes, me vendría muy bien feedback sobre:
- claridad de las etiquetas de fairness y certificación,
- si la UI guía bien el orden de lectura (readiness → fairness/comparabilidad → certificación → KPIs),
- y cualquier mejora de reproducibilidad/documentación.

Gracias,
[TU NOMBRE]

