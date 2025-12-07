"""
Simple icon creator for JobDocs
Creates a basic icon if none exists
Requires: pip install Pillow
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    import os

    def create_icon():
        """Create a simple icon for JobDocs"""

        # Icon is created in windows_installer directory
        icon_path = 'icon.ico'

        if os.path.exists(icon_path):
            print(f"Icon already exists at {icon_path}")
            return

        # Create images at multiple sizes for the .ico file
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        images = []

        for size in sizes:
            # Create new image with transparent background
            img = Image.new('RGBA', size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Background circle (blue)
            margin = size[0] // 8
            draw.ellipse(
                [margin, margin, size[0] - margin, size[1] - margin],
                fill=(41, 128, 185, 255),  # Nice blue color
                outline=(52, 73, 94, 255),
                width=max(1, size[0] // 32)
            )

            # Draw "JD" text
            font_size = size[0] // 3
            try:
                # Try to use a nice font if available
                font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", font_size)
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()

            text = "JD"
            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Center the text
            x = (size[0] - text_width) // 2 - bbox[0]
            y = (size[1] - text_height) // 2 - bbox[1]

            # Draw text with shadow
            shadow_offset = max(1, size[0] // 64)
            draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 128), font=font)
            draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

            images.append(img)

        # Save as .ico file
        images[0].save(icon_path, format='ICO', sizes=[(img.width, img.height) for img in images])
        print(f"✓ Created {icon_path} successfully!")

        # Also save as PNG for reference
        png_path = icon_path.replace('.ico', '.png')
        images[0].save(png_path, format='PNG')
        print(f"✓ Created {png_path} for reference")

except ImportError:
    print("PIL/Pillow not installed. Skipping icon creation.")
    print("Install with: pip install Pillow")
    print("Or provide your own icon.ico file")

if __name__ == '__main__':
    create_icon()
