# Skill: code-inspection

Entender código antes de cambiarlo, gastando el mínimo de tokens.

## Pasos
1. Leer `context/module-map.md` → identificar archivos candidatos.
2. Grep por símbolo/término; Glob por patrón de ruta. No listar árboles completos.
3. Leer solo rangos relevantes (función + llamadores directos + test asociado).
4. Trazar el contrato: entradas, salidas, efectos secundarios (red, órdenes, disco).
5. Anotar discrepancias con `context/` → corregir contexto (skill `context-update`).

## Salida esperada
- 3–8 viñetas: dónde está, qué hace, quién lo llama, riesgos, tests existentes.

## Anti-patrones
- Abrir archivos >400 líneas enteros. · Leer datos/logs completos. · Suponer rutas `PROPUESTA` como existentes sin verificar.
