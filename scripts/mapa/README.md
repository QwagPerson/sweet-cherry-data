# 🗺️ Generador de Mapa Interactivo - Zonas Climáticas

Un script Python que genera un mapa interactivo con las 8 zonas de cultivo, mostrando sus nombres directamente en el mapa y clasificadas por tipo de clima.

## 📋 Características

✅ **Nombres visibles sin hacer clic** - Cada zona muestra su nombre directamente en el mapa  
✅ **Colores por clima** - Código de colores para identificar rápidamente:
   - 🔵 Azul = Frío (Los Niches, Teno Montaña)
   - 🔴 Rojo = Cálido (Melipilla, Pichidegua)
   - 🟠 Naranja = Moderado (Sarmiento, Teno Oriente, Teno Poniente, Viluco)

✅ **Información detallada** - Haz clic en cualquier marcador para ver:
   - Nombre completo de la zona
   - Código identificador
   - Tipo de clima
   - Coordenadas exactas (latitud y longitud)

✅ **Fácil exportación** - Múltiples opciones para guardar:
   - Screenshot automático
   - Exportar a PNG/PDF desde el navegador
   - Captura de pantalla del sistema

## 🚀 Uso Rápido

### 1. Generar el mapa
```bash
python genera_mapa.py
```

Este comando:
- Lee los datos de `lugar.csv`
- Genera `mapa_zonas.html`
- Abre automáticamente el mapa en tu navegador

### 2. Exportar a PNG

#### **Opción A: Screenshot simple (MÁS FÁCIL)**
1. El mapa ya está en tu navegador
2. Presiona: **Windows + Shift + S**
3. Dibuja el área del mapa
4. Se guarda automáticamente en portapapeles

#### **Opción B: Script de exportación**
```bash
python exportar_png.py
```

#### **Opción C: Herramientas del navegador**
1. Con el mapa abierto, presiona **Ctrl+P**
2. Selecciona "Guardar como PDF"
3. O instala una extensión como "FireShot" para PNG

## 📦 Instalación de dependencias

```bash
# Dependencias obligatorias (ya deberían estar instaladas)
pip install pandas folium

# Opcional: Para exportación automática a PNG
pip install html2image
```

## 📁 Archivos

```
D:\Data\FIA_2025\silver\maestros\
├── genera_mapa.py          # Script principal
├── exportar_png.py         # Script para exportar a PNG
├── mapa_zonas.html         # Mapa generado (abierto en navegador)
├── mapa_zonas.png          # Imagen capturada (si se exporta)
├── lugar.csv               # Datos de zonas
├── tratamiento.csv         # Datos de tratamientos
├── variedad.csv            # Datos de variedades
└── README.md               # Este archivo
```

## 🗺️ Zonas incluidas

| # | Nombre | Código | Clima | Ubicación |
|---|---|---|---|---|
| 1 | Los Niches | NIC | Frío | -35.037, -71.190 |
| 2 | Melipilla | MEL | Cálido | -33.756, -71.169 |
| 3 | Pichidegua | PIC | Cálido | -34.344, -71.317 |
| 4 | Sarmiento | SAR | Moderado | -34.944, -71.220 |
| 5 | Teno Montaña | TEM | Frío | -34.911, -71.029 |
| 6 | Teno Oriente | TEO | Moderado | -34.917, -71.054 |
| 7 | Teno Poniente | TEP | Moderado | -34.889, -71.228 |
| 8 | Viluco | VIL | Moderado | -33.777, -70.762 |

## 💡 Consejos

- **Para dar zoom**: Usa la rueda del mouse o los controles del mapa
- **Para mover**: Arrastra con el mouse
- **Para más información**: Haz clic en los marcadores (círculos de color)
- **Para exportar rápido**: Usa Windows + Shift + S en lugar de scripts

## 🛠️ Personalización

Si deseas modificar el script:
- Cambia los colores en el diccionario `colores`
- Ajusta el nivel de zoom inicial con `zoom_start`
- Modifica los estilos de la leyenda en el HTML

## 📧 Soporte

Si tienes problemas:
1. Asegúrate de que `lugar.csv` existe en la carpeta
2. Verifica que tengas Python 3.7+
3. Instala las dependencias: `pip install pandas folium`

---

**Última actualización**: 2026-05-12  
**Versión**: 1.1

