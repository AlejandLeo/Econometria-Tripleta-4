# Simulador de beneficio social por mantenimiento vial

Aplicación local basada en el modelo HC3 del notebook `EconometriaA.ipynb`.
Permite explorar, en tiempo real, el beneficio social potencial asociado con un
ritmo mensual de reparación de semáforos y luminarias.

## Alcance metodológico

- El modelo original usa quejas mensuales, no reparaciones físicas.
- La aplicación convierte reparaciones en quejas evitadas equivalentes mediante
  factores visibles y editables.
- Los resultados son asociaciones históricas, no ahorros causales garantizados.
- La proyección anual supone que el ritmo ingresado se repite cada mes.

## Instalación en Windows PowerShell

```powershell
cd EconometriaNYC_DOT\simulador_ahorro_vial
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\run.ps1
```

## Exportar el snapshot desde Snowflake

Instale las dependencias opcionales:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-export.txt
```

Defina las variables descritas en `.env.example` en la sesión de PowerShell y
ejecute. El exportador carga automáticamente el archivo `.env` ubicado en la
raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe src\export_snapshot.py
```

La función `load_dotenv()` es la que lee el archivo. Después, `os.getenv()` y
`os.environ` consultan las variables que quedaron cargadas en memoria.
`.env.example` es únicamente una plantilla y nunca se lee automáticamente.

Para usar otro archivo de configuración:

```powershell
.\.venv\Scripts\python.exe src\export_snapshot.py --env-file C:\ruta\credenciales.env
```

Las variables definidas previamente en PowerShell tienen prioridad sobre los
valores de `.env`, porque el cargador usa `override=False`.

Con autenticación web, establezca `SNOWFLAKE_AUTHENTICATOR=externalbrowser` y no
defina una contraseña. El exportador crea:

- `data/econometria_snapshot.csv`
- `data/econometria_snapshot.metadata.json`

Elija un solo modo de autenticación:

- Navegador/SSO: `SNOWFLAKE_AUTHENTICATOR=externalbrowser` y
  `SNOWFLAKE_PASSWORD=` vacío. Aunque hubiera una contraseña, el exportador la
  ignora en este modo.
- Usuario y contraseña: deje `SNOWFLAKE_AUTHENTICATOR=` vacío y complete
  `SNOWFLAKE_PASSWORD`.

La aplicación detectará el archivo automáticamente y habilitará su descarga.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

El escenario de referencia valida 50 semáforos, 100 luminarias y USD 1,85
millones de costo operativo mensual.

