from build_svg import prepare_image, image_to_ascii
from pathlib import Path

img = prepare_image(Path("assets/foto.jpg"))
pixels = list(img.getdata())
print("Min pixel:", min(pixels))
print("Max pixel:", max(pixels))
print("Avg pixel:", sum(pixels)/len(pixels))
