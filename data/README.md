# Datos del simulador

`modelo_hc3.json` contiene el snapshot congelado de los resultados publicados por
`EconometriaA.ipynb`.

`econometria_snapshot.csv` se genera ejecutando `src/export_snapshot.py` en un
entorno autenticado contra Snowflake. No se incluye un CSV inventado ni se
reconstruyen las filas omitidas por la vista truncada del notebook.

El exportador también crea `econometria_snapshot.metadata.json` con fecha,
cantidad de filas y SHA-256 del archivo.

