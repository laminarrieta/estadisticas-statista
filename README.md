# estadisticas-statista

Script en Python que descarga las estadísticas de población equivalentes a las
que publica Statista, usando la **API abierta y gratuita del Banco Mundial**
(misma fuente primaria que Statista utiliza para la mayoría de sus gráficos
demográficos, pero sin paywall ni restricciones de ToS).

> Statista no permite scraping automatizado de su web y sus datos están detrás
> de paywall. Este repo va directo a la fuente pública: `api.worldbank.org`.

## Qué descarga

El script genera `estadisticas_poblacion.xlsx` con 5 hojas:

| Hoja                        | Contenido |
|-----------------------------|-----------|
| Portada                     | Metadatos de la ejecución (fecha, fuente, cobertura) |
| Población mundial           | Ranking de países por población total (último año disponible) |
| Pirámide y demografía       | Reparto 0‑14 / 15‑64 / 65+, natalidad, mortalidad, fecundidad, esperanza de vida |
| España y comparables        | Serie histórica 1960‑actual para ESP, DEU, FRA, ITA, PRT, GBR, USA y Mundo (12 indicadores) |
| Urbanización y migración    | % población urbana, crecimiento urbano y migración neta a 5 años |

## Uso local

```bash
pip install -r requirements.txt
python descargar_poblacion.py
```

Se creará `estadisticas_poblacion.xlsx` en el mismo directorio.

## Ejecución automática (GitHub Actions)

El workflow `.github/workflows/descarga-semanal.yml` ejecuta el script
**todos los viernes a las 15:00 hora de Madrid** y:

1. Sube el `.xlsx` como _artifact_ descargable desde la pestaña Actions.
2. Guarda una copia versionada en `data/estadisticas_poblacion_YYYY-MM-DD.xlsx`
   con _commit_ automático al repo.
3. Sobrescribe el `estadisticas_poblacion.xlsx` en la raíz con la última versión.

También se puede disparar a mano desde **Actions → Descarga semanal → Run workflow**.

### Nota sobre la zona horaria

GitHub Actions solo acepta _cron_ en UTC. Madrid cambia entre **CET (UTC+1)** en
invierno y **CEST (UTC+2)** en verano, así que el workflow define dos
programaciones para mantener las 15:00 locales todo el año:

- `0 13 * * 5` → 15:00 Madrid en horario de verano (CEST)
- `0 14 * * 5` → 15:00 Madrid en horario de invierno (CET)

GitHub ejecuta las dos; el script es idempotente y si corre dos veces el mismo
día solo se sobrescribe el fichero del día. Si prefieres una sola ejecución
puedes quedarte con la que te convenga según la época del año.

## Cómo publicar el repo en GitHub

```bash
cd estadisticas-statista
git init
git add .
git commit -m "Commit inicial"

# Con GitHub CLI:
gh repo create estadisticas-statista --public --source=. --push

# O manualmente (sustituye USUARIO):
git remote add origin https://github.com/USUARIO/estadisticas-statista.git
git branch -M main
git push -u origin main
```

Para que el commit automático del workflow funcione, el repo necesita permisos
de escritura del token por defecto:

**Settings → Actions → General → Workflow permissions → Read and write
permissions** (normalmente ya viene activado).

## Licencia

MIT
# estadisticas-statista
Descarga semanal de estadísticas de población (equivalentes a Statista) desde la API abierta del Banco Mundial.
