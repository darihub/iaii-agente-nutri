# Fase 4: Evaluación, optimización y despliegue

Pruebas mínimas recomendadas (tomadas del notebook original):

1. Hacer preguntas cuya respuesta esté explícitamente en los PDF.
2. Hacer preguntas cuya respuesta **no** aparezca en los PDF y verificar que el bot
   reconozca que no tiene información suficiente.
3. Inspeccionar los fragmentos recuperados y comprobar que realmente provengan del PDF
   y respondan a la consulta.
4. Verificar documento y página de origen; el prompt por sí solo no garantiza citas correctas.
5. Comparar embeddings experimental vs. baseline con las mismas preguntas.
6. Probar n8n con timeout, URL incorrecta, error HTTP y respuesta JSON/no JSON.

## Inspeccionar los fragmentos recuperados (punto 3 y 4)

```bash
python -m asistente.evaluacion "Escribí acá una pregunta de evaluación"
```

Imprime, por cada fragmento recuperado (k = 5), sus metadatos (archivo y página) y su
texto. No usa el LLM, así que no necesita clave de Groq.

## Comparar embeddings (punto 5)

Ejecutá la misma pregunta con cada modelo definiendo `EMBEDDING_MODEL`:

```bash
# Baseline (por defecto)
python -m asistente.evaluacion "tu pregunta"

# Experimental
EMBEDDING_MODEL=linhha2705/multilingual-e5-nutrition python -m asistente.evaluacion "tu pregunta"
# Windows PowerShell:  $env:EMBEDDING_MODEL="linhha2705/multilingual-e5-nutrition"; python -m asistente.evaluacion "tu pregunta"
```

## Hiperparámetros a ajustar (en `asistente/config.py`)

| Parámetro | Valor actual |
|---|---|
| `CHUNK_SIZE` | 800 |
| `CHUNK_OVERLAP` | 150 |
| `RETRIEVER_K` | 5 |
| `LLM_TEMPERATURE` | 0.2 |

## Probar n8n (punto 6)

Las pruebas automáticas de `tests/test_n8n_client.py` ya cubren timeout, error de conexión,
error HTTP y respuesta JSON/no JSON con un servidor simulado.
