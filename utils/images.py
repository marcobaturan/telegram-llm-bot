from PIL import Image
import base64
import io


def openai_requirements_image_resize(img: Image.Image) -> Image.Image:
    """
    Resize the image according to OpenAI vision constraints:
    - High-res mode: long side <= 2000px, short side <= 768px
    Only downsizes; never upscales.
    """
    width, height = img.size

    # If already within limits, return as-is
    if width <= 2000 and height <= 2000 and min(width, height) <= 768:
        return img

    aspect_ratio = width / height
    new_width, new_height = width, height

    # First, cap the long side to 2000
    if max(width, height) > 2000:
        if width > height:
            new_width = 2000
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = 2000
            new_width = int(new_height * aspect_ratio)

    # Then ensure the short side <= 768
    if min(new_width, new_height) > 768:
        if new_width < new_height:
            new_width = 768
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = 768
            new_width = int(new_height * aspect_ratio)

    # Only downsizing
    new_width = min(width, new_width)
    new_height = min(height, new_height)

    return img.resize((new_width, new_height), Image.LANCZOS)


def encode_image_to_data_url(img: Image.Image, fmt: str = "JPEG") -> str:
    """
    Encode a PIL image to a base64 data URL (default JPEG).
    Converts to RGB for JPEG safety.
    """
    buf = io.BytesIO()
    if fmt.upper() == "JPEG":
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    mime = "image/jpeg" if fmt.upper() == "JPEG" else f"image/{fmt.lower()}"
    return f"data:{mime};base64,{b64}"
