# IEVR Save Editor

Editor de partidas de **INAZUMA ELEVEN: Victory Road** (Steam) para **Linux y Windows**, con
interfaz gráfica, iconos de objetos y caras de personajes. Edita el archivo de guardado con el
juego cerrado: no toca la memoria del juego ni el anticheat.

> *English summary below.*

> [!WARNING]
> Proyecto no oficial, sin relación con LEVEL-5. Pensado para el modo historia/offline:
> **no lo uses para obtener ventaja en el modo online**. Editar partidas puede corromperlas;
> el editor hace una copia antes de cada guardado, pero úsalo bajo tu responsabilidad.

## Funciones

| Sección | Qué se puede hacer |
|---|---|
| **Jugadores** | Nivel (hasta 99) y rareza de cada jugador y del avatar, también en bloque; **entrenamiento con judías** (los 3 huecos, hasta el límite de su nivel) ⚗️; equipamiento (botas, pulsera, accesorio, especial, ropa) y las 13 técnicas equipadas ⚗️ |
| **Objetos** | Cantidades de todo el inventario y añadir lo que no tienes: consumibles, judías de entrenamiento, botas, pulseras, accesorios, equipaciones, ropa, emblemas, tácticas especiales, títulos… |
| **Técnicas** | Supertécnicas (tiro, regate, defensa, portero) con elemento, potencia y TP, keshins, armaduras keshin, miximax, tótems, pasivas y modos |
| **Espíritus** | Normales por rareza (verde, azul, morado, amarillo, leyenda), héroe y basara ⚗️ |
| **Crónica** | Marcar partidos como superados hasta cualquiera de las 6 dificultades, uno a uno o en bloque |
| **Partida** | Nombre y apodo del avatar ⚗️, espíritus ficha, marcar personajes como conocidos en la base de datos ⚗️, restaurar copias de seguridad, idioma |

Además: **Deshacer/Rehacer** (`Ctrl+Z` / `Ctrl+Y`), **resumen de los cambios** antes de guardar, aviso si
la partida es de una versión del juego más nueva que la probada y aviso de nuevas versiones del editor
(se puede desactivar). Interfaz en **español e inglés** (según el idioma del sistema).

⚗️ = experimental: funciona sobre el formato, pero aún no se ha comprobado a fondo en el juego.

Las tablas muestran el **icono de cada objeto** (equipamiento, consumibles, equipaciones, ropa,
emblemas, keshins…) y la **cara de cada jugador y espíritu**, sacados de tu instalación del juego.

Los nombres de objetos, personajes y técnicas se leen **de tu propia instalación del juego**,
en tu idioma; el editor no incluye ningún archivo del juego.

## Instalación

Descarga el ejecutable de [Releases](../../releases):

- **Windows:** `ievr-save-editor-windows-x64.exe` y ábrelo. Windows SmartScreen puede avisar
  porque el ejecutable no está firmado: «Más información» → «Ejecutar de todas formas».
- **Linux / Steam Deck:** `ievr-save-editor-linux-x86_64`, dale permisos (`chmod +x`) y ábrelo.

**Desde el código** (Python 3.12 o superior):

```sh
pip install -r requirements.txt -r requirements-dev.txt
python build.py          # compila dist/ievr-save-editor(.exe), un único ejecutable
python -m ievr_editor    # o ejecútalo directamente sin compilar
```

En Linux, `./build.sh` y `./install.sh` lo compilan y lo añaden al menú de aplicaciones
(`./install.sh --uninstall` lo quita).

## Uso

1. **Cierra el juego** (el editor se niega a guardar si sigue abierto).
2. Abre el editor. No hay que configurar nada:
   - Encuentra la partida en `Steam/userdata/<cuenta>/2799860/remote/002AB8F4-USERDATALIVE`
     (Windows, Linux, Steam Deck, Flatpak y Snap). Si hay **varias cuentas de Steam**, pregunta
     cuál abrir mostrando el nombre de cada una.
   - Encuentra el juego en cualquiera de tus bibliotecas de Steam. Si no lo encuentra, te pide
     la carpeta una vez y la recuerda.
   - Los nombres de objetos y personajes salen en el idioma de tu sistema si el juego lo
     tiene (español, inglés, francés, alemán, italiano, portugués…). La interfaz está en español
     o inglés; se puede cambiar en la página Partida.
3. Edita y pulsa **Guardar** (`Ctrl+S`). La partida anterior se copia en la carpeta de copias
   (se guardan las 20 últimas):
   - Linux: `~/.local/share/ievr-editor/backups/`
   - Windows: `%LOCALAPPDATA%\ievr-editor\backups\`
4. Si al abrir el juego Steam avisa de un conflicto de Steam Cloud, elige la versión **de este equipo**.

Probado con la versión 7.1.2 del juego en Steam bajo Linux (Proton). La versión de Windows
usa el mismo código y pasa los tests en Windows, pero aún no se ha probado con una partida real.

## Cómo funciona

El formato se ha obtenido por ingeniería inversa del ejecutable del juego.

| Módulo | Qué hace |
|---|---|
| `crypto.py` | Keystream del juego (XOR derivado de CRC32) usado en partidas y CPK; la semilla de cada partida se recupera invirtiendo el CRC |
| `container.py` | Contenedor de la partida de Steam (cabecera, entradas, CRCs) |
| `l5bin.py` | Árbol binario etiquetado de LEVEL-5 dentro de la partida (lectura/escritura sin pérdidas) |
| `cpk.py`, `t2b.py`, `rdbn.py` | Lectura de los datos del juego (CPK de CRI con CRILAYLA, tablas `.cfg.bin`) |
| `g4tx.py`, `icons.py` | Texturas G4TX (DDS/BC7) → iconos PNG en caché |
| `gamedata.py`, `catalog.py` | Índice `cpk_list` y catálogo de todo lo obtenible |
| `editor.py`, `players.py` | Operaciones sobre la partida |
| `gui/` | Interfaz Qt (PySide6) |

Tests: `python -m pytest tests` (usan datos sintéticos, no hacen falta partidas).

## Créditos

- [Viola](https://github.com/SuperTavor/Viola) (SuperTavor) y
  [ievr_cfg_bin_editor](https://github.com/Telmo26/ievr_cfg_bin_editor) (Telmo26):
  referencia para los formatos CPK y RDBN.
- [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2): estructura del formato G4TX.
- Formato T2B basado en el trabajo de la comunidad de LEVEL-5 (Tiniifan, onepiecefreak3, Togenyan).

## Licencia

[GPL-3.0](LICENSE).

---

## English summary

Save editor (Qt GUI, Linux and Windows, **English and Spanish interface**) for **INAZUMA ELEVEN: Victory
Road** on Steam, with item icons and character faces. Undo/redo, a summary before saving and backups you
can restore from the app. It edits the save file while the game is closed: players (level, rarity,
equipment, equipped techniques, bean training), inventory, super techniques/keshins/miximax with power
and element, spirits, Chronicle mode progress, avatar name.
Item and character names are read from your own game install, in your language.
Unofficial, not affiliated with LEVEL-5, meant for offline play. GPL-3.0.
