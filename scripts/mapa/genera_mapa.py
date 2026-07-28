import pandas as pd
import folium
from folium import plugins
import webbrowser
import os
import subprocess
import time

# Leer el archivo CSV con los datos de lugares
df = pd.read_csv('../../maestros/lugar.csv')

# Definir colores para cada condición climática
colores = {
    'frio': '#4285F4',      # Azul
    'calido': '#EA4335',    # Rojo
    'moderado': '#FBBC04'   # Naranja/Amarillo
}

# Crear el mapa centrado en las coordenadas promedio
lat_central = df['latitud'].mean()
lon_central = df['longitud'].mean()
mapa = folium.Map(
    location=[lat_central, lon_central],
    zoom_start=8,
    tiles='OpenStreetMap'
)

# Agregar marcadores para cada zona
for idx, row in df.iterrows():
    color = colores.get(row['condicion'].lower(), '#808080')
    
    # Crear popup con información de la zona
    popup_text = f"""
    <b>{row['nombre'].upper()}</b><br>
    Código: {row['codigo']}<br>
    Clima: {row['condicion'].upper()}<br>
    Latitud: {row['latitud']:.6f}<br>
    Longitud: {row['longitud']:.6f}
    """
    
    folium.Marker(
        location=[row['latitud'], row['longitud']],
        popup=folium.Popup(popup_text, max_width=250),
        tooltip=row['nombre'],
        icon=folium.Icon(
            color='white',
            icon_color=color,
            prefix='fa',
            icon='circle'
        )
    ).add_to(mapa)
    
    # Agregar etiqueta de texto con el nombre de la zona
    html = f"""
    <div style="font-size: 12px; color: {color}; font-weight: bold; 
                 text-shadow: 1px 1px 1px white, -1px -1px 1px white, 
                             1px -1px 1px white, -1px 1px 1px white;">
        {row['nombre']}
    </div>
    """
    folium.Marker(
        location=[row['latitud'], row['longitud']],
        icon=folium.DivIcon(html=html)
    ).add_to(mapa)

# Agregar una leyenda mejorada
leyenda_html = '''
<div style="position: fixed; 
     bottom: 50px; right: 50px; width: 250px; height: auto; 
     background-color: white; border:2px solid grey; z-index:9999; 
     font-size:13px; padding: 12px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.3);">
     
     <p style="margin: 0 0 12px 0; font-size: 15px;"><b>Leyenda climática</b></p>
     
     <p style="margin: 8px 0;">
        <i class="fa fa-circle" style="color:#4285F4; margin-right: 8px;"></i> <b>Frío</b>
     </p>
     
     <p style="margin: 8px 0;">
        <i class="fa fa-circle" style="color:#EA4335; margin-right: 8px;"></i> <b>Cálido</b>
     </p>
     
     <p style="margin: 8px 0;">
        <i class="fa fa-circle" style="color:#FBBC04; margin-right: 8px;"></i> <b>Moderado</b>
     </p>
     
     <hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">
     
     <p style="margin: 8px 0; font-size: 11px; color: #666;">
        💡 Haz clic en los indicadores para más información
     </p>
</div>
'''

# Agregar botón para exportar a PNG
export_button_html = '''
<div style="position: fixed; 
     bottom: 50px; left: 50px; width: auto; height: auto; 
     background-color: #4285F4; border:none; z-index:9999; 
     font-size:13px; padding: 10px 15px; border-radius: 5px; 
     box-shadow: 0 0 10px rgba(0,0,0,0.3);">
     <a href="#" onclick="exportarPNG(); return false;" 
        style="color: white; text-decoration: none; font-weight: bold; cursor: pointer;">
        📥 Exportar a PNG
     </a>
</div>

<script>
function exportarPNG() {
    // Usar leaflet-image para exportar
    alert('Para exportar a PNG:\\n\\n1. Presiona F12 (Herramientas del desarrollador)\\n2. Ve a la consola\\n3. Copia y pega este código:\\n\\nleafletImage(map, function(err, canvas) {\\n  var img = document.createElement("img");\\n  img.src = canvas.toDataURL();\\n  var link = document.createElement("a");\\n  link.href = img.src;\\n  link.download = "mapa_zonas.png";\\n  link.click();\\n});\\n\\nOUse una extensión del navegador como "Save Web Page as Image"');
}

// Función alternativa más fácil
function descargarMapa() {
    var canvas = document.querySelector('canvas');
    if (canvas) {
        var img = canvas.toDataURL();
        var link = document.createElement('a');
        link.href = img;
        link.download = 'mapa_zonas.png';
        link.click();
    }
}
</script>
'''

mapa.get_root().html.add_child(folium.Element(leyenda_html))
mapa.get_root().html.add_child(folium.Element(export_button_html))

# Guardar el mapa
output_file = 'mapa_zonas.html'
mapa.save(output_file)
print(f"✓ Mapa generado exitosamente: {output_file}")
print(f"✓ El mapa muestra los nombres de las zonas sin necesidad de hacer clic")
print(f"\n📋 Para exportar a PNG (método recomendado):")
print(f"  1. Instala: pip install selenium pillow")
print(f"  2. Asegúrate de tener Firefox instalado")
print(f"  3. Ejecuta: python exportar_png.py")

# Opcionalmente, abrir el mapa en el navegador
try:
    webbrowser.open('file://' + os.path.realpath(output_file))
    print(f"\n✓ Mapa abierto en el navegador")
except:
    print(f"\nPara ver el mapa, abre: {os.path.realpath(output_file)}")

