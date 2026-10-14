# IEVR Save Editor (Linux)

Editor de partidas de **INAZUMA ELEVEN: Victory Road** (Steam) para Linux, con interfaz
gráfica. Edita el archivo de guardado con el juego cerrado: no toca la memoria del juego
ni el anticheat.

> *English summary below.*

> [!WARNING]
> Proyecto no oficial, sin relación con LEVEL-5. Pensado para el modo historia/offline:
> **no lo uses para obtener ventaja en el modo online**. Editar partidas puede corromperlas;
> el editor hace una copia antes de cada guardado, pero úsalo bajo tu responsabilidad.

## Funciones

| Sección | Qué se puede hacer |
|---|---|
| **Jugadores** | Nivel (hasta 99) y rareza de cada jugador y del avatar, también en bloque; equipamiento (botas, pulsera, accesorio, especial, ropa) y las 13 técnicas equipadas ⚗️ |
| **Objetos** | Cantidades de todo el inventario y añadir lo que no tienes: consumibles, judías de entrenamiento, botas, pulseras, accesorios, equipaciones, ropa, emblemas, tácticas especiales, títulos… |
| **Técnicas** | Supertécnicas (tiro, regate, defensa, portero), keshins, armaduras keshin, miximax, tótems, pasivas y modos |
| **Espíritus** | Normales por rareza (verde, azul, morado, amarillo, leyenda), héroe y basara ⚗️ |
| **Crónica** | Marcar partidos como superados hasta cualquiera de las 6 dificultades, uno a uno o en bloque |
| **Partida** | Nombre y apodo del avatar ⚗️, espíritus ficha, marcar personajes como conocidos en la base de datos ⚗️ |

⚗️ = experimental: funciona sobre el formato, pero aún no se ha comprobado a fondo en el juego.

Los nombres de objetos, personajes y técnicas se leen **de tu propia instalación del juego**
(en español); el editor no incluye ningún archivo del juego.

## Instalación

**Ejecutable:** descarga `ievr-save-editor-linux-x86_64` de
[Releases](../../releases), dale permisos (`chmod +x`) y ábrelo.

**Desde el código** (Python 3.12 o superior):

```sh
./build.sh      # compila dist/ievr-save-editor (un único ejecutable)
./install.sh    # lo copia a ~/.local/bin y lo añade al menú de aplicaciones
```

`./install.sh --uninstall` lo quita. Para ejecutarlo sin compilar: `./ievr-editor.sh`.

## Uso

1. **Cierra el juego** (el editor se niega a guardar si sigue abierto).
2. Abre el editor: detecta solo la partida
   (`~/.local/share/Steam/userdata/<id>/2799860/remote/002AB8F4-USERDATALIVE`) y el juego.
3. Edita y pulsa **Guardar** (`Ctrl+S`). La partida anterior se copia en
   `~/.local/share/ievr-editor/backups/` (se guardan las 20 últimas).
4. Si al abrir el juego Steam avisa de un conflicto de Steam Cloud, elige la versión **de este equipo**.

Probado con la versión 7.1.2 del juego en Steam (Proton).

## Cómo funciona

El formato se ha obtenido por ingeniería inversa del ejecutable del juego.

| Módulo | Qué hace |
|---|---|
| `crypto.py` | Keystream del juego (XOR derivado de CRC32) usado en partidas y CPK; la semilla de cada partida se recupera invirtiendo el CRC |
| `container.py` | Contenedor de la partida de Steam (cabecera, entradas, CRCs) |
| `l5bin.py` | Árbol binario etiquetado de LEVEL-5 dentro de la partida (lectura/escritura sin pérdidas) |
| `cpk.py`, `t2b.py`, `rdbn.py` | Lectura de los datos del juego (CPK de CRI con CRILAYLA, tablas `.cfg.bin`) |
| `gamedata.py`, `catalog.py` | Índice `cpk_list` y catálogo de todo lo obtenible |
| `editor.py`, `players.py` | Operaciones sobre la partida |
| `gui/` | Interfaz Qt (PySide6) |

Tests: `python -m pytest tests` (usan datos sintéticos, no hacen falta partidas).

## Créditos

- [Viola](https://github.com/SuperTavor/Viola) (SuperTavor) y
  [ievr_cfg_bin_editor](https://github.com/Telmo26/ievr_cfg_bin_editor) (Telmo26):
  referencia para los formatos CPK y RDBN.
- Formato T2B basado en el trabajo de la comunidad de LEVEL-5 (Tiniifan, onepiecefreak3, Togenyan).

## Licencia

[GPL-3.0](LICENSE).

---

## English summary

Linux save editor (Qt GUI) for **INAZUMA ELEVEN: Victory Road** on Steam. It edits the save
file while the game is closed: players (level, rarity, equipment, equipped techniques),
inventory, super techniques/keshins/miximax, spirits, Chronicle mode progress, avatar name.
Item and character names are read from your own game install. The UI is in Spanish.
Unofficial, not affiliated with LEVEL-5, meant for offline play. GPL-3.0.
