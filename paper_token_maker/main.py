import os
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

def process_images(image_dir):
    images = []
    for filename in os.listdir(image_dir):
        if filename.lower().endswith(('png', 'jpg', 'jpeg')):
            img_path = os.path.join(image_dir, filename)
            img = Image.open(img_path)
            img = img.resize((int(1.5 * img.info['dpi'][0]), int(2.5 * img.info['dpi'][1])))  # Resize image
            img_mirrored = ImageOps.flip(img)  # Mirror the image vertically
            combined_img = Image.new('RGB', (img.width, img.height * 2))
            combined_img.paste(img, (0, 0))
            combined_img.paste(img_mirrored, (0, img.height))
            images.append(combined_img)
            if len(images) >= 10:
                break
    return images

def create_pdf(images, output_path):
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    margin = 0.25 * inch
    border = 0.2 * inch
    img_width = 1.5 * inch
    img_height = 5 * inch

    positions = [
        (margin, height - margin - img_height),
        (margin + img_width + border, height - margin - img_height),
        (margin, height - margin - 2 * img_height - border),
        (margin + img_width + border, height - margin - 2 * img_height - border),
        (margin, height - margin - 3 * img_height - 2 * border),
        (margin + img_width + border, height - margin - 3 * img_height - 2 * border),
        (margin, height - margin - 4 * img_height - 3 * border),
        (margin + img_width + border, height - margin - 4 * img_height - 3 * border),
        (margin, height - margin - 5 * img_height - 4 * border),
        (margin + img_width + border, height - margin - 5 * img_height - 4 * border),
    ]

    for i, img in enumerate(images):
        x, y = positions[i]
        c.drawImage(img, x, y, width=img_width, height=img_height)

    c.showPage()
    c.save()

def main():
    image_dir = 'path/to/your/image/directory'  # Change this to your directory
    output_path = 'output.pdf'
    
    images = process_images(image_dir)
    create_pdf(images, output_path)

if __name__ == "__main__":
    main()
