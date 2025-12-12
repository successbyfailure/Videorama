#!/usr/bin/env python3
"""
Script para generar iconos PNG para la extensión de Chrome.
Requiere Pillow (PIL): pip install Pillow
"""

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow no está instalado.")
    print("Instálalo con: pip install Pillow")
    exit(1)

def create_icon(size):
    """Crea un icono simple para Videorama"""
    # Crear imagen con fondo verde
    img = Image.new('RGB', (size, size), color='#4CAF50')
    draw = ImageDraw.Draw(img)

    # Calcular proporciones
    padding = size // 8
    video_width = size - (padding * 4)
    video_height = video_width * 2 // 3

    # Calcular posición centrada verticalmente
    video_y = (size - video_height) // 2

    # Dibujar rectángulo de video (blanco)
    draw.rectangle(
        [padding * 2, video_y, padding * 2 + video_width, video_y + video_height],
        fill='white'
    )

    # Dibujar triángulo de play (verde) en el centro del rectángulo
    play_size = video_height // 3
    play_x = padding * 2 + video_width // 2 - play_size // 3
    play_y = video_y + video_height // 2

    play_triangle = [
        (play_x, play_y - play_size // 2),
        (play_x, play_y + play_size // 2),
        (play_x + play_size, play_y)
    ]
    draw.polygon(play_triangle, fill='#4CAF50')

    return img

if __name__ == '__main__':
    # Generar iconos en diferentes tamaños
    sizes = [16, 48, 128]

    for size in sizes:
        icon = create_icon(size)
        filename = f'icon{size}.png'
        icon.save(filename)
        print(f'Generado: {filename}')

    print('\nIconos generados correctamente.')
