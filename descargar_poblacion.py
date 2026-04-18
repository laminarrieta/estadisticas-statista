"""
descargar_poblacion.py
----------------------
Descarga estadisticas de poblacion equivalentes a las que publica Statista
usando fuentes abiertas y oficiales (Banco Mundial y UN Population Division).

Por que NO Statista directamente:
  - Statista tiene sus datos detras de un paywall y sus Terminos de Servicio
    prohiben el scraping automatizado. La mayoria de sus graficos de poblacion
    se basan en datos del Banco Mundial / ONU, que son publicos y gratuitos.
  - La API del Banco Mundial es gratis, no requiere clave y cubre las mismas
    series que Statista usa como fuente.

Que descarga este script:
  1. Poblacion mundial y ranking de paises (ultimo ano disponible)
  2. Piramide de edad / demografia (0-14, 15-64, 65+, natalidad, mortalidad,
     esperanza de vida)
  3. Espana en detalle (serie historica 1960-actual de los indicadores clave)
  4. Urbanizacion y migracion neta

Salida:
  estadisticas_poblacion.xlsx con una hoja por categoria.

Uso:
  pip install requests pandas openpyxl
  python descargar_poblacion.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------- #
# Configuracion
# --------------------------------------------------------------------------- #

WB_BASE = "https://api.worldbank.org/v2"
# Paises a consultar en la hoja "Espana y comparables"
PAISES_FOCO = ["ESP", "DEU", "FRA", "ITA", "PRT", "GBR", "USA", "WLD"]

# Indicadores del Banco Mundial equivalentes a los que usa Statista
INDICADORES = {
    # Totales
    "SP.POP.TOTL":       "Poblacion total",
    "SP.POP.GROW":       "Crecimiento poblacion (% anual)",
    "EN.POP.DNST":       "Densidad (hab./km2)",

    # Piramide / demografia
    "SP.POP.0014.TO.ZS": "Poblacion 0-14 anos (%)",
    "SP.POP.1564.TO.ZS": "Poblacion 15-64 anos (%)",
    "SP.POP.65UP.TO.ZS": "Poblacion 65+ anos (%)",
    "SP.DYN.CBRT.IN":    "Tasa natalidad (por 1.000)",
    "SP.DYN.CDRT.IN":    "Tasa mortalidad (por 1.000)",
    "SP.DYN.TFRT.IN":    "Fecundidad (hijos por mujer)",
    "SP.DYN.LE00.IN":    "Esperanza de vida al nacer (anos)",

    # Urbanizacion y migracion
    "SP.URB.TOTL.IN.ZS": "Poblacion urbana (%)",
    "SP.URB.GROW":       "Crecimiento poblacion urbana (% anual)",
    "SM.POP.NETM":       "Migracion neta (5 anos)",
}

ANIO_INICIO_HISTORICO = 1960
ANIO_FIN_HISTORICO    = 2024   # la API devuelve solo lo disponible

SALIDA = Path(__file__).with_name("estadisticas_poblacion.xlsx")


# --------------------------------------------------------------------------- #
# Capa de acceso a la API del Banco Mundial
# --------------------------------------------------------------------------- #

def wb_get(endpoint: str, params: dict | None = None) -> list[dict]:
    """Llama a la API del Banco Mundial paginando hasta agotar los resultados."""
    params = dict(params or {})
    params.setdefault("format", "json")
    params.setdefault("per_page", 20000)

    url = f"{WB_BASE}/{endpoint.lstrip('/')}"
    for intento in range(3):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            # La API devuelve [metadata, filas]; si no hay filas, [metadata, None]
            if isinstance(data, list) and len(data) == 2:
                return data[1] or []
            return []
        except (requests.RequestException, ValueError) as e:
            if intento == 2:
                raise
            print(f"  ! reintento {intento + 1} tras error: {e}", file=sys.stderr)
            time.sleep(2 * (intento + 1))
    return []


def descargar_indicador(indicador: str, paises: str = "all",
                        fecha: str | None = None) -> pd.DataFrame:
    """Devuelve un DataFrame largo: pais, iso3, anio, valor."""
    params = {}
    if fecha:
        params["date"] = fecha
    filas = wb_get(f"country/{paises}/indicator/{indicador}", params)
    registros = []
    for f in filas:
        if f.get("value") is None:
            continue
        registros.append({
            "pais":  f["country"]["value"],
            "iso3":  f["countryiso3code"] or f["country"]["id"],
            "anio":  int(f["date"]),
            "valor": f["value"],
        })
    return pd.DataFrame(registros)


# --------------------------------------------------------------------------- #
# Construccion de cada hoja
# --------------------------------------------------------------------------- #

def hoja_poblacion_mundial() -> pd.DataFrame:
    """Ranking de paises + totales regionales del ultimo ano disponible."""
    print("1/4  Poblacion mundial y ranking por pais...")
    # Pedimos los ultimos 5 anos y nos quedamos con el mas reciente que tenga dato
    df = descargar_indicador("SP.POP.TOTL", paises="all",
                             fecha=f"{ANIO_FIN_HISTORICO - 4}:{ANIO_FIN_HISTORICO}")
    if df.empty:
        return df
    ultimo = df.sort_values("anio").groupby("iso3").tail(1)
    ultimo = ultimo.rename(columns={"valor": "poblacion"})
    ultimo["poblacion"] = ultimo["poblacion"].astype("Int64")
    ultimo = ultimo.sort_values("poblacion", ascending=False).reset_index(drop=True)
    ultimo.insert(0, "rank", range(1, len(ultimo) + 1))
    return ultimo[["rank", "pais", "iso3", "anio", "poblacion"]]


def hoja_piramide_edad() -> pd.DataFrame:
    """Reparto 0-14 / 15-64 / 65+ + natalidad, mortalidad, esperanza de vida."""
    print("2/4  Piramide de edad y demografia...")
    indicadores = {
        "SP.POP.0014.TO.ZS": "pct_0_14",
        "SP.POP.1564.TO.ZS": "pct_15_64",
        "SP.POP.65UP.TO.ZS": "pct_65_mas",
        "SP.DYN.CBRT.IN":    "natalidad_por_1000",
        "SP.DYN.CDRT.IN":    "mortalidad_por_1000",
        "SP.DYN.LE00.IN":    "esperanza_vida",
        "SP.DYN.TFRT.IN":    "fecundidad",
    }
    frames = []
    for cod, nombre in indicadores.items():
        d = descargar_indicador(cod, paises="all",
                                fecha=f"{ANIO_FIN_HISTORICO - 4}:{ANIO_FIN_HISTORICO}")
        if d.empty:
            continue
        d = d.sort_values("anio").groupby("iso3").tail(1)
        d = d.rename(columns={"valor": nombre})[["pais", "iso3", "anio", nombre]]
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f.drop(columns=["pais", "anio"]), on="iso3", how="outer")
    # Redondeos
    for col in out.columns:
        if col not in ("pais", "iso3", "anio"):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out.sort_values("pais").reset_index(drop=True)


def hoja_paises_foco() -> pd.DataFrame:
    """Serie historica larga para Espana y paises de referencia."""
    print(f"3/4  Serie historica {ANIO_INICIO_HISTORICO}-{ANIO_FIN_HISTORICO} "
          f"para {', '.join(PAISES_FOCO)}...")
    paises_str = ";".join(PAISES_FOCO)
    fecha = f"{ANIO_INICIO_HISTORICO}:{ANIO_FIN_HISTORICO}"
    frames = []
    for cod, etiqueta in INDICADORES.items():
        d = descargar_indicador(cod, paises=paises_str, fecha=fecha)
        if d.empty:
            continue
        d["indicador"] = etiqueta
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    largo = pd.concat(frames, ignore_index=True)
    # Pivotamos: filas = pais+anio, columnas = indicador
    ancho = (largo.pivot_table(index=["pais", "iso3", "anio"],
                               columns="indicador", values="valor",
                               aggfunc="first")
                   .reset_index()
                   .sort_values(["pais", "anio"]))
    ancho.columns.name = None
    return ancho


def hoja_urbanizacion_migracion() -> pd.DataFrame:
    """Ultima foto: % urbano, crecimiento urbano, migracion neta por pais."""
    print("4/4  Urbanizacion y migracion...")
    indicadores = {
        "SP.URB.TOTL.IN.ZS": "pct_poblacion_urbana",
        "SP.URB.GROW":       "crecimiento_urbano_pct",
        "SM.POP.NETM":       "migracion_neta_5_anos",
    }
    frames = []
    for cod, nombre in indicadores.items():
        d = descargar_indicador(cod, paises="all",
                                fecha=f"{ANIO_FIN_HISTORICO - 6}:{ANIO_FIN_HISTORICO}")
        if d.empty:
            continue
        d = d.sort_values("anio").groupby("iso3").tail(1)
        d = d.rename(columns={"valor": nombre})[["pais", "iso3", "anio", nombre]]
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f.drop(columns=["pais", "anio"]), on="iso3", how="outer")
    for col in out.columns:
        if col not in ("pais", "iso3", "anio"):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out.sort_values("pct_poblacion_urbana", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Escritura del Excel
# --------------------------------------------------------------------------- #

def escribir_excel(hojas: dict[str, pd.DataFrame], ruta: Path) -> None:
    print(f"\nEscribiendo {ruta.name} ...")
    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        # Portada
        portada = pd.DataFrame({
            "Campo":  ["Titulo", "Generado", "Fuente", "Cobertura", "Hojas"],
            "Valor":  [
                "Estadisticas de poblacion (equivalente a graficos Statista)",
                pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "Banco Mundial - World Development Indicators (api.worldbank.org)",
                f"Paises miembros + agregados regionales, {ANIO_INICIO_HISTORICO}-{ANIO_FIN_HISTORICO}",
                ", ".join(hojas.keys()),
            ],
        })
        portada.to_excel(writer, sheet_name="Portada", index=False)

        for nombre, df in hojas.items():
            if df is None or df.empty:
                pd.DataFrame({"aviso": ["Sin datos devueltos por la API"]}).to_excel(
                    writer, sheet_name=nombre[:31], index=False)
                continue
            df.to_excel(writer, sheet_name=nombre[:31], index=False)

        # Auto-ajuste de ancho de columna
        for ws in writer.book.worksheets:
            for col in ws.columns:
                max_len = max((len(str(c.value)) for c in col if c.value is not None),
                              default=10)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    print(f"Descargando datos del Banco Mundial -> {SALIDA.name}\n")
    hojas = {
        "Poblacion mundial":        hoja_poblacion_mundial(),
        "Piramide y demografia":    hoja_piramide_edad(),
        "Espana y comparables":     hoja_paises_foco(),
        "Urbanizacion y migracion": hoja_urbanizacion_migracion(),
    }
    escribir_excel(hojas, SALIDA)

    print("\nResumen:")
    for nombre, df in hojas.items():
        print(f"  - {nombre:<28} {len(df):>6} filas")
    print(f"\nListo: {SALIDA.resolve()}")


if __name__ == "__main__":
    main()
