"""
Script para exportar el mapa interactivo HTML a PNG
Ofrece múltiples opciones de exportación
"""

import os
import time
import webbrowser
from pathlib import Path
import subprocess
import sys

def exportar_con_html2image():
    """Intenta exportar usando html2image (la mejor opción)"""
    try:
        from html2image import HtmlImage
        html_file = Path('mapa_zonas.html').absolute()

        if not html_file.exists():
            return False

        print("🌐 Usando html2image para exportar...")
        hti = HtmlImage(output_path=str(Path.cwd()))
        hti.screenshot(
            html_file=str(html_file),
            save_as='mapa_zonas.png',
            size=(1400, 900)
        )
        print(f"✓ Mapa exportado a: mapa_zonas.png")
        return True
    except:
        return False

def exportar_con_herramientas_navegador():
    """Abre el mapa en el navegador para exportar manualmente"""
    html_file = Path('mapa_zonas.html').absolute()

    if not html_file.exists():
        print(f"❌ Archivo no encontrado: {html_file}")
        return False

    print("=" * 60)
    print("📋 INSTRUCCIONES PARA EXPORTAR A PNG")
    print("=" * 60)
    print(f"\n✓ El mapa se abrirá automáticamente en tu navegador")
    print(f"\n📌 Opción 1 - Screenshot simple (RECOMENDADO):")
    print(f"   1. El mapa está abierto ↓")
    print(f"   2. Presiona: Windows + Shift + S (o Print Screen)")
    print(f"   3. Dibuja el área del mapa")
    print(f"   4. Se guarda automáticamente en portapapeles")
    print(f"\n📌 Opción 2 - Usar extensión de navegador:")
    print(f"   1. Instala 'FireShot' en Chrome/Firefox")
    print(f"   2. Haz clic en la extensión")
    print(f"   3. Elige 'Guardar como PNG'")
    print(f"\n📌 Opción 3 - Exportar a PDF:")
    print(f"   1. Presiona Ctrl+P")
    print(f"   2. Selecciona 'Guardar como PDF'")
    print(f"\n" + "=" * 60)

    webbrowser.open(f'file:///{html_file}')
    print("\n✓ Mapa abierto en el navegador")
    return True

def instalar_dependencias_exportacion():
    """Ofrece instalar dependencias para exportación automática"""
    print("\n💡 Para exportar automáticamente a PNG sin acciones manuales:")
    print("   Ejecuta: pip install html2image")
    print("   Luego ejecuta este script de nuevo")

if __name__ == "__main__":
    print("=" * 60)
    print("Exportador de Mapa a PNG")
    print("=" * 60)

    html_file = Path('mapa_zonas.html').absolute()

    if not html_file.exists():
        print(f"❌ Archivo no encontrado: {html_file}")
        print("Asegúrate de ejecutar 'python genera_mapa.py' primero")
        sys.exit(1)

    # Intentar con html2image primero
    print("\n🚀 Buscando métodos de exportación...")
    if not exportar_con_html2image():
        print("\n📌 html2image no disponible")
        instalar_dependencias_exportacion()
        print("\n" + "=" * 60)
        exportar_con_herramientas_navegador()

    print("\n" + "=" * 60)

